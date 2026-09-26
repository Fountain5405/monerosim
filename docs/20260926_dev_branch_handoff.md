# `dev` branch handoff — for a fresh agent on a fresh box (2026-09-26)

**Read this first.** `dev` is the integration branch for two feature lines
that must stay OFF `main` until the owner says otherwise (other people use
main): the chain-snapshot preload + mainnet-replica tooling
(`feat/mainnet-replica`) and the selfish-mining / countermeasure campaign
(`feat/selfish-mining-experiments`). Both feature branches stay intact;
new work happens on `dev`. Do not merge `dev` → `main` on your own.

## What is on `dev` and what has been proven

- Merge of `origin/main` (5183217b) + the replica branch (`bbfa6d26`) + the
  selfish branch (`6d6bf364`); see those merge commits for the two manual
  conflict resolutions (`finalize_hash` lives in `src/utils/seeded_hash.rs`;
  a duplicated test module was dropped).
- Daemon patch stack `patches/*.patch` (5 patches): replica's mining patch
  (adds `--sim-timestamp-offset`) + the selfish PoP/SoP patch with the
  2026-09-25 review fixes. All five apply cleanly to `monero.pin`.
- Verified on the pilot box (24 cores / 32 GB): Rust 154 unit + integration
  + golden tests, pytest 637; three daemon smokes green through the health
  gate (`scripts/sop_health_check.py`): `test_configs/sop_fork_smoke.yaml`,
  `test_configs/pop_exact_fork_smoke_fast.yaml`,
  `test_configs/dev_snapshot_sop_smoke.yaml` (grafts the `h50` snapshot:
  every daemon starts at height 1536 on an established difficulty).
- The `chain_snapshots/h50/` preset (1535 blocks, D0 ≈ 6000 for 50 h/s) is
  regenerated, verified and committed; the 114-node replica consumer smoke
  proved the graft end to end (`docs/CHAIN_SNAPSHOT_REGEN.md`, outcomes at
  the bottom).
- The E4 countermeasure state is in `docs/20260925_e4_code_data_review.md`:
  the earlier "SoP v2 works" verdict and every "exact uncle" claim are
  RETRACTED (five daemon defects, all fixed and validated); PoP-core,
  det-tie and mid-scale results stand. Section 3 there is the re-run plan.

## Bootstrap on a new box

```bash
git clone https://github.com/Fountain5405/monerosim.git && cd monerosim
git checkout dev
./setup.sh --sim-binary          # long first build (Shadow + monerod-sim)
# no TTY?  yes | ./setup.sh --sim-binary   (answers the prompts; kill the
# optional test simulation it launches at the end)
```

Then, before anything else:

```bash
# 1. the installed daemon must be THIS tree's patches
for p in patches/*.patch; do sha256sum "$p"; done
cat ~/.monerosim/bin/monerod-sim.provenance      # shas must match
# 2. tests
cargo test --release -q --no-fail-fast           # goldens need venv/ present
venv/bin/python -m pytest scripts/ agents/ -q
# 3. the three smokes, each gated (reorgs started == succeeded, 0 exceptions)
./run_sim.sh --config test_configs/sop_fork_smoke.yaml --name sop_fork_smoke --no-monitor
venv/bin/python scripts/sop_health_check.py archived_runs/<run> --diff 300 --w 16 --require-forks --require-share-weight
./run_sim.sh --config test_configs/pop_exact_fork_smoke_fast.yaml --name pop_exact_fast --no-monitor
venv/bin/python scripts/sop_health_check.py archived_runs/<run> --require-forks --require-share-weight
./run_sim.sh --config test_configs/dev_snapshot_sop_smoke.yaml --name snap_sop --no-monitor
venv/bin/python scripts/sop_health_check.py archived_runs/<run>
```

If a rebuild is ever needed without the full setup, `install_sim_monerod`
in `setup.sh` wants `MONEROSIM_BIN=~/.monerosim/bin` (the DIRECTORY) and
its `cp` is unchecked — always confirm the binary mtime and provenance.

## The campaign (why the 256 GB box)

1. **Micro preset for the selfish topology.** The `h50` preset is sized
   for the replica (50 h/s); on the 10 h/s micro topology it means 600 s
   blocks. Copy `test_configs/preload_chain.scenario.yaml`, set the
   miners' hashrates to the campaign base's total (e.g. 10 h/s → D0 =
   120 × 10 = 1200), `stop_time` ≈ 12 h (≥ 300 blocks: LWMA window + the
   SoP 160-block legacy window), `sim-timestamp-offset` = stop_time +
   600 s; run; `scripts/chain_snapshot.py export --total-hashrate 10
   --d0 1200 ...`; `verify`; commit `chain_snapshots/<name>/`. Then in
   `test_configs/selfish_micro_sop.yaml`: `chain_snapshot: <name>`, drop
   `fixed-difficulty`, the attacker can start at 0 s (synchronized).
2. **Re-run campaign** (review §3): the SoP cells of
   `test_configs/matrix/pop_sop2.yaml` at n=2 with stock pairs; stock
   baselines to n ≥ 2; exact-uncle cells only if the manuscript still
   wants the MRL #144 exact variant (otherwise keep the det-tie relabel).
   `scripts/selfish_matrix.py` runs a spec; set `parallel:` to what the
   box allows (~12 GB and ~2 cores per 6 h micro cell). Every cell's
   `health` column must read `ok`; a control cell that never forked
   proves nothing about fork choice.
3. **Never run a multi-hour simulation inside an agent tool call** —
   launch it detached (`setsid nohup ... &`) and poll; a tool timeout
   kills the shell. When killing leftovers, put `pgrep`/`kill` in a script
   file: a `pgrep -f` pattern inside the same command line self-matches.
4. **Full mainnet replica**: measured ≈ 240 MB per daemon + 2.1 GB per
   native miner; 1,107 nodes ≈ 270 GB. Step up (e.g. 300 nodes, light-mode
   RandomX) before the full run.

## Where the reasoning lives

- `docs/20260925_e4_code_data_review.md` — the audit, the fix log, the
  re-run plan.
- `docs/20260922_selfish_mining_manuscript.md` — findings (with
  retraction notices), ledger of every run.
- `docs/20260923_sop_design.md` — Share-or-Perish design + retracted steps.
- `docs/CHAIN_SNAPSHOT.md`, `docs/CHAIN_SNAPSHOT_REGEN.md` — the preload
  feature and its regen/consumer outcomes.
- `docs/SELFISH_MINING.md` §11 — the matrix runner.
