# Chain Snapshots (difficulty preload for native mining)

**Design:** `docs/superpowers/specs/2026-09-23-difficulty-preload-design.md`
Sec 5 ("A: chain snapshot"). **Depends on:** `docs/NATIVE_MINING.md`.

## What and why

Native mining (`general.mining.mode: native`) uses real RandomX and monerod's
real difficulty algorithm. A fresh regtest chain starts at difficulty 1 and
only reaches its equilibrium `D ≈ 120 × total_hashrate` once the algorithm's
720-block window fills — about 24 simulated hours of warm-up during which
blocks arrive far too fast and orphan/propagation/DAA behaviour isn't
representative. A chain snapshot skips that warm-up: a long fakechain, mined
once (offline, outside any consumer run) at the target difficulty, ships as a
small git-tracked preset and gets copied into every node's data dir before
Shadow starts. Every consumer run then joins a chain with a full, settled DAA
window from block 1 — mainnet-like, and free of the artificial warm-up.

The DAA's real response to a *later* hashrate change (still ~720 blocks) is
unaffected — only the one-time genesis warm-up is what this feature removes.

## The timestamp problem, and why a constant shift fixes it

Every monerosim run's Shadow clock starts at the same instant: 2000-01-01
00:00 UTC (`946,684,800`). A chain mined during a snapshot's own generator
run therefore accumulates timestamps starting from that *same* epoch, and by
the time it reaches height ~1,500 its blocks are timestamped far in the
future relative to a fresh consumer run's clock, which also starts at that
epoch. Monero's timestamp rules only check **order** (`>=` the median of the
last 60 blocks) and **not-in-the-future** (`<=` now + 2h) — never absolute
recency — so shifting *every* mined timestamp back by the same constant
during generation preserves both rules and produces a chain whose tip lands
safely *before* the epoch instead of after it. That shift is
`patches/monero-sim-mining.patch`'s `--sim-timestamp-offset <seconds>`
(generation-only; consumer runs never set it).

## Preset layout

```
chain_snapshots/<preset>/
  manifest.json       # height, D0, total_hashrate, monero_pin, hf_schedule,
                       # network_id, genesis_hash, tip_timestamp, tip_hash,
                       # generated_by_run, created_at
  blocks.jsonl.gz      # one JSON object per line, heights 1..height:
                       # {"height": N, "hash": "...", "blob": "<hex>"}
```

Presets are committed to the repo (small — gzip, not zstd, to avoid a new
Python dependency; see `chain_snapshots/README.md`), so cloning the repo is
enough to run a native-mining config with a preloaded chain — no generator
run required unless you need a new hashrate/version/hard-fork combination.

## Cache key and the local template

A preset's `blocks.jsonl.gz` isn't a usable monerod data dir by itself — the
blocks still need to be replayed through a real daemon (`submit_block`,
re-verifying every block's PoW) to produce an LMDB data dir. That replay
happens once per machine and is cached under
`~/.monerosim/chain_snapshots/<key>/`, keyed by
`sha256(D0, monero_pin, hf_schedule, network_id, height)[:16]` (computed in
`scripts/chain_snapshot.py`; the orchestrator never recomputes it — it always
invokes `build-template`, which is a fast no-op on a cache hit, and reads the
resulting cache path back from the script's own stdout).

## Consumer side

```yaml
general:
  mining:
    mode: native
    chain_snapshot: auto     # auto | off | <preset name> | <path>
```

- `off` — no preload, unconditionally (the historical cold-start warm-up).
- `auto` (default, **soft**) — pick the repo preset under `chain_snapshots/`
  whose `total_hashrate` and `monero_pin` match this run. Zero matches logs
  a warning naming the expected preset (hashrate + pin) and this doc's
  generator recipe, then continues without a snapshot (the same
  cold-start warm-up as `off`) — it does not error. More than one match is
  still a hard error listing the candidates.
- a bare name (no `/`) — `chain_snapshots/<name>/`.
- anything containing `/` — used as a path directly.

An explicit preset name or path (i.e. anything other than `auto`/`off`) is
always a hard error if it's missing or mismatched (see preflight, below) —
only `auto`'s zero-match case is soft.

YAML booleans are accepted as aliases: `false` == `off`, `true` == `auto`
(see the scenario-parser gotcha below — this is what makes a bare `off`
survive that round-trip without quoting).

**Only meaningful in native mode.** Setting `chain_snapshot` to a concrete
preset name/path while `mining.mode` isn't `native` is a config-load error
(`auto`/`off` are always accepted, in either mode, since they're no-ops
outside native mining — `auto` outside native mode never even scans
`chain_snapshots/`).

At generation time (in the `monerosim` binary, never inside Shadow) the
resolved preset is preflighted (manifest present; `monero_pin` matches;
`hf_schedule` matches, or both are empty; tip strictly before the Shadow
epoch and no more than 30 minutes earlier — the DAA's cut window would
otherwise eventually expose a gap that big), the local template cache is
ensured, and the cached LMDB data is copied
(`cp --sparse=always -r`) into every monerod-family agent's
`{daemon_data_dir}/monero-<id>/` — miners, relays, users, observers, spies.
Cuprate nodes are skipped: they sync the preloaded blocks from monerod peers
at boot, the same path they'd take on mainnet.

## Regenerating a preset

`test_configs/preload_chain.scenario.yaml` is the generator recipe (its
header has the exact commands): a tiny native-mining run — 5 miners × 10 h/s,
no users or relays — mined for 50 simulated hours (well past the 735+720 =
1,455-block DAA-window floor), with `--sim-timestamp-offset` set so the tip
lands ~10 minutes before the Shadow epoch. Run it with `--no-clean` so the
daemon data dir survives, then:

```bash
venv/bin/python scripts/chain_snapshot.py export \
    --data-dir "$DAEMON_DATA_BASE/monero-miner-001" \
    --out chain_snapshots/h50/ --total-hashrate 50 --d0 6000 \
    --generated-by <run id>
venv/bin/python scripts/chain_snapshot.py verify --preset chain_snapshots/h50/
```

then commit `chain_snapshots/h50/`.

## Config reference

| Key | Type | Default | Meaning |
|---|---|---|---|
| `general.mining.chain_snapshot` | string | `auto` | `auto` (soft) \| `off` \| preset name \| path. Native mode only. Also accepts YAML booleans (`true`/`false`) as `auto`/`off` aliases. |

## `scripts/chain_snapshot.py` reference

- `export --data-dir <dir> --out <preset dir> --total-hashrate N --d0 D --generated-by <id> [--hf-schedule <spec>]`
  — dump a generator run's chain (heights 1..tip) into a preset.
- `build-template --preset <dir> [--cache-root <dir>]` — materialize (or
  reuse) the local LMDB template cache; prints the cache path.
- `verify --preset <dir>` — manifest schema + `monero_pin` + timestamp checks.

## Gotcha: `off` through `scripts/scenario_parser.py`

`.scenario.yaml` files are expanded through Python's PyYAML, which resolves
a *bare* `off` (YAML 1.1) to the boolean `false` on re-emission — turning
`chain_snapshot: off` into `chain_snapshot: false` in the expanded config.
Quoting is no longer required to handle this: monerosim's config parser
accepts YAML booleans as aliases (`false` == `off`, `true` == `auto`), so
either a bare `chain_snapshot: off` or its round-tripped `chain_snapshot:
false` resolves the same way. `chain_snapshot: "off"` (quoted) still works
too. Configs loaded directly by monerosim (not through the scenario
expander) are unaffected either way — serde_yaml keeps a bare `off` as the
string `"off"`.
