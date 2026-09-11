"""Tests for agents.shared_records: the per-writer append-only JSONL store.

agents/shared_records.py is stdlib-only and must also work when executed
directly as ``python3 agents/shared_records.py`` (no ``agents`` package
import), so these tests exercise both the importable API and the CLI
subprocess entry point.
"""
import json
import subprocess
import sys
from pathlib import Path

from agents.shared_records import (
    RecordWriter,
    iter_records,
    load_records,
    materialize_array,
    records_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_writer_creates_dir_and_appends_lines(tmp_path):
    caller_record = {"tx_hashes": ["abc"], "sender_id": "user-1"}
    writer = RecordWriter(tmp_path, "transactions", "user-1")

    first = writer.append(caller_record)
    second = writer.append(caller_record)
    writer.close()

    path = tmp_path / "transactions" / "user-1.jsonl"
    assert path.exists()
    lines = path.read_text().splitlines(keepends=True)
    assert len(lines) == 2
    for line in lines:
        assert line.endswith("\n")
        json.loads(line)  # each line parses on its own

    assert first["seq"] == 1
    assert second["seq"] == 2
    assert first["writer_id"] == "user-1"
    assert second["writer_id"] == "user-1"
    # append() must not mutate the caller's dict.
    assert caller_record == {"tx_hashes": ["abc"], "sender_id": "user-1"}


def test_writer_reopen_continues_after_close(tmp_path):
    writer = RecordWriter(tmp_path, "transactions", "user-1")
    writer.append({"sender_id": "user-1"})
    writer.close()

    writer2 = RecordWriter(tmp_path, "transactions", "user-1")
    second = writer2.append({"sender_id": "user-1"})
    writer2.close()

    path = tmp_path / "transactions" / "user-1.jsonl"
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    # Documented behaviour: seq restarts at 1 for a new instance (no
    # cross-process recovery of the last seq).
    assert second["seq"] == 1


def test_iter_skips_unterminated_last_line(tmp_path):
    directory = records_dir(tmp_path, "transactions")
    directory.mkdir(parents=True)
    (directory / "user-1.jsonl").write_bytes(
        b'{"sender_id":"user-1","seq":1}\n{"sender_id":"user-1","seq":2}'
    )

    records = list(iter_records(tmp_path, "transactions"))
    assert len(records) == 1
    assert records[0]["seq"] == 1


def test_iter_skips_and_counts_corrupt_line(tmp_path, caplog):
    directory = records_dir(tmp_path, "transactions")
    directory.mkdir(parents=True)
    (directory / "user-1.jsonl").write_text(
        '{"sender_id":"user-1","seq":1}\n'
        "{not json\n"
        '{"sender_id":"user-1","seq":2}\n'
    )

    with caplog.at_level("WARNING"):
        records = list(iter_records(tmp_path, "transactions"))

    assert len(records) == 2
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "user-1.jsonl" in warnings[0].getMessage()


def test_load_orders_by_timestamp_writer_seq(tmp_path):
    directory = records_dir(tmp_path, "transactions")
    directory.mkdir(parents=True)

    def line(timestamp, writer_id, seq):
        return json.dumps(
            {"sender_id": writer_id, "timestamp": timestamp,
             "writer_id": writer_id, "seq": seq},
            separators=(",", ":"),
        ) + "\n"

    (directory / "a.jsonl").write_text(line(2.0, "a", 1) + line(1.0, "a", 2))
    (directory / "b.jsonl").write_text(line(1.0, "b", 1))
    (directory / "c.jsonl").write_text(line(1.0, "a", 3))

    records = load_records(tmp_path, "transactions")
    ordering = [(r["timestamp"], r["writer_id"], r["seq"]) for r in records]
    assert ordering == [
        (1.0, "a", 2),
        (1.0, "a", 3),
        (1.0, "b", 1),
        (2.0, "a", 1),
    ]


def test_missing_dir_yields_nothing(tmp_path):
    assert list(iter_records(tmp_path, "transactions")) == []
    assert load_records(tmp_path, "transactions") == []


def test_materialize_array_roundtrip(tmp_path):
    writer = RecordWriter(tmp_path, "transactions", "user-1")
    writer.append({"sender_id": "user-1", "timestamp": 1.0})
    writer.append({"sender_id": "user-1", "timestamp": 2.0})
    writer.close()

    out_path = tmp_path / "transactions.json"
    count = materialize_array(tmp_path, "transactions", out_path)

    assert count == 2
    with open(out_path) as f:
        materialized = json.load(f)
    assert materialized == load_records(tmp_path, "transactions")


def test_cli_materialize(tmp_path):
    writer = RecordWriter(tmp_path, "transactions", "user-1")
    writer.append({"sender_id": "user-1", "timestamp": 1.0})
    writer.close()

    out_path = tmp_path / "transactions.json"
    result = subprocess.run(
        [sys.executable, "agents/shared_records.py", "materialize",
         str(tmp_path), "transactions", str(out_path)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "1"
    with open(out_path) as f:
        materialized = json.load(f)
    assert len(materialized) == 1
