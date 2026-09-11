# Per-writer JSONL transaction log — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single rewritten `transactions.json` array (exclusive lock + O(n) rewrite per append) with one append-only `.jsonl` file per writer, no lock, with readers that tolerate an in-flight last line and an archive step that materializes the legacy array.

**Architecture:** A stdlib-only module `agents/shared_records.py` owns the format (writer, reader, materialize CLI). `BaseAgent.append_shared_record` is the only agent-facing entry point. The two consumers (`simulation_monitor`, `tx_analyzer.rs`) read the directory and fall back to the array when the directory is absent. `run_sim.sh` copies the directory into the archive and materializes `transaction_registry/transactions.json`.

**Tech Stack:** Python 3.12 stdlib (`os`, `json`, `glob`, `logging`), Rust (`serde_json`, existing `tempfile` dev-dependency), bash.

**Spec:** `docs/superpowers/specs/2026-09-11-per-writer-jsonl-transaction-log-design.md` (binding authority).

## Global Constraints

- No agent may ever block in the kernel on a lock: no `fcntl.flock(` outside `agents/file_locking.py` (enforced by `scripts/test_file_locking.py`), and the new writer uses no lock at all.
- Record fields stay exactly `tx_hashes`, `sender_id`, `recipients`, `total_amount`, `timestamp`, plus the two additions `writer_id` and `seq`.
- `agents/shared_records.py` imports only the standard library and nothing from `agents.*`, and must run as a script (`python3 agents/shared_records.py …`) because `run_sim.sh` uses the system `python3`, not the venv, and `agents/__init__.py` pulls in the whole agent stack.
- Readers skip a final line lacking `\n` (in-flight write) and skip-and-count an unparseable line.
- Global order everywhere is `(timestamp, writer_id, seq)`.
- Both readers fall back to `transactions.json` when `<shared_dir>/transactions/` does not exist.
- Python tests: `venv/bin/python -m pytest <file> -q`; full suite `venv/bin/python -m pytest agents/ scripts/ -q`. Rust: `cargo test --release --bin tx_analyzer` (or the crate's usual `cargo test`).
- Commit per task with explicit paths; message trailers:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01GE7jWZHV88pnyEcsyuR13G`.

---

### Task 1: `agents/shared_records.py` + tests

**Files:**
- Create: `agents/shared_records.py`
- Test: `agents/test_shared_records.py` (next to `agents/test_base_agent.py`, same pytest style)

**Interfaces (Produces):**
```python
DEFAULT_STREAM = "transactions"
def records_dir(shared_dir: Path | str, stream: str) -> Path            # <shared_dir>/<stream>
class RecordWriter:
    def __init__(self, shared_dir, stream: str, writer_id: str): ...     # lazy open on first append
    def append(self, record: dict) -> dict                               # adds writer_id, seq; ONE os.write; returns the record written
    def close(self) -> None
    seq: int                                                             # last sequence number written (0 before any)
def iter_records(shared_dir, stream: str) -> Iterator[dict]              # sorted filenames, complete lines only
def load_records(shared_dir, stream: str) -> list[dict]                  # sorted by (timestamp, writer_id, seq)
def materialize_array(shared_dir, stream: str, out_path) -> int          # writes JSON array (indent=2), returns count
# CLI: python3 agents/shared_records.py materialize <shared_dir> <stream> <out_path>  -> prints the count, exit 0
```
Writer details: directory created with `mkdir(parents=True, exist_ok=True)`; file opened once with `os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)`; line = `json.dumps(record, separators=(",", ":")) + "\n"` encoded UTF-8, emitted with a single `os.write`; `append` must not mutate the caller's dict (copy, then add `writer_id` and `seq`). `seq` starts at 1 per `RecordWriter` instance. Reader details: a file's last line without a trailing newline is skipped; a line that fails `json.loads` is skipped and counted, and one `logging.warning` per `iter_records` call reports the count and file. Missing directory yields nothing. Sorting key uses `record.get("timestamp", 0.0)`, `record.get("writer_id", "")`, `record.get("seq", 0)`.

- [ ] **Step 1: Write the failing tests** in `agents/test_shared_records.py` (use `tmp_path`):
  - `test_writer_creates_dir_and_appends_lines`: two appends → file `<tmp>/transactions/user-1.jsonl` has 2 newline-terminated lines, each parses, `seq` 1 and 2, `writer_id == "user-1"`, caller's dict unchanged.
  - `test_writer_reopen_continues_after_close`: append, close, new RecordWriter with the same ids, append → the file has 2 lines (seq restarts at 1 for a new instance — assert the documented behaviour, do not implement recovery).
  - `test_iter_skips_unterminated_last_line`: write one complete line and one partial line without `\n` → `iter_records` yields 1 record.
  - `test_iter_skips_and_counts_corrupt_line` (use `caplog`): a `{not json` line between two good lines → 2 records, one warning mentioning the file.
  - `test_load_orders_by_timestamp_writer_seq`: three writer files with interleaved timestamps → expected order.
  - `test_missing_dir_yields_nothing`.
  - `test_materialize_array_roundtrip`: materialize → `json.load` gives the same list as `load_records`, count returned matches.
  - `test_cli_materialize` (`subprocess.run([sys.executable, "agents/shared_records.py", "materialize", ...], cwd=repo_root)`): exit 0, prints the count, output file valid.
- [ ] **Step 2: Run** `venv/bin/python -m pytest agents/test_shared_records.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `agents/shared_records.py` per the interface (module docstring: why per-writer append-only, why no lock, the torn-line rule, the stdlib-only rule).
- [ ] **Step 4: Run** the file's tests → PASS; run `venv/bin/python -m pytest scripts/test_file_locking.py -q` → PASS (no flock introduced).
- [ ] **Step 5: Commit** `agents/shared_records.py agents/test_shared_records.py` — `feat(agents): per-writer append-only JSONL record store (no locks)`.

### Task 2: `BaseAgent.append_shared_record`, migrate both callers, delete `append_shared_list`

**Files:**
- Modify: `agents/base_agent.py` (delete `append_shared_list` at ~630-665; add `append_shared_record`; close writers in `_cleanup_agent`)
- Modify: `agents/regular_user.py:482`, `agents/miner_distributor/agent.py:1377`
- Test: `agents/test_base_agent.py` (add), `agents/test_shared_records.py` unchanged

**Interfaces:**
- Consumes: `agents.shared_records.RecordWriter`.
- Produces: `BaseAgent.append_shared_record(self, stream: str, record: dict) -> dict` — lazily creates one `RecordWriter(self.shared_dir, stream, self.agent_id)` per stream in `self._record_writers: dict[str, RecordWriter]`; returns the record written. `_cleanup_agent` (or wherever the agent's existing shutdown hook lives — find it) closes every writer.

- [ ] **Step 1: Failing test** in `agents/test_base_agent.py`, following that file's existing fixture for constructing an agent with a temp `shared_dir`: `test_append_shared_record_writes_per_writer_jsonl` — two appends land in `<shared_dir>/transactions/<agent_id>.jsonl` with `seq` 1, 2 and `writer_id == agent_id`; and `test_append_shared_list_removed`: `assert not hasattr(BaseAgent, "append_shared_list")`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**; change `regular_user.py` to `self.append_shared_record("transactions", tx_record)` and `miner_distributor/agent.py` likewise (the `tx_record` dicts keep their five fields). Delete `append_shared_list` and its docstring. Keep `write_shared_state`/`read_shared_state` untouched.
- [ ] **Step 4: Run** `venv/bin/python -m pytest agents/test_base_agent.py agents/test_shared_records.py -q` → PASS; `grep -rn append_shared_list agents/ scripts/ src/ docs/` → only the spec/plan/CHANGELOG mention it (fix any other hit).
- [ ] **Step 5: Commit** — `refactor(agents): transactions ledger is per-writer JSONL; remove append_shared_list`.

### Task 3: simulation monitor reads the directory (with legacy fallback)

**Files:**
- Modify: `agents/simulation_monitor/agent.py:950-992` (`_read_transaction_data`)
- Test: `agents/test_simulation_monitor.py` (add)

**Interfaces:**
- Consumes: `agents.shared_records.load_records`.
- Produces: `_read_transaction_data` unchanged in signature and in what it computes (`unique_tx_hashes`, `tx_created_by_node`, `total_created`); the record loop is factored into a pure module-level function `summarize_transaction_records(records: list[dict]) -> tuple[set[str], dict[str, int], int]` so it is testable without an agent instance. Layout choice: if `records_dir(shared_dir, "transactions")` exists → `load_records`; elif `<shared_dir>/transactions.json` exists → `json.load` of the array (legacy); else → empty.

- [ ] **Step 1: Failing tests** (look at how `agents/test_simulation_monitor.py` already builds fixtures and follow it): `test_summarize_transaction_records_counts_unique_hashes_and_per_node` (two writers, one duplicate hash across records, legacy `tx_hash` field on one record); `test_read_transaction_data_prefers_directory_over_legacy_array` (temp shared dir containing both layouts with different contents → the directory wins); `test_read_transaction_data_legacy_array_fallback`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `venv/bin/python -m pytest agents/test_simulation_monitor.py -q` → PASS.
- [ ] **Step 5: Commit** — `feat(monitor): read the per-writer transactions directory, fall back to the legacy array`.

### Task 4: `tx_analyzer.rs` loader

**Files:**
- Modify: `src/bin/tx_analyzer.rs:1861-1950` (`load_transactions`)
- Test: same file, `#[cfg(test)]` module using the `tempfile` dev-dependency

**Interfaces:**
- Produces: `load_transactions(shared_dir)` unchanged in signature/return; when `<shared_dir>/transactions/` exists, read each `*.jsonl` in sorted filename order, one `serde_json::Value` per complete line (a trailing line with no `\n`, or one that fails to parse, is skipped with `log::warn!`), then sort by `(timestamp, writer_id, seq)` before the existing per-record handling (current `tx_hashes` array + legacy `tx_hash` string paths stay as they are); otherwise fall back to `transactions.json` exactly as today.

- [ ] **Step 1: Failing test**: build a temp dir with `transactions/a.jsonl` (2 records, one with two `tx_hashes`), `transactions/b.jsonl` (1 record, earlier timestamp) and a partial trailing line; assert `load_transactions` returns 4 `Transaction`s in `(timestamp, writer_id, seq)` order; second test: only a legacy `transactions.json` array present → same result as before this change.
- [ ] **Step 2: Run** `cargo test --bin tx_analyzer load_transactions` → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; `cargo build --release` succeeds.
- [ ] **Step 5: Commit** — `feat(tx_analyzer): load per-writer JSONL transactions with legacy fallback`.

### Task 5: `run_sim.sh` archive + materialize

**Files:**
- Modify: `run_sim.sh` `archive_transaction_registry()` (~1614-1655) and the summary line at ~1799-1801 if it counts `*.json` only.

- [ ] **Step 1:** In `archive_transaction_registry`, after copying the JSON/lock files: if `"$SHARED_DIR/transactions"` is a directory, `cp -r` it to `"$tx_dir/transactions/"` and run `python3 agents/shared_records.py materialize "$SHARED_DIR" transactions "$tx_dir/transactions.json"` (log the count; a failure is a `log_warn`, not fatal). Keep the copy of any legacy `transactions.json` if one exists in the shared dir (old agents).
- [ ] **Step 2:** `bash -n run_sim.sh`; then a dry check: create a fake `$SHARED_DIR` with two `.jsonl` writers in a temp dir, source only the function (or run the two commands by hand) and confirm the archive layout + materialized count.
- [ ] **Step 3: Commit** — `feat(run_sim): archive per-writer transaction logs and materialize transactions.json`.

### Task 6: CHANGELOG + docs

**Files:**
- Modify: `CHANGELOG.md` (`## [Unreleased]` → `### Changed`), `docs/ARCHITECTURE.md` and `docs/ANALYSIS_TOOLS.md` (wherever they describe `transactions.json` / the shared directory / `transaction_registry`), spec status line.

- [ ] **Step 1:** CHANGELOG entry: "Transactions ledger is now one append-only `shared/transactions/<agent_id>.jsonl` per writer (fields unchanged plus `writer_id`, `seq`), with no file lock; the monitor and `tx_analyzer` read the directory and fall back to the old array; the archive still contains `transaction_registry/transactions.json` (materialized at archive time). Only tools that read `transactions.json` from the **live** shared directory during a run are affected." Reference the flock deadlock entry above it.
- [ ] **Step 2:** Update the two docs' descriptions of the file layout (state the per-writer files, the ordering rule, the torn-line rule, and that the archive materializes the array). Mark the spec's Status line "implemented 2026-09-11 (this plan)".
- [ ] **Step 3: Commit** — `docs: per-writer transaction log layout, changelog`.

### Task 7 (controller, not a subagent): acceptance run

- [ ] Baseline: `archived_runs/<ts>_jsonl_before` (quickstart.yaml, seed 12345, run on unchanged code).
- [ ] After: `nice -n10 ./run_sim.sh --config test_configs/quickstart.yaml --name jsonl_after --no-monitor`.
- [ ] Compare `summary.txt`: `Transactions broadcast` / `Transactions in blocks` / `Blocks mined` counts identical; `Result: ALL CHECKS PASSED` both.
- [ ] After-run checks: `transaction_registry/transactions/*.jsonl` exist, every line newline-terminated (`tail -c1` of each file is `\n`), materialized `transaction_registry/transactions.json` record count == total line count, no `transactions.lock` in the live shared dir listing (`transaction_registry/` has no `transactions.lock`), monitor's `transaction_tracking.json` totals match the before run.
- [ ] Full suites green: `venv/bin/python -m pytest agents/ scripts/ -q`, `cargo test`.
