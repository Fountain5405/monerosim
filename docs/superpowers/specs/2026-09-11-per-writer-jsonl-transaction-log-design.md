# Per-writer JSONL transaction log — design

**Status:** implemented 2026-09-11 (plan `docs/superpowers/plans/2026-09-11-per-writer-jsonl-transaction-log.md`). Acceptance: quickstart.yaml seed 12345 before (`archived_runs/20260911_110213_jsonl_before`) vs after (`archived_runs/20260911_113847_jsonl_after`): 178 blocks both, 191 transactions in blocks both, 168 ledger records both, all summary checks PASS both; after-run archive has 4 per-writer files, 168 newline-terminated lines, materialized array of 168, no `transactions.lock`.
deadlock fixed in `agents/file_locking.py` (branch `fix/shadow-safe-flock`).
**Scope:** the shared transaction ledger only. The agent registry keeps its
lock (see §8).

## 1. Problem

`$MONEROSIM_SHARED_DIR/transactions.json` is one JSON array. Every append
(`BaseAgent.append_shared_list`, `agents/base_agent.py:630-665`) takes an
exclusive lock on `transactions.lock`, reads the whole array, appends one
record, rewrites the whole array to `.tmp` and renames it. Two writers use
it: `agents/regular_user.py:482` (every sent transaction) and
`agents/miner_distributor/agent.py:1377` (funding transactions).

Two consequences:

- **Cross-process mutual exclusion.** Under Shadow a blocking `flock` runs
  natively on the simulator's worker thread; when the holder is a
  descheduled host the worker never returns and the whole simulation
  freezes (300-node run, 2026-09-11, sim-time 5h56m). The non-blocking
  polling lock removes the freeze but not the contention.
- **Quadratic I/O.** Each append rewrites everything written so far. At
  5h56m of that run every append rewrote 2597 records (862 KB). The long
  rewrite is exactly the window in which native preemption pauses the
  holder, so the two problems feed each other.

The concurrent *writes* are the issue. Reads only mattered because a
shared-lock read blocks while an exclusive lock is held.

## 2. Goals and non-goals

Goals: no lock of any kind on the ledger; O(1) per append; the same record
schema and the same consumer-facing data; tolerance of a torn in-flight
write; deterministic global ordering; no change to agent timing.

Non-goals: a database (any cross-process database reintroduces kernel
file locks or a network service host inside the simulation); changing the
record fields; touching `agent_registry.json`.

## 3. Layout

```
$MONEROSIM_SHARED_DIR/transactions/<writer_id>.jsonl
```

One file per writer, named by `agent_id` (`user-034.jsonl`,
`miner-distributor.jsonl`). One JSON object per line. Record fields are
today's five (`tx_hashes`, `sender_id`, `recipients`, `total_amount`,
`timestamp`) plus two new ones:

| field | value | purpose |
| --- | --- | --- |
| `writer_id` | the appending agent's `agent_id` | the distributor's `sender_id` is the funding sender, not the writer |
| `seq` | per-writer counter from 1 | ordering and de-duplication |

The archived form keeps the same directory under
`<run>/transaction_registry/transactions/` plus a materialized
`transaction_registry/transactions.json` array (§6) for anyone who reads
the old shape.

## 4. Writer

New `BaseAgent.append_shared_record(stream: str, record: dict)`:

1. `path = shared_dir / stream / f"{agent_id}.jsonl"`; create the
   directory once (`exist_ok=True`).
2. On first use open the file once with
   `os.open(path, O_WRONLY | O_APPEND | O_CREAT, 0o644)` and keep the
   descriptor for the life of the process; close it in `_cleanup_agent`.
3. `seq += 1`; add `writer_id` and `seq`; encode with
   `json.dumps(record, separators=(",", ":")) + "\n"`; emit with one
   `os.write` call.

No lock, no temp file, no rename, no fsync. There is exactly one writer
per file, so nothing can interleave; the only observable hazard is a
reader seeing the last line before its newline lands, which §5 handles.
`open`/`write` on regular files go through Shadow's native passthrough
and never block, so the simulation cannot wedge on them. `O_APPEND`
survival through that passthrough is a check for the acceptance run, not
an assumption (§7).

`append_shared_list` loses both callers and is deleted; the regression
test in `scripts/test_file_locking.py` already forbids any blocking flock
from returning.

