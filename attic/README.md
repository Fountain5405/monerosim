# attic/

Ad-hoc tools and scripts preserved here for occasional use. **They are not part
of the supported product surface.**

These scripts were useful at some point during development or analysis, but
they are no longer wired into the main simulation pipeline and are no longer
maintained. Imports may break, behavior may diverge from the rest of the
codebase, and CLI flags may stop matching what's documented at the top of
each file. Nothing in this directory will be fixed unless and until someone
needs it again.

If you need one of these and it doesn't work, the expectation is that you
fix it for yourself (and ideally promote it back into `scripts/` with tests
if the use case justifies that).

## Running

These scripts assume they're run from the repo root with the repo root on
the Python path. Set `PYTHONPATH=.` so that imports like `from scripts.error_handling`
or `from agents.base_agent` resolve:

```sh
PYTHONPATH=. python attic/log_processor.py --help
```

## Contents

- `log_processor.py` — fuzzy-matching log summarizer; groups similar log lines
  to produce a more meaningful digest than naive deduplication.
- `enhanced_monitor.py` — live log-tailing monitor that parses agent log files
  in real time (blockchain progress, tx flow, network topology, etc.).
- `assess_internetness.py` — analyzes how closely a generated network resembles
  the real Internet: IP geography, latency, bandwidth distribution.
- `verify_transaction_inclusion.py` — cross-checks "transactions in blocks"
  counts between the log-based analysis and the monitor agent's data.
  **Broken**: depends on `scripts/post_simulation_monitor_analysis.py`, which
  was deleted. Kept here as a reference only.
- `regenerate_enhanced_blocks.py` — rebuilds `blocks_with_transactions.json`
  from `blocks_found.json` and `transaction_tracking.json` for runs where the
  monitor agent wasn't active.
- `sync_check.py` — checks that nodes have synchronized blockchains and are at
  the same height; uses dynamic agent discovery from the shared state directory.
