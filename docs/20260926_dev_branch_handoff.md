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

## Progress log

### 2026-09-26 — bootstrap on the 64-core / 251 GB box; campaign step 1 done; matrix launched

- Box: Ubuntu 24.04 (looks release-upgraded from 20.04 after 2026-09-19).
  Two bootstrap snags, both fixed and recorded: a leftover apt.llvm.org
  *focal* repo broke `clang-18` (disable it, `--allow-downgrades` the two
  LLVM 18 libs), and CMake caches from before the upgrade remembered
  `libdl.so` / `librt.so` dev symlinks glibc 2.39 no longer ships
  (`rm -rf sibling_repos/shadowformonero/build`; `cmake -U RT -U
  PROTOLIB_LIBRARY .` in `sibling_repos/monero/build/release`). setup.sh
  now builds monero without Trezor/Ledger (1c465f5e) and offers the
  native-mining micro gate as its `--sim-binary` test run (7ecc2c1c).
- Verification: provenance matches all five patch shas (built
  2026-09-26T12:41Z); Rust 170 passed; pytest 647 passed; the three smokes
  green through the health gate (`20260926_125218_sop_fork_smoke`,
  `20260926_130449_pop_exact_fast`, `20260926_132145_snap_sop`).
- Step 1: `chain_snapshots/h10/` generated (run `20260926_125216_preload_h10`,
  29 min wall), verified, committed with the generator scenario, the base
  switch (`selfish_micro_sop.yaml`: `chain_snapshot: h10`, no
  fixed-difficulty, attacker + bridge at 0 s) and the two matrix specs
  (80821982).
- Reviews (three parallel: `main..dev` diff, daemon patches in a patched
  worktree, measurement pipeline vs manuscript) found one BLOCKER for the
  matrix — the share denominator included the grafted preload blocks — plus
  a first-tick fork=0 artifact in the attacker agent and two matrix-runner
  overlay bugs. All fixed with tests in 21c61e1a BEFORE launch. Daemon-patch
  findings (SoP weight table keeps a late block's share weight, contrary to
  the design doc; duplicate share slot truncates later embeddings; vote
  check and workshare pooling not gated on the sim flags; exact-uncle
  sibling check) are results-neutral for withholding attackers and are
  queued as a separate patch + rebuild + smoke. Full finding lists are in
  this session's review outputs; the fix commits cite them.
- Step 2: `pop_sop2_h10` (seed 12345) and `pop_sop2_h10_rep` (seed 54321),
  6 cells each, all 12 concurrently. Launched 13:42Z; stopped at 13:54Z to
  try `parallelism: 4` (12 x 13 default Shadow workers had load ~175 with
  the CPU mostly idle) — that STALLED the grafted cells at 5 sim-seconds
  (recorded in the base's comment; do not lower the worker count); final
  relaunch 14:08Z at the default. At ~1x realtime the 6 h cells finish
  around 20:15Z. Results land in
  `matrix_runs/pop_sop2_h10*/{table.md,results.json}`; gate every row on
  `health == ok`, `attacker_found > 0`, `forks_seen > 0`,
  `preload_blocks == 336`. Every run's `binary_provenance.txt` records the
  12:41Z monerod-sim (pre-fix patch stack) they ran on.
- Analysis tooling added while the matrix runs (a78492af): the bridge's
  chain (stock fork choice) is the default reference; `share_honest_ref`
  now sits beside `share`, computed from the first honest miner's daemon
  log via `scripts/honest_chain_from_log.py` (the archived LMDBs are
  useless for this — Shadow's hard stop plus `db-sync-mode: fastest`
  leaves them at genesis; `--archive-blockchain` output is empty for
  native-mining runs). `scripts/selfish_matrix.py --reanalyze <spec>`
  recomputes every finished cell from its archive without re-running —
  run it on both specs when the matrix ends so the rows carry the fixed
  analysis and the honest-reference column.
- Daemon-patch fixes (weight table l_b gates shares; duplicate share slot
  skipped; unflagged nodes don't pool/relay shares; SoP-only tie RNG
  seeded; slot logged as a number) are COMMITTED in `patches/monero-sim-pop.patch`
  after two smokes of a scratch build (`20260926_140023_sop_fork_smoke_fixed`
  on the h10 graft, `20260926_141745_sop_fork_smoke_fixed_off` on this
  morning's exact cold-start config: exit 0, 0 exceptions, 271 forks, 263 of
  281 subjective decisions share-weighted). The INSTALLED monerod-sim
  (12:41Z) predates it, so `monerod-sim.provenance` no longer matches the
  tree until you rebuild: `./setup.sh --sim-binary` (or its
  install_sim_monerod steps), then the three smokes on the installed binary.
  Do that only after the running matrix has finished — its daemons are the
  12:41Z build and their runs record it. The hard-fork vote bypass stays
  unconditional by design (the unflagged bridge must carry SoP blocks); the
  "byte-for-byte stock" wording was qualified.
- Open decision for the owner: does the manuscript still want the MRL #144
  exact-uncle variant (≈10 more cells at n=2)? Otherwise keep the det-tie
  relabel.

## Where the reasoning lives

- `docs/20260925_e4_code_data_review.md` — the audit, the fix log, the
  re-run plan.
- `docs/20260922_selfish_mining_manuscript.md` — findings (with
  retraction notices), ledger of every run.
- `docs/20260923_sop_design.md` — Share-or-Perish design + retracted steps.
- `docs/CHAIN_SNAPSHOT.md`, `docs/CHAIN_SNAPSHOT_REGEN.md` — the preload
  feature and its regen/consumer outcomes.
- `docs/SELFISH_MINING.md` §11 — the matrix runner.
