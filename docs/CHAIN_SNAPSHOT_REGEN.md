# Regenerating the `h50` chain snapshot (after the timestamp-offset fix)

**Date:** 2026-09-24
**Branch:** `feat/mainnet-replica` — fix committed at `4f60fcef`

This runbook is self-contained for a **fresh machine**. The snapshot regen is a
small job (5 native miners), so it does **not** need the big R7525 — any modest
box will do, which also gets it off a shared/contended machine.

## Why regenerate

`--sim-timestamp-offset` (in `patches/monero-sim-mining.patch`) shifts every
mined block's timestamp back so the generated chain's tip lands *before* the
Shadow epoch (`946684800` = 2000-01-01), letting a consumer run graft it in as
history. A bug meant the offset was applied only in `create_block_template`'s
full path, **not** in the cached-block-template fast path (hit on the miner's
5-second template refresh) — so only the first ~2 blocks were shifted and the
tip landed ~2 days *after* the epoch, failing snapshot `verify`. Fixed at
`4f60fcef` (offset now applied in the cached path too). The snapshot must be
**rebuilt with the fixed binary and regenerated.** Detail:
`docs/superpowers/specs/2026-09-23-difficulty-preload-design.md`,
`docs/CHAIN_SNAPSHOT.md`, and the header of
`test_configs/preload_chain.scenario.yaml`.

Evidence the fix is sufficient: the 114-node replica **smoke** (a normal genesis
start, no offset) reached final difficulty **5856 ≈ nominal 6000** with a 2.1-min
mean block interval — so the mining/DAA model is correct, and the earlier
`d0_measured=1197` was the timestamp outlier depressing difficulty, not a
hashrate shortfall. A clean regen should land `D0 ≈ 6000`.

## Resource needs

| Job | Footprint |
|---|---|
| **This regen** (5 native miners) | ~16–24 GB RAM, ~8 cores plenty; wall-time is single-core-bound (~10–19 h for the full pass). Modest box is fine. |
| Full ~1,107-node replica run (later, not this doc) | Tens of GB RAM over 16 h + many cores — that's what the R7525 is for. |

## 0. Prerequisites

`setup.sh` checks these and bulk-installs Boost if missing: `git`, `cmake`,
`cargo` (rust), `python3`, `build-essential`, `libglib2.0-dev`. See
`./setup.sh --help`.

## 1. Clone + checkout

```bash
git clone https://github.com/Fountain5405/monerosim.git
cd monerosim
git checkout feat/mainnet-replica          # must be at 4f60fcef or later
```

No submodules — a plain clone is complete.

## 2. Build (this bakes in the fix)

```bash
./setup.sh --sim-binary
```

`--sim-binary` builds `monerod-sim` = vanilla monerod (`monero.pin`) + our
patches, **including the fixed `monero-sim-mining.patch`**; it also pulls the
Shadow fork + monero per the committed `.pin` files, creates `venv/`, and
installs the Python deps. **First-time build is long** (Shadow + monerod from
source).

## 3. Short-verify FIRST (cheap gate — do this before the ~19 h run)

Confirms the timestamp fix took (tip lands before the epoch) without spending the
full run. A 30-minute pass is enough: `verify` gates on the tip-before-epoch
rule, not on `D0`, so `D0` not being settled yet is fine here.

```bash
venv/bin/python scripts/scenario_parser.py \
    test_configs/preload_chain.scenario.yaml -o /tmp/preload_verify.yaml --no-calibrate
sed -i 's/stop_time: 50h/stop_time: 30m/' /tmp/preload_verify.yaml   # or edit by hand

./run_sim.sh --config /tmp/preload_verify.yaml --name preload_verify \
    --no-monitor --no-clean --no-archive
# run_sim.sh prints "Run tmp dir: <DAEMON_DATA_BASE>" — note that path.

venv/bin/python scripts/chain_snapshot.py export \
    --data-dir "<DAEMON_DATA_BASE>/monero-miner-001" \
    --out /tmp/h50_verify/ --total-hashrate 50 --d0 6000 --generated-by preload_verify
venv/bin/python scripts/chain_snapshot.py verify --preset /tmp/h50_verify/
```

- **PASS** ⇒ the timestamp fix works (the tip is before the epoch). The
  `WARNING: d0_measured ... off nominal` that `export` prints here is expected —
  30 min is too short for the DAA to settle. Proceed to step 4.
- **FAIL on the timestamp rule** ⇒ the offset still isn't reaching every block;
  stop and re-open the patch rather than burning the full run.

