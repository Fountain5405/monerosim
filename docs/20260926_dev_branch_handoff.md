# `dev` branch handoff — for a fresh agent on a fresh box (2026-09-26)

**Read this first.** `dev` is the integration branch for two feature lines
that must stay OFF `main` until the owner says otherwise (other people use
main): the chain-snapshot preload + mainnet-replica tooling
(`feat/mainnet-replica`) and the selfish-mining / countermeasure campaign
(`feat/selfish-mining-experiments`). Both feature branches stay intact;
new work happens on `dev`. Do not merge `dev` → `main` on your own.

## What is on `dev` and what has been proven

- Merge of `origin/main` (5183217b) + the replica branch (`683373dd`) + the
  selfish branch (`a6b22994`); see those merge commits for the two manual
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
  now builds monero without Trezor/Ledger (8d511e45) and offers the
  native-mining micro gate as its `--sim-binary` test run (d428a1fb).
- Verification: provenance matches all five patch shas (built
  2026-09-26T12:41Z); Rust 170 passed; pytest 647 passed; the three smokes
  green through the health gate (`20260926_125218_sop_fork_smoke`,
  `20260926_130449_pop_exact_fast`, `20260926_132145_snap_sop`).
- Step 1: `chain_snapshots/h10/` generated (run `20260926_125216_preload_h10`,
  29 min wall), verified, committed with the generator scenario, the base
  switch (`selfish_micro_sop.yaml`: `chain_snapshot: h10`, no
  fixed-difficulty, attacker + bridge at 0 s) and the two matrix specs
  (4cd78307).
- Reviews (three parallel: `main..dev` diff, daemon patches in a patched
  worktree, measurement pipeline vs manuscript) found one BLOCKER for the
  matrix — the share denominator included the grafted preload blocks — plus
  a first-tick fork=0 artifact in the attacker agent and two matrix-runner
  overlay bugs. All fixed with tests in 21c94c3d BEFORE launch. Daemon-patch
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
- Analysis tooling added while the matrix runs (e2cc495b): the bridge's
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
- **Step 2 result (16:27Z, `docs/20260926_sop_h10_rerun.md`)**: all 12 cells
  green through the gate (`--reanalyze` at `703bdffe`). SoP v2 vs ES
  {0.035, 0.000} (honest-ref 0.000/0.000) vs stock {0.377, 0.441}; SoP v2 vs
  lead-2 {0.000, 0.000} vs stock {0.305, 0.469}; controls stock {0.381,
  0.410}, SoP {0.440, 0.326}. 2,822 of 2,822 subjective SoP decisions
  share-weighted, 0 exceptions. Manuscript §4 notice, §5 finding 10 and §7
  ledger updated; review §3 carries a status block. One cell's `run_sim.sh`
  exited 126 after a complete archive because the script was edited in place
  under 12 running instances (never do that; memory + `703bdffe`).
- Fixed `monerod-sim` (patch stack at `9cbd1be9`) INSTALLED 16:30Z with a
  provenance file matching the tree; the three bootstrap smokes on it are
  GREEN (16:54Z): `20260926_162837_sop_fork_smoke` (forks 110, all 110 SoP
  decisions share-weighted), `20260926_163610_pop_exact_fast` (reorgs 79/79
  per node, 3,767 forks, 111 uncle-weighted decisions),
  `20260926_164756_snap_sop` (h50 graft plumbing, 0 exceptions). The
  bootstrap check in this doc passes on this box as of that time. Any new
  cell runs on this binary.
- Owner decisions (17:40Z): run the MRL #144 exact cells; add the
  SoP-flagged honest-attacker control; `chain_snapshot` is not broken — the
  default became `off` because `auto` silently grafted h10 into the 22
  legacy 10 h/s configs; every campaign base names its preset explicitly.

### 2026-09-26 evening — exact-uncle sibling fix; campaign 3 launched

- **Patch fix (review F5c)**: `sim_pop_uncle_bonus_header` anchored the
  sibling test on `main[height-2]`, wrong for a containing block ≥ 3 deep in
  an alt chain (every legitimate uncle there was rejected); the deviated
  verifier had no sibling test. Both now read the parent block's own
  `prev_id` (`sim_pop_parent_prev`, main or alt). Patch sha `dcfbaeeb…`;
  built 17:50Z in the scratch worktree, INSTALLED 17:53Z (provenance matches
  the five tree shas; previous binary kept at the scratchpad's
  `bin_fixed/monerod-sim.installed-1353`). Smokes: all three gated smokes GREEN on the installed binary, run concurrently 17:55–18:14Z: `20260926_175546_pop_exact_fast_fix2` (reorgs 69/69 and 70/70 on the honest miners, 57/57 attacker, 104–107/104–107 on relays and seeds, 0 exceptions, 7,914 alternative blocks, **96 uncle headers COUNTED per honest miner with 0 "not a sibling" rejections** — the pre-fix run of the same config, `20260926_163610_pop_exact_fast`, counted 68/69 with 2 rejections — and 176 uncle-weighted fork decisions vs 111); `20260926_175531_sop_fork_smoke_fix2` (forks 230, all 230 SoP decisions share-weighted, 0 exceptions); `20260926_175601_snap_sop_fix2` (h50 graft plumbing, 0 exceptions).
