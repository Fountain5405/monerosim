# chain_snapshots/

Committed difficulty-preload presets for native mining. See
`docs/CHAIN_SNAPSHOT.md` for what these are and how `general.mining.chain_snapshot`
consumes them, and `docs/superpowers/specs/2026-09-23-difficulty-preload-design.md`
for the design.

Each subdirectory is one preset:

```
<preset>/
  manifest.json       # height, D0, total_hashrate, monero_pin, hf_schedule,
                       # network_id, genesis_hash, tip_timestamp, tip_hash,
                       # generated_by_run, created_at
  blocks.jsonl.gz      # one JSON object per line, heights 1..height
```

Keep each preset **under 1 MB** (a ~1,500-block coinbase-only fakechain gzips
to well under that). Presets are generated with
`venv/bin/python scripts/chain_snapshot.py export ...` from a generator run
(recipe in `test_configs/preload_chain.scenario.yaml`'s header) and checked
with `scripts/chain_snapshot.py verify --preset <dir>` before committing.

Regenerate a preset whenever its target hashrate, `monero.pin`, or hard-fork
schedule changes — `general.mining.chain_snapshot: auto` matches on exactly
those fields and errors (naming the missing combination) if nothing fits.