**Correction (2026-09-25, first execution of this runbook):** `verify` requires
the tip to land *at most 1800 s* before the epoch, not merely before it — with
the 50 h offset (180,600 s) a 30-min run's tip lands ~178,900 s early and
`verify` prints `FAIL: tip is 178924s before the Shadow epoch, exceeds the 1800s
max gap`. That FAIL is the gap rule, not the timestamp fix (the tip time equals
epoch − offset + run time, i.e. the offset reached the last block). To exercise
the full `verify` rule in the short gate, size the offset for the short run:
`sim-timestamp-offset: 2400` (= 30 min + 10 min) in the expanded YAML. The
30-min run took ~9 min wall on a 24-core box.

## 4. Full regeneration

The authoritative recipe is in the header of
`test_configs/preload_chain.scenario.yaml`. In short:

```bash
venv/bin/python scripts/scenario_parser.py \
    test_configs/preload_chain.scenario.yaml \
    -o test_configs/preload_chain.expanded.yaml --no-calibrate

./run_sim.sh --config test_configs/preload_chain.expanded.yaml \
    --no-monitor --no-clean --no-archive          # ~10–19 h; note the printed DAEMON_DATA_BASE + run id

venv/bin/python scripts/chain_snapshot.py export \
    --data-dir "<DAEMON_DATA_BASE>/monero-miner-001" \
    --out chain_snapshots/h50/ --total-hashrate 50 --d0 6000 \
    --generated-by <run id printed by run_sim.sh>

venv/bin/python scripts/chain_snapshot.py verify --preset chain_snapshots/h50/
```

`verify` must **PASS**, and `export` should print **no `d0_measured` WARNING**
(i.e. `D0 ≈ 6000`). If `verify` passes but `d0_measured` is still far off after a
clean full run, that's a separate finding — stop and flag it rather than
committing.

The `stop_time` (50 h) and `--sim-timestamp-offset` (180,600 s) in the scenario
are already sized correctly — leave them as-is.

## 5. Commit + push

```bash
git add chain_snapshots/h50/          # blocks.jsonl.gz + manifest.json, keep <1 MB
git commit -m "feat(chain-snapshot): h50 preset (D0~6000, tip before epoch)"
git push origin feat/mainnet-replica
```

Then pull on the R7525 (or wherever the full replica runs) and generate/run the
replica as usual. The consumer side rebuilds an LMDB template from
`blocks.jsonl.gz` automatically (`chain_snapshot.py build-template`, cached per
machine) — nothing to do here beyond committing the preset.

## Regen outcome (2026-09-25)

Executed end to end on the 24-core / 32 GB pilot box, on this branch at
`edaeabfb`.

- **Generator** `20260925_121054_preload_h50` (5 × 10 h/s, 50 h simulated):
  5 h 38 min wall (≈ 9 simulated hours per wall hour — far under the
  10–19 h estimate above), 0 failed processes.
- **Export / verify**: 1535 blocks, 230 KB gzipped; `verify` PASS — tip 805 s
  before the Shadow epoch, `d0_measured` 5996 vs nominal 6000, median block
  interval 78 s (= 120 s mean × ln 2 for exponential inter-arrivals, so it is
  consistent with the 120 s target). Committed as `chain_snapshots/h50/`
  (`135e6b47`).
- **Note on the tip**: the consumer inherits the chain's *instantaneous* tip
  difficulty (6669 at height 1535 here), not the windowed `d0_measured`;
  LWMA then drifts it toward nominal over the following window. Expect the
  first consumer blocks ~10 % above D0.

## Consumer smoke outcome (2026-09-25)

`test_configs/mainnet_replica_smoke.scenario.yaml` (114 agents, 8 h
simulated, `chain_snapshot: auto`) run `20260925_175002_replica_smoke_h50`:

- Snapshot consumption: preset `chain_snapshots/h50`, cache key
  `a17488322c7a9c0a`, height 1535, D0 6000, **118 nodes seeded**, 180 MB
  copied; `build-template` took 37 s on the first (uncached) use.
- **Graft proven**: miner-001's FIRST mined block is HEIGHT 1536 at
  difficulty 6663 (not height 1 / difficulty 1); its last is HEIGHT 1689 at
  6324 (154 blocks); relay-001 ended at HEIGHT 1679 — the whole mesh ran on
  the preloaded chain. `run_sim` exit 0, 2 h 28 min wall.
- **2 of 5 miners were OOM-killed** (miner-003 at sim 01:21, miner-004 at
  01:25, SIGKILL): each native miner holds a ~2.1 GB RandomX dataset and the
  114-daemon fleet peaked at ~27.5 GB used + 2 GB swap on this 32 GB box.
  The remaining three miners kept the chain going (difficulty then eased
  from 6663 toward 6324), so the smoke completed, but the plumbing check ran
  at 30 h/s instead of 50 for most of the run. This is the runbook's own
  point: the replica belongs on the R7525. Options if it must run here:
  light-mode RandomX for the miners (`--sim-rx-full-dataset` off, ~256 MB
  each) or fewer/larger hosts.