- **Two probe bugs found by the scratch smoke**: (1) `run_sim.sh`'s
  capability gate read the probe's TAB-separated lines with `IFS=$'\t'`;
  TAB is IFS whitespace, adjacent tabs collapse, so an explicit patched
  binary needing no flag shifted the agent name into the flags column and
  the gate refused the run ("does not support --attacker-bridge"). The
  probe now writes `-` for an empty field and the gate treats it as none.
  (2) The probe substituted monerod-sim for EVERY native miner; the
  orchestrator does so only when the config says exactly `monerod`, so a
  miner pointed at an explicit build was probed at the wrong path. Both
  unit-tested (`scripts/test_run_sim_helpers.py`).
- **Campaign 3** (driver `run_campaign3.sh` in the scratchpad, detached;
  kill script beside it): stage 1 = `pop_exact_h10` + `_rep` (ES, lead-2,
  honest × exact; h10 base; stock pairs are pop_sop2_h10's rows) and
  `sop2_h10_ctl` + `_rep` (`upgraded_sop2`: attacker daemon connected +
  SoP-flagged; `connected_sop2`: connected, unflagged) — 10 micro cells at
  once (~11.5 GB each measured on the morning matrix). Stage 2, started by
  the driver when every stage-1 matrix has written `results.json`:
  `pop_exact_mid` + `_rep` (ES, lead-2, honest × {exact, none} on the
  UNCHANGED genesis mid base, 6 at once, ~20 GB each). Expect stage 1 to
  finish ~7 h after launch and stage 2 ~14 h after that. Read out with
  `venv/bin/python scripts/matrix_pairs.py pop_exact_h10 pop_exact_h10_rep
  --ledger` (and the other two pairs). Launched 18:14:56–18:15:56Z (runner pids in the scratchpad's `matrix3/pids.txt`; every run dir is named `*_<matrix>__<cell>`).

- **Stage 1 results (19:56–20:19Z)** — `docs/20260926_exact_uncles_and_sop_controls.md`.
  Exact micro: ES {0.169, 0.199} vs stock {0.377, 0.441}; lead-2 {0.284,
  0.292} vs {0.305, 0.469}; honest {0.378, 0.389}; all health ok — but **0
  uncle headers embedded** in any cell. Controls: `upgraded` {0.363, 0.368}
  (orphan 0.014/0.000, shares circulating), `connected` {0.394, 0.418}
  (orphan 0, no ties): the 17 lost ties of honest_sop2 draw 2 were the
  offline-bridge control's own latency, not an upgrade cost measurable here.
- **F5d + the γ ≈ 0 structural finding (20:05–20:30Z)**: added a template
  refresh when an accepted alternative block sits at the tip height (both
  uncle flags); two diagnostic smokes (`20260926_200552_pop_exact_fast_fix3`,
  `20260926_201720_pop_exact_fast_fix3b`, both green) showed embeddings still
  follow reorgs only, because the attacker's tie block never reaches honest
  miners alone at γ ≈ 0 (unflagged bridge relays no alternatives; the block
  arrives with its child via the sync path and is displaced at once). Exact =
  det-tie by construction in the single-bridge topology. Build installed
  20:30Z (pop sha `9492d7cb…`, provenance matches; SoP smokes not re-run —
  the hook cannot run in a SoP cell). Micro exact re-run (`pop_exact2_h10`)
  written then dropped as pointless.
- **Stage 2 launched 20:31Z**: `pop_exact_mid` + `_rep` (driver
  `run_stage2.sh` in the scratchpad; 6 mid cells at once, 12 total, ~2 waves
  of ~7 h → done ~11:00Z 09-27). Read out with
  `venv/bin/python scripts/matrix_pairs.py pop_exact_mid pop_exact_mid_rep --ledger`
  and count `embedding uncle header` per honest miner before reading shares.
- Owner decision opened: a γ > 0 exact cell (bridge with `sim-relay-alt-blocks`)
  is the only way to measure the uncle term against the attacker itself.

- **Stage 2 results (2026-09-27T01:46Z)**: all 12 mid cells health ok. Exact
  vs stock: ES {0.253, 0.303} vs {0.376, 0.518}; lead-2 {0.241, 0.251} vs
  {0.455, 0.351}; honest {0.416, 0.367} vs {0.405, 0.470}. Uncle term live
  but rare (12–22 embeddings per attack cell, all skips "not sibling").
  Exact ES sits inside the retained det-tie-only mid range, so a
  same-daemon det-tie pair (`pop_dettie_mid{,_rep}`, ES + lead-2, 4 cells,
  driver `run_stage3.sh`) was launched 01:47Z; ~5 h.

- **Campaign 4 launched 03:27Z (owner request)**: `pop_exact_relay` + `_rep`,
  exact with a relaying attacker bridge (`sim-relay-alt-blocks`), {ES,
  lead-2} × {stock, det-tie, exact}, 12 micro cells, driver
  `run_relay_matrix.sh`. Relay smoke green, first attacker uncle ever
  counted. New `scripts/uncle_attribution.py`: 0 attacker uncles in every
  earlier exact cell. Rationale: results doc §4.

- **Campaign 4 done (06:12Z)**: relay results + two new findings in
  `docs/20260926_exact_uncles_and_sop_controls.md` §4–§5. The uncle term never
  entered a fork decision (138 attacker uncles embedded, 0 counted); relay
  gives the attacker γ 0.10–0.43 under PoP det-tie. **Attacker stranding**:
  the stock bridge adopts long released branches the flagged miners reject,
  so the attacker keeps mining them (SoP cells lost 28–57 % of attacker
  blocks this way; explains most PoP spread). Tool:
  `scripts/attacker_stranding.py`. Owner decision open: re-run attack cells
  with a bridge that runs the honest rule.

- **Stranding re-run launched 2026-09-27T13:02Z (owner said yes)**: the
  attacker's bridge runs the countermeasure rule (SoP cells: the relays'
  `sim-share-or-perish`; PoP cells: the honest miners' exact flags); nothing
  else changes (a test asserts it). Six matrices `pop_sop2_h10_fbridge`,
  `pop_exact_h10_fbridge`, `pop_exact_mid_fbridge` (+ `_rep`), ES and
  lead-2, 12 cells at once (8 micro ≈ 2.5 h, 4 mid ≈ 6–7 h), driver
  `run_fbridge.sh` in the scratchpad. Bridges confirmed flagged at start
  (PoP banner; SoP "weight table armed"). Read out per matrix with
  `scripts/matrix_pairs.py <m> <m>_rep` and `scripts/attacker_stranding.py`,
  against the original rows; record realized γ (PoP bridges may announce
  tie blocks that win det-tie).

- **Stranding re-run done (2026-09-27 16:00Z; read out 2026-09-28)**:
  12/12 health ok, commit `cf55ea8e`. Results:
  `docs/20260926_exact_uncles_and_sop_controls.md` §6.
  - Stranding NOT removed. Measured at the attacker's daemon, it still
    abandons rejected branches of up to 29 blocks. The flagged bridge
    rejects reveals and never announces them, so the honest-side
    `attacker_stranding.py` read ≈ 0. Cause: `SelfishStrategy` assumes a
    reveal wins and compares heights only.
  - SoP ES earned {0.405, 0.495}: a rejected branch stayed level past
    #146's k·w = 48 fail-safe window and won on cumulative difficulty.
    Lead-2 stayed at 0.000.
  - PoP shares stay below α, with γ 0.02–0.20.
  - Manuscript E4 notice, finding 10, §7 ledger, SoP re-run doc and review
    §3 status updated.
  - Owner decision open: a rejection-aware attacker (agent change).

- **2026-09-28/29 — rejection-aware attacker, block times, h10 regen**:
  - `reject_aware` attacker + monerod-sim `flush_cache sim_alt_blocks`
    (`f4005dfe`, `9c96e08f`, `3ad1cd09`). Smokes on the rebuilt daemon
    under way.
  - The post-run block-time summary now shows expected exponential
    counts, splits out the genesis warm-up and gives a verdict (`bff72772`).
  - `h10` snapshot found to start consumers 9.8 % under D0, so every h10
    cell ran ~10 % fast (results doc §7). `chain_snapshot.py` now gates on
    the next-block difficulty (`ca01aa4d`); a 32 h generator
    (`preload_h10_32h`) is running to replace the preset.

## Where the reasoning lives

- `docs/20260925_e4_code_data_review.md` — the audit, the fix log, the
  re-run plan.
- `docs/20260922_selfish_mining_manuscript.md` — findings (with
  retraction notices), ledger of every run.
- `docs/20260923_sop_design.md` — Share-or-Perish design + retracted steps.
- `docs/CHAIN_SNAPSHOT.md`, `docs/CHAIN_SNAPSHOT_REGEN.md` — the preload
  feature and its regen/consumer outcomes.
- `docs/SELFISH_MINING.md` §11 — the matrix runner.
