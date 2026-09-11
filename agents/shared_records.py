"""Per-writer append-only JSONL record store.

Replaces the single ``transactions.json`` array (one exclusive lock,
rewrite-the-whole-file-per-append) with one append-only file per writer:
``<shared_dir>/<stream>/<writer_id>.jsonl``. There is exactly one process
appending to any given file, so nothing can interleave and no lock is
needed at all -- see the design doc
(docs/superpowers/specs/2026-09-11-per-writer-jsonl-transaction-log-design.md)
for why a shared lock under Shadow's native, blocking ``flock`` could freeze
the whole simulation.

Torn-line rule: a writer's ``open`` + single ``os.write`` per line means a
reader can only ever observe a *complete* previous line followed by, at
worst, an in-flight line with no trailing newline yet. Readers therefore
treat a final line without ``\\n`` as not-yet-written and skip it; a line
that has a trailing newline but fails to parse is corrupt and is skipped
and counted (not silently dropped).

This module imports only the standard library and nothing from
``agents.*``: ``run_sim.sh`` invokes it as
``python3 agents/shared_records.py materialize <shared_dir> <stream>
<out_path>`` using the system ``python3``, not the project's venv, and
``agents/__init__.py`` imports the whole agent stack (RPC clients, etc.)
which is not installed there.
"""
import glob
import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterator

DEFAULT_STREAM = "transactions"


def records_dir(shared_dir, stream: str) -> Path:
    """Return ``<shared_dir>/<stream>``, the directory of per-writer files."""
    return Path(shared_dir) / stream


class RecordWriter:
    """Appends JSON-object records to one writer's own file, no lock.

    One instance per (stream, writer_id) for the life of the process. The
    file is opened lazily, on the first ``append``, with ``O_APPEND`` so
    each ``os.write`` lands atomically at end-of-file even if something
    else has grown the file (it hasn't -- there is exactly one writer).
    """

    def __init__(self, shared_dir, stream: str, writer_id: str):
        self._path = records_dir(shared_dir, stream) / f"{writer_id}.jsonl"
        self._writer_id = writer_id
        self._fd = None
        self.seq = 0

    def _ensure_open(self) -> None:
        if self._fd is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fd = os.open(
                str(self._path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644
            )

    def append(self, record: dict) -> dict:
        """Write *record* plus ``writer_id``/``seq`` as one JSON line.

        Does not mutate the caller's dict. Returns the record actually
        written (a copy, with the two fields added).
        """
        self._ensure_open()
        self.seq += 1
        out = dict(record)
        out["writer_id"] = self._writer_id
        out["seq"] = self.seq
        line = (json.dumps(out, separators=(",", ":")) + "\n").encode("utf-8")
        os.write(self._fd, line)
        return out

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def iter_records(shared_dir, stream: str) -> Iterator[dict]:
    """Yield every complete record across all writer files, filename order.

    A missing directory yields nothing. Within each file, a final line
    with no trailing newline (an in-flight write) is skipped. A complete
    line that fails to parse is skipped and counted; at most one
    ``logging.warning`` is emitted per call, naming the offending file(s)
    and the total skipped count.
    """
    directory = records_dir(shared_dir, stream)
    if not directory.is_dir():
        return

    corrupt_total = 0
    corrupt_files: list[str] = []

    for path_str in sorted(glob.glob(str(directory / "*.jsonl"))):
        path = Path(path_str)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content:
            continue
        # Splitting on "\n" and dropping the last element discards, in one
        # step, either the empty tail after a trailing newline (all real
        # lines are complete) or an unterminated in-flight last line.
        lines = content.split("\n")[:-1]
        for line in lines:
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                corrupt_total += 1
                if path.name not in corrupt_files:
                    corrupt_files.append(path.name)

    if corrupt_total:
        logging.warning(
            "shared_records: skipped %d unparseable line(s) in %s",
            corrupt_total, ", ".join(corrupt_files),
        )


def load_records(shared_dir, stream: str) -> list:
    """All records, ordered by ``(timestamp, writer_id, seq)``."""
    records = list(iter_records(shared_dir, stream))
    records.sort(
        key=lambda r: (
            r.get("timestamp", 0.0), r.get("writer_id", ""), r.get("seq", 0),
        )
    )
    return records


def materialize_array(shared_dir, stream: str, out_path) -> int:
    """Write ``load_records`` as a legacy-shaped JSON array. Returns count."""
    records = load_records(shared_dir, stream)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return len(records)


def _main(argv: list) -> int:
    if len(argv) != 4 or argv[0] != "materialize":
        print(
            "usage: shared_records.py materialize <shared_dir> <stream> <out_path>",
            file=sys.stderr,
        )
        return 2
    _, shared_dir, stream, out_path = argv
    count = materialize_array(shared_dir, stream, out_path)
    print(count)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
