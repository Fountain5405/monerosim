# SoP study: handoff for the repository reorganisation (2026-11-01)

Branch: `sop-research`. Before the handoff commit it was at `1a6614cb`, and
nothing was unpushed. The branch left main at `5f04b397` (2026-10-22) and has
173 commits since. The handoff commit is tagged `handoff/sop`.

Do not rebase or squash: result docs cite commit hashes.

Main has 5 commits the branch lacks: `8220ba97`, `4fe1459a`, `b9c69d54`,
`44c8cf78` (v0.4.0) and `9d300222`. "Known problems" below explains why they
matter. The branch has not merged main, as asked.

## Status

The study asks whether Share-or-Perish (MRL #146) raises the hashrate a
selfish miner needs, and what it costs honest miners. It grew out of the
study's selfish-mining and Publish-or-Perish (MRL #144) work from 2026-09.

**Current findings: `docs/20261026_sop_attacker_search.md`**, items 1-11,
written up through 2026-11-01:

- **Threshold.** SoP raises the profitability threshold from 0.369 to 0.4635
  of hashrate. That is with two honest miners, K=3 and w=16, against the
  strongest attacker the search found. The race model agrees within 0.01.
- **MDP bounds.** At alpha 0.45 the optimal attack lies between 0.45 (lower)
  and 0.7265 (upper, 4/4 caps). The solver was cross-checked on 2026-10-31
  (item 11): it matches pymdptoolbox and the HiGHS LP, and it reproduces the
  epsilon-OPT column of SSZ's Bitcoin table.
- **Network advantage.** When the honest path is slower than d, SoP loses
  0.03-0.21 of protection. It still beats the stock rule by 0.15-0.2 below
  alpha 0.45, and ties it at 0.45.
- **Slow honest miners lose about twice what they lose under stock:**
  10.7-14.7 % against 5.0-5.8 % on a 6 s path. The cause is a lateness
  cascade along relay chains, because monerod relays only blocks on the
  relayer's main chain. **The d sweep (item 9) shows a longer d does not fix
  it.**
- **Partial adoption (item 10)** is worse than either end for someone at
  every step tested (alpha 0.30 and 0.45). Stock nodes ban their SoP peers
  for 24 h. Removing the bans (`--sim-no-drop-score`) removes the partition,
  but the attacker then takes 0.991 of the single chain, so the gain comes
  from mixing fork rules. SoP needs a flag day. These networks have 14 nodes;
  the owner wants the ladder rerun on a 256 GB box with larger networks.

**Superseded and retracted docs.** Each of the study's 34 dated docs now
starts with a status line. Superseded:
- `20260923_sop_design.md`
- `20260925_e4_code_data_review.md` (its SoP numbers)
- `20260926_dev_branch_handoff.md`
- `20260926_sop_h10_rerun.md`
- `20260926_exact_uncles_and_sop_controls.md` §2
- `20261007_sop_campaign7_results.md`
- `20261019_sop_campaign8_results.md`
- `20261022_sop_v4_results.md`
- `20261028_mrl_status.md`

The SoP findings 9 and 10 in `20260922_selfish_mining_manuscript.md` are
also superseded. Retractions made earlier are kept in place inside the
manuscript, the SoP design doc and the E4 review, each with a dated note.

**Not stamped:**
- `docs/20261021_research_direction_idea_SoP.txt` is a colleague's note
  relayed by the owner, kept verbatim.
- `review_report.md` is the independent reviewer's report, not written by
  the study.

**`review_report.md`, now at the repository root, belongs to SoP.** It is the
independent review (2026-10-08) of the dev-branch SoP campaign 7, committed
in `70b15966`. Its prompt is `docs/review/20261008_review_prompt.md`. Move
both together, for example to `studies/sop/docs/review/20261008_review_report.md`
and `studies/sop/docs/review/20261008_review_prompt.md`.

## Files

`FILES.md` (next to this file) lists every file, generated from git:
- 455 files are owned by SoP: move them into `studies/sop/`;
- 25 are shared with the simulator: keep them in place;
- no branch change falls outside these two lists.

The SoP-owned files:
- every `scripts/sop_*.py` and its test;
- `scripts/selfish_mining/`;
- `test_configs/matrix/*`;
- `test_configs/*sop*`, `*pop*` and `selfish_*`;
- `data/campaign*`, `data/sop_*`;
- `patches/monero-sim-pop.patch`;
- `gml_processing/1200_nodes_caida_slow_links.gml`;
- `scripts/gml_add_slow_nodes.py`;
- the dated docs above, `docs/assets/sop/`, `docs/review/20261008_review_prompt.md`
  and `review_report.md`.

Main names `test_configs/selfish_micro_sop.yaml` in a help message at
`setup.sh:54`. Update that text after the move.

**Shared files the branch changed, and why:**

- `agents/selfish_miner.py` (8 commits): attacker logging of reveals and
  publishes (`75784b15`), the pool-share count on an empty branch
  (`61969161`), the network-advantage attacker with bridges (`322427b3`),
  and the v3 topologies' seed pinning and hidden bridge (`9010e04e`).
- `agents/selfish_strategy.py` (5 commits): the `param_stubborn` strategy
  (`5c54ce4e`), the `learned` strategy (`d32b00d7`), the RL per-race returns
  (`69bb8d37`), and the `window_rule` 20261020 fix for stock networks
  (`eb070be4`).
- `agents/test_selfish_miner.py`, `agents/test_selfish_strategy.py`: tests
  for the above.
- `scripts/selfish_matrix.py` (2 commits): overlay targets for the
  slow-miner and partial-adoption specs (`96a9aede`), and the tail-emission
  reruns (`7528e5bb`). `scripts/test_selfish_matrix.py` pins every
  twin-spec relationship (45 tests).
- `pyproject.toml`: the pytest marker `slow` (`596de7c5`).
- `.gitignore`: `mdp_out/`, the solver's output directory, whose policy
  dumps run to 2 GB (`c8d9366a`).

Main loads the selfish-mining agents from Rust and from its golden fixtures
(`src/config/agent_config.rs`, `src/utils/mining.rs`,
`tests/fixtures/selfish*.yaml`, `tests/orchestrator_selfish.rs`). So the
agents stay where they are, and main's selfish golden tests must run after
the merge (see the checks below).

**Shared with another study: none.** Antiproxy's `feat/spy-relay-log`
touches none of the branch's files. `hashrate-gating` and `progress-brief`
have unrelated histories, each holding only a README.

**Material that was outside git, now copied here** (copied, not moved; the
originals stay):

| cited as | copy in this folder |
|---|---|
| `.claude/...` (`remote_test.sh` 19 times, `HANDOFF.md`, campaign5-9 scripts, queues, logs, notes, review prompt) | `dot-claude/...`, same structure |
| `~/monerosim_rl/data`, the `*_remote.sh` launchers | `home/lithium/monerosim_rl/`, `home/phantom/monerosim_rl/` |
| lithium `~/mdpcheck`: solver cross-check runner, results, logs | `home/lithium/mdpcheck/` |
| lithium `~/monerosim/mdp_out/*.log`: the exact-MDP solve logs | `home/lithium/mdp_out/` |
| `~/.monerosim/bin/monerod-sim.provenance`, every machine | `home/provenance/` |
| `~/simbin_build.log`: the 10-30 rebuilds | `home/{lithium,phantom}/simbin_build.log` |

`dot-claude/HANDOFF.md` is the operational handoff of 10-31 / 11-01: rules,
results, queues and pitfalls. `dot-claude/HANDOFF_20261021_pre_v4.md` and
`_20261023_pre_o5.md` are the earlier ones.

`.claude/worktrees/v0.3.1` is cited twice but no longer exists. It was a git
worktree of the v0.3.1 tag, recoverable with `git worktree add <dir> v0.3.1`.

**Left out:**
- the 16 MB ELF `.claude/campaign7/bin/monerod-sim.pre-stale-fix`; its
  provenance is in `home/provenance/`;
- `__pycache__`;
- the `~/mdpcheck` venv;
- my local copies of the SSZ paper (copyrighted; cite arXiv 1507.06183);
- the MDP policy dumps (`policy_*.json`, 2.2 GB and 208 MB);
- the rsync copies of repo code inside `~/monerosim_rl`;
- the run archives in the research pool (result docs cite them by run
  directory);
- the owner's stressnet node logs and the parsed tables derived from them
  (doc item 8 gives the statistics).

**Redacted in the copies** (7 files):
- real LAN IPs, now `<boxNN-lan-ip>`, `<tr-lan-ip>`, `<phantom-lan-ip>`,
  `<lithium-lan-ip>` and `<mainnet-node-lan-ip>`;
- the internal hostnames behind box80-82, tr and the control box, now
  `box8N-host`, `tr-host` and `control-box`;
- the stressnet monitoring hub's name and the path of its sidecar config,
  which holds a token.

No keys, tokens or passwords were found. The control box's untracked
`CLAUDE.local.md` maps the placeholders back.

## Daemon

Base: monero `v0.18.5.1` (`monero.pin`).

Patches, in apply order (`setup.sh --sim-binary`, or
`dot-claude/campaign9/simbin_build.sh`), with sha256 at the tip of
`sop-research`:

| # | patch | sha256 |
|---|---|---|
| 1 | `patches/monero-fakechain-hardforks.patch` | `732924a33a90978d3236758dbbb1e971bda69bbb51c3079a9489d24644d842fa` |
| 2 | `patches/monero-sim-mining.patch` | `b25b83ccc9ed0acc3b422112b073cf0742442efe8a06b254bf6dab9f455dab79` |
| 3 | `patches/monero-sim-selfish-relay.patch` | `4d4c86d6044eac36c32a06a0929a3c21db5e08d13e8ee6f952186d7b300d9dca` |
| 4 | `patches/monero-sim-peerlist-dump.patch` | `b99de1927045e48a29ff90bb1e594f17e1e3d639bb389a1ddca2b9fef11549b1` |
| 5 | `patches/monero-sim-pop.patch` | `3f321bdede8fe8c50ff70c7f186fa9749d86a63df02aa25d35eed799628ce464` (`df22d181`, the 10-30 nodrop build) |
| 6 | `patches/monero-sim-tail-emission.patch` | `5a6e3937f0b56abf36a3be2747c66cee4b7195e049f7e88ddfffc53214e0767e` |

Patches 1-4 and 6 are the same on main. Only `monero-sim-pop.patch` (the
PoP/SoP patch) differs between builds:

| pop version | sha256 | commit | built into |
|---|---|---|---|
| v4 slot fix | `1a6d7b3527fe3366d548df267e1af1184a8b7a1160c569e02fb8758ac5794c68` | `d8cc1d45` (2026-10-21, also on main) | box80, box81, box82 (2026-10-24); tr/lever65 (2026-10-21) |
| first-seen knob only | `e220d3199e302a26...` | `facf47d5` (2026-10-30) | lithium's intermediate build, kept as `monerod-sim.pre-nodrop`. Only the knob smoke used it. |
| **nodrop build** | `3f321bdede8fe8c50ff70c7f186fa9749d86a63df02aa25d35eed799628ce464` | `df22d181` (2026-10-30) | **lithium and phantom, 2026-10-30 19:39Z**. It adds `--sim-sop-seen-at-notify` (stamp first-seen in the P2P fluffy-block handler) and `--sim-no-drop-score` (a stock node skips `hit_score`'s height-drop penalty). |

**The 10-30 nodrop build.** On 2026-10-30, `dot-claude/campaign9/simbin_build.sh`
was run on lithium and phantom. It re-applied the six patches above to the
pinned ref in `~/.monerosim/build/monero-sim`, ran `make daemon`, and
installed by rename. It installs only `monerod-sim`; `monerod` and
`monero-wallet-rpc` stay as they were. The patch itself was regenerated
in a lithium worktree (`~/.monerosim/build/monero-knob`): the pin, with
patches 1-4 and the old pop patch committed as "pre-pop", plus the two
edits applied, then `git diff <pre-pop>`. The edit and build scripts (scratch
files at the time) are in `home/lithium/monero-knob/`: `knob_edit.py`,
`nodrop_edit.py`, `knob_build*.sh`, `nodrop_build.sh`, `lithium_build.sh`.

Both boxes produced the same binary, sha256
`c11b5a99eeb040f23c08e0121f4e12de3a19e2372469b1351d96b89c4bbb8c16`. The
build logs are `home/{lithium,phantom}/simbin_build.log`. Specs that use
either new flag run only there: `sop_knob_smoke`, `sop_v4_adopt_nodrop_72h`.

**Provenance, verbatim** (`~/.monerosim/bin/monerod-sim.provenance`; copies
in `home/provenance/`). All accounts are `selfishmining` unless marked.

box80, box81 and box82 are identical except the build time (box80
`05:40:14Z`, box81 `05:41:14Z`, box82 `05:41:15Z`):

```
binary: monerod-sim (alias: monerod-hf)
base: v0.18.5.1 (monero.pin)
patch: patches/monero-fakechain-hardforks.patch
patch_sha256: 732924a33a90978d3236758dbbb1e971bda69bbb51c3079a9489d24644d842fa
patch: patches/monero-sim-mining.patch
patch_sha256: b25b83ccc9ed0acc3b422112b073cf0742442efe8a06b254bf6dab9f455dab79
patch: patches/monero-sim-selfish-relay.patch
patch_sha256: 4d4c86d6044eac36c32a06a0929a3c21db5e08d13e8ee6f952186d7b300d9dca
patch: patches/monero-sim-peerlist-dump.patch
patch_sha256: b99de1927045e48a29ff90bb1e594f17e1e3d639bb389a1ddca2b9fef11549b1
patch: patches/monero-sim-pop.patch
patch_sha256: 1a6d7b3527fe3366d548df267e1af1184a8b7a1160c569e02fb8758ac5794c68
patch: patches/monero-sim-tail-emission.patch
patch_sha256: 5a6e3937f0b56abf36a3be2747c66cee4b7195e049f7e88ddfffc53214e0767e
built: 2026-10-24T05:40:14Z
```

lithium (`19:39:13Z`) and phantom (`19:39:53Z`), identical except the build
time:

```
binary: /home/selfishmining/.monerosim/bin/monerod-sim
base: v0.18.5.1 (monero.pin)
patch: patches/monero-fakechain-hardforks.patch
patch_sha256: 732924a33a90978d3236758dbbb1e971bda69bbb51c3079a9489d24644d842fa
patch: patches/monero-sim-mining.patch
patch_sha256: b25b83ccc9ed0acc3b422112b073cf0742442efe8a06b254bf6dab9f455dab79
patch: patches/monero-sim-selfish-relay.patch
patch_sha256: 4d4c86d6044eac36c32a06a0929a3c21db5e08d13e8ee6f952186d7b300d9dca
patch: patches/monero-sim-peerlist-dump.patch
patch_sha256: b99de1927045e48a29ff90bb1e594f17e1e3d639bb389a1ddca2b9fef11549b1
patch: patches/monero-sim-pop.patch
patch_sha256: 3f321bdede8fe8c50ff70c7f186fa9749d86a63df02aa25d35eed799628ce464
patch: patches/monero-sim-tail-emission.patch
patch_sha256: 5a6e3937f0b56abf36a3be2747c66cee4b7195e049f7e88ddfffc53214e0767e
built: 2026-10-30T19:39:13Z
builder: simbin_build.sh (setup.sh steps, sim binary only)
```

tr, account `lever65` (the owner's account, where the antiproxy study runs).
SoP runs no daemons there; it is only the pool host and push relay. Build
time 2026-10-21T19:27:40Z, same patches as box80-82 (pop `1a6d7b35...`).

Binary sha256s are in `home/provenance/binary_sha256.txt`. The 10-24
`monerod-sim` builds differ between boxes although their provenance matches:
box80 and box82 have `b4c820c7...`, while box81, phantom's `pre-nodrop` and
lithium's `pre-knob` have `f8a82553...`. Their stock `monerod` differs the
same way, so this is a toolchain difference, not a source one. Campaign 7's
pre-stale-fix daemon provenance is in
`home/provenance/campaign7-pre-stale-fix.monerod-sim.provenance`.

**Accounts.**
- `selfishmining` on box80-82, phantom, lithium and the control box is used
  only by SoP, as far as I know.
- phantom and lithium also run the owner's Monero stressnet nodes under the
  account `monero`; never touch them.
- lithium has the owner's `lever65` account, with archives in
  `/home/lever65/monerosim_archives`; never move them.

## Running and queued work

**None.** The fleet drained at 2026-11-01 06:21Z. All queues are empty and
every queue runner, watcher and memory guard is stopped. Nothing of SoP's
runs on any machine.

Where things live for the next run:

| machine | account | checkout | commit | notes |
|---|---|---|---|---|
| control box | selfishmining | `/home/selfishmining/monerosim` | `sop-research` (this branch) | runs only the Claude instances; `.claude/` (git-ignored) is the live original of `dot-claude/` |
| box80, box81, box82, phantom, lithium | selfishmining | `~/monerosim` | git HEAD stale (old main commits plus modified files) | content rsync'ed from the control box by `sync_tree.sh`, so HEAD does not describe the code; each run's `binary_provenance.txt` and `dot-claude/campaign9/queues/*.log` record the control-box commit |
| lithium, phantom (box80 partly) | selfishmining | `~/monerosim_rl` | not git | scratch copy for `remote_test.sh` |
| lithium | selfishmining | `~/mdpcheck` | not git | venv with numpy 2.5.4, scipy 1.18.1, pymdptoolbox 4.0b3, pytest; the cross-check scripts |

Run archives go to the research pool on tr:
`/spinny/readfrom/20261024_monerosim_research_effort/<host>/archived_runs/`.
The control box mounts it over NFS at `/mnt/remote_spinny/20261024_monerosim_research_effort`.
Result docs cite run directories there.

**Repo paths the scripts and specs hard-code.** Update these after the move.
- `dot-claude/campaign9/*`:
  - the checkout and its venv: `/home/selfishmining/monerosim`, `venv/bin/python`;
  - code: `scripts/selfish_matrix.py`, `scripts/selfish_mining/sop_stuck_time.py`,
    `agents/selfish_miner.py` (`rerun_cell.sh` checks for `_fork_header`);
  - specs and outputs: `test_configs/matrix/<spec>.yaml`,
    `matrix_runs/<spec>/{cells,configs,table.md}`, `archived_runs/`;
  - the daemon build: `patches/`, `monero.pin`;
  - the RL data: `data/sop_rl`;
  - the campaign directory's own files: `.claude/campaign9/{queues/,HALT,GO,queue.log,*.matrix.out}`;
  - `remote_test.sh` rsyncs `scripts agents test_configs src pytest.ini conftest.py pyproject.toml tests patches monero.pin analysis/eclipse chain_snapshots/h10/manifest.json data/sop_rl`;
  - `sync_tree.sh` copies `agents/ scripts/ test_configs/ gml_processing/`.
- Specs (`test_configs/matrix/sop_*.yaml`) name:
  - their base configs: `test_configs/selfish_micro_sop.yaml` (47 times),
    `selfish_n40_sop.yaml`, `selfish_micro_sop_h4.yaml`,
    `selfish_micro_sop_tail.yaml`, `selfish_micro_sop_slow.yaml`,
    `selfish_micro_sop_gamma.yaml`, `selfish_micro_sop_scale{300,1000}.yaml`;
  - `chain_snapshots/h10`;
  - `gml_processing/1200_nodes_caida_with_loops.gml` and
    `gml_processing/1200_nodes_caida_slow_links.gml`;
  - `scripts/make_sop_scale_base.py`, `scripts/sop_oracle.py`;
  - `data/campaign8/analysis_out/modelb_sweep_hs_*`,
    `data/sop_search/kw_perish_047.jsonl`, `data/sop_rl/policy_noown_a045.json.gz`;
  - `agents/selfish_miner.py`.
- Scripts: `scripts/sop_attacker_search.py` writes `data/sop_search/`, and
  `scripts/sop_rl.py` reads and writes `data/sop_rl/`.
- `scripts/test_selfish_matrix.py` loads specs by `test_configs/matrix/` name.

## Checks after the move

1. **Python tests on a lane box** (run on lithium, 2026-11-01):
   `remote_test.sh <box> -q scripts/test_selfish_matrix.py scripts/test_sop_*.py agents/test_selfish_miner.py agents/test_selfish_strategy.py scripts/test_gml_add_slow_nodes.py`.
   Expected: `379 passed, 1 skipped`, 52 min on lithium (2026-11-01). The skip is `test_sop_mdp_crosscheck.py`, which needs scipy.
2. **Solver cross-check tests** (need scipy and pymdptoolbox: lithium
   `~/mdpcheck/venv`): `python -m pytest -q scripts/test_sop_mdp_crosscheck.py`.
   Expected: `5 passed`, 51 s on lithium (2026-11-01). In the repo venv they skip.
3. **Cross-check, a few minutes:**
   `scripts/sop_mdp_crosscheck.py btc --alpha 0.35 --gamma 0 --T 95 --T-policy 0`.
   Expected: `hand_written`, `toolbox_rvi` and `highs_lp` all 0.370774
   (SSZ Table 2: 0.37077).
4. **Main's Rust tests after the merge.** The branch changed the
   selfish-mining agents that main's fixtures load. Run `cargo test`,
   especially `tests/orchestrator_selfish.rs`, `tests/orchestrator_selfish_eclipse.rs`
   and the `tests/golden/selfish.yaml` golden. Not run on the branch: the
   control box runs no compute, and the merge has not happened.
5. **Shadow smoke** (2 cells, 3 simulated hours; wall time not measured,
   my estimate is under an hour; needs the 10-30 daemon, so lithium or
   phantom):
   `venv/bin/python scripts/selfish_matrix.py test_configs/matrix/sop_knob_smoke.yaml`.
   Expected:
   - both cells complete with health ok;
   - every SoP daemon logs `SIM-SoP: weight table armed (w=16 delay_ms=5000 k=3 mode=whole_branch)`;
   - the notify cell logs `first-seen stamped at P2P notification` at start
     and `first seen at notify` for received blocks (1,055 on 2026-10-30);
   - no exceptions.

   `dot-claude/campaign9/analysis/knob_gate.sh <cell>` prints these.
   The spec's original gate 3 (identical chains in both cells) is invalid:
   Shadow runs are not bit-reproducible.

   For a box without the 10-30 daemon, run a short cell of any `sop_v4_*`
   spec instead. Expect the same "weight table armed" line and
   `check_run.py` PASS or WARN.

**Configs in active use** (the last campaigns, 2026-10-30 to 11-01):
- `test_configs/matrix/sop_v4_{dsweep_gamma,dsweep_param,dsweep_slow,seed2_adopt,seed2_gamma,seed2_slow,adopt,adopt_lowalpha,adopt_nodrop}_72h.yaml`;
- their d = 5 twins `sop_v4_{slow,gamma,param}_72h.yaml`;
- `sop_knob_smoke.yaml`;
- the bases `test_configs/selfish_micro_sop.yaml`, `selfish_micro_sop_slow.yaml`
  and `selfish_micro_sop_gamma.yaml`;
- `gml_processing/1200_nodes_caida_slow_links.gml`, `chain_snapshots/h10`.

## Known problems

**Fixes only on this branch:**
- the attacker counts its pool shares on an empty branch (`61969161`);
- the `window_rule` 20261020 fix (`eb070be4`);
- the two daemon flags (`facf47d5`, `df22d181`);
- the race-model counting changes (`b9242908`, `316bb786`);
- the matrix-runner overlays (`96a9aede`).

box80-82 still run the 10-24 daemon, without the two flags. Rebuild them with
`simbin_build.sh` between cells, never beside a running cell: they have
1-3 GiB free while running.

**Fixes on main this branch lacks:**
- `4fe1459a` "fix(placement): honour topology_node on script-only agents".
  Not checked: whether any SoP spec places a script-only agent with
  `topology_node`. If one does, placement after the merge can differ from
  every run so far. Diff one spec's generated Shadow config before and after
  the merge.
- `44c8cf78`, release v0.4.0 ("faster, leaner and larger runs; native
  mining"): rerun the smoke above after the merge.
- `8220ba97`, `b9c69d54`, `9d300222`: tests and baselines only.

**Docs:**
- `docs/20261028_mrl_status.md` line 11 says the exact MDP solver "neither
  beat the family". That overstates it: capped solves are lower bounds. Its
  status line says so; the text is unchanged.
- The SSZ upper-bound column is not reproduced (item 11).

**Statistical limits:**
- The d-sweep cells are one seed each, and the attacker-side ones are inside
  the d = 5 seed spread.
- The adoption cells are 14-node networks.
- The lateness-cascade mechanism is shown in the fork-decision logs, but how
  often real Monero nodes sit behind a run of such relays is not measured.

**Half-finished:** nothing is in flight. Decisions open with the owner:
- the large-network adoption ladder and 5/5 MDP caps on a 256 GB box;
- a block-granular MDP for a tight bound;
- a relay-fix experiment: forward competing tip blocks whatever the local
  fork choice;
- the attacker agent's tie reaction (polling to block notifications);
- a transaction-load cell for the first-seen knob;
- multi-node arrival data from the stressnet monitoring hub.

**Owner's pause.** Since 2026-10-31 the owner has asked for no new
experiments until the reorganisation lands. The control box's memory and
`dot-claude/HANDOFF.md` record this.