## 5. Readers

New module `agents/shared_records.py`:

- `iter_records(shared_dir, stream)`: glob `<shared_dir>/<stream>/*.jsonl`
  in sorted filename order; for each file yield `json.loads(line)` per
  complete line. A final line with no trailing newline is an in-flight
  write and is skipped. A line that fails to parse is skipped and counted;
  the count is logged once per call.
- `load_records(shared_dir, stream)`: `iter_records` collected and sorted
  by `(timestamp, writer_id, seq)`. Under Shadow `timestamp` is simulated
  time, so this order is deterministic across runs of the same seed. The
  old array's order was lock-acquisition order, which preemption made
  scheduler-dependent, so ordering improves.
- `materialize_array(shared_dir, stream, out_path)`: write
  `load_records` as a JSON array (the legacy shape).
- `python -m agents.shared_records materialize <shared_dir> <stream> <out>`
  for the wrapper (§6).

Consumers:

- `agents/simulation_monitor/agent.py:950-992` `_read_transaction_data`:
  replace the `json.load` of the array with `load_records(shared_dir,
  "transactions")`; the per-record field handling and the two files it
  writes (`transaction_tracking.json`, `blocks_with_transactions.json`,
  single writer each) are unchanged. If the `transactions/` directory is
  absent and `transactions.json` exists, read the array (old runs, mixed
  versions).
- `src/bin/tx_analyzer.rs:1861-1950` `load_transactions`: when
  `<shared_dir>/transactions/` exists, read every `*.jsonl` in sorted
  order line by line into the same `Vec<serde_json::Value>` and keep the
  existing current/legacy field handling; a trailing unparseable line is
  ignored with a warning; otherwise fall back to `transactions.json` as
  today. Sort by `(timestamp, writer_id, seq)` so Python and Rust agree.

## 6. Wrapper

`run_sim.sh` `archive_transaction_registry` (lines 1614-1655) copies
`*.json` and `*.lock` from the shared directory. Add: copy the
`transactions/` directory, then materialize
`transaction_registry/transactions.json` from it so external readers of
the archive keep the array shape. The live shared directory no longer
contains `transactions.json` or `transactions.lock` during a run; that is
the one consumer-facing change and goes in the CHANGELOG as such.

## 7. Verification

Unit tests (`scripts/test_shared_records.py`):

- append creates the directory and file, lines parse, `seq` increments,
  reopening after `_cleanup_agent` continues the sequence;
- `iter_records` skips an unterminated last line, skips and counts a
  corrupt line, returns nothing for a missing directory;
- `load_records` orders by `(timestamp, writer_id, seq)` across three
  writer files;
- monitor `_read_transaction_data` over a temp shared dir with two
  writers yields the same counts as the equivalent array.

Rust: a unit test for `load_transactions` on a fixture directory and on a
legacy array, both yielding the same `Transaction`s.

Acceptance: one quickstart-scale run (the 105-agent config) before and
after, same seed: identical `Transactions broadcast` and `Transactions in
blocks` counts in `summary.txt`; `transaction_registry/transactions/`
present, its materialized array has the same record count as the sum of
line counts; no `transactions.lock` created; every line in the archived
`.jsonl` files newline-terminated (confirms `O_APPEND` through Shadow).

## 8. Out of scope, noted

`agent_registry.json` is a read-modify-write dict under
`agent_registry.lock`, written once per agent at startup
(`base_agent._register_self`, lines 672-739) and read by the DNS server,
the miners, the distributor and the users. It keeps the non-blocking
polling lock. The same per-writer pattern (`registry/<agent_id>.json`,
readers glob) would remove that lock too and is a separate small change.

## 9. Work plan

1. `agents/shared_records.py` (writer helper, reader, materialize CLI) + tests.
2. `BaseAgent.append_shared_record`; migrate the two callers; delete
   `append_shared_list`.
3. Monitor reader with legacy fallback.
4. `tx_analyzer.rs` loader with legacy fallback + test.
5. `run_sim.sh` archive + materialize step.
6. CHANGELOG (Changed, consumer-facing) and the shared-directory layout
   note in the transaction-registry documentation.

Roughly 300 lines of Python, 60 of Rust, 20 of bash, plus tests: one PR.
