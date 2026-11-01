# HANDOFF — SoP mitigation case (written 2026-10-31 02:25Z)

Branch `sop-research`, HEAD e95d6716, tree clean. 46 commits since
origin/sop-research (b0376d4c) are unpushed; pushes need the owner's go-ahead
each time (via `.claude/campaign9/push_files.sh` or its two git push lines,
through tr's checkout). All results are in docs/20261026_sop_attacker_search.md
("The mitigation case (2026-10-28)" and the subsections after it).

## STATUS 2026-11-01 06:30Z (read first)

- Fleet DRAINED. The last cell synced at 06:21Z. No lanes, queue runners,
  watchers or memguard are running, and every box is idle (checked).
- The owner asked (10-31 ~11:30Z) to drain and then reorganize the git
  repo. Add NO experiments until the owner says the reorganization is done
  (memory: queue-drain-before-repo-reorg).
- All results are written up in docs/20261026_sop_attacker_search.md,
  sections 9-11, through commit 1a6614cb:
  - d sweep: a longer d does not undo SoP's slow-miner cost (a lateness
    cascade along relay chains).
  - Adoption: the nodrop cell has no split but the attacker takes 0.991, so
    the gain comes from the mixed fork rules and SoP needs a flag day.
  - Solver cross-check: matches pymdptoolbox, HiGHS and SSZ's Table 2.
- Pushed 11-01 with the owner's go-ahead: origin/sop-research = 1a6614cb,
  0 unpushed, working tree clean.
- After the reorganization: the .claude/campaign9 scripts (git-ignored)
  hard-code scripts/, test_configs/matrix/ and docs/ paths, and the lane
  boxes hold their own tree copies (~/monerosim). Check both and re-sync
  before any run.
- The cross-check venv lives outside the repo, at lithium:~/mdpcheck
  (numpy, scipy, pymdptoolbox, pytest).
- Everything below this block predates the drain (10-31 02:25Z).

## Standing rules (owner)

- Control box control-box runs ONLY the Claude instances: no sims, solves, test
  suites or Monte Carlo. Log parsing / scoring from the pool is fine (precedent).
  Tests run on lithium (`sync_tree.sh lithium` first).
- phantom (.22) and lithium (.25) run the owner's testnet stressnet nodes (user
  `monero`): keep >= 8 GiB free (memguard_lanes.sh), one 72 h lane each, phantom
  never more than 2 lanes. Never modify /home/lever65, the monero user's files or
  services, or the protected archives. Reading the stressnet logs read-only via
  `sudo -n` is authorized (owner 10-30); never read/use <sidecar config file, holds a hub token, never read>.
- Kill by pid with anchored patterns; never `pkill -f` broad patterns.
- tr (.33) is the antiproxy agent's: no runs; pool host and push relay only.
- Owner is on US Eastern: quote UTC with EDT beside it.
- Keep the fleet busy with the next logical experiment and report it.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Results (one seed per cell unless stated)

1. No-attacker control: SoP costs honest revenue/orphans nothing; tip churn 30-60
   switches / 72 h vs 0-2.
2. Honest fragmentation: crossing 0.4635 with two miners, 0.450 with four
   (0.395 / 0.449 / 0.549 at 0.44 / 0.45 / 0.47).
3. Slow honest miner (no attacker), blocks lost by the slow miner, stock / SoP:
   3 s 4.4 / 2.6 %, 6 s 5.0 / 10.7 %, 12 s 13.9 / 25.9 %. A cliff at d = 5 s,
   then about twice the stock loss, all on the slow miner.
4. Network-advantage attacker (bridges beside both miners), SoP 3 s / 6 s path:
   0.35: 0.175 / 0.209; 0.40: 0.246 / 0.385; 0.45: 0.486 / 0.699 (base 0.44).
   Mechanism = lateness rule (verified from logs). Stock tie-racer (SM1): 0.303
   (0.30, 6 s), 0.363 / 0.338 (0.35), 0.671 / 0.649 (0.45) — but our SM1 answers
   ties ~5 s after the honest find (daemon-log analysis), so use the SM1 formula
   at gamma 0.5 as the stock reference (0.416 / 0.526 / 0.681). Past d SoP still
   beats stock by 0.15-0.2 below 0.45 and ties it at 0.45. The audit's reveals /
   gamma columns read 0 for SM1 cells (they parse param_stubborn lines only).
5. Partial adoption: no split without an attacker. With the attacker at 0.45
   worse than either rule: 25 % ~0.88 of all blocks (SoP side 0.906, stock
   0.858), 50 % SoP side 0.998 / stock 0.836, 75 % 0.883 / 0.755. Mechanism
   (logs): stock nodes block SoP peers for 24 h via monerod's height-drop peer
   scoring (the patch exempts SoP nodes only) -> "daily resync bursts". Flag day
   needed for every node incl. relays. Open: lower alpha, bigger networks (owner:
   adoption belongs on the 256 GB box), the nodrop mechanism cell (queued).
6. Upper bound (over-paying MDP): 0.8036 at 3/3 caps, 0.7265 at 4/4 (alpha 0.45);
   lower bound 0.45. 5/5 needs ~120 GB. Tight bound = block-granular abstraction.
7. Tail emission: CLOSED, 8/8 reruns inside their stock-emission seed spread.
8. Stressnet propagation (phantom + lithium testnet logs, 10-19..10-30, 8,432
   live blocks): inter-node gap median 25 ms, p99 0.95 s; processing <= 113 ms
   even at 1.7 MB; 0.06 % of blocks > 5 s apart outside one stall / one burst.
   Lower bound only (two LAN neighbours). The stressnet-monitor sidecar hub holds multi-node
   arrival times (ask the hub operator; owner's call).
Knobs built: `--sim-sop-seen-at-notify` (first-seen at fluffy receipt; smoke
passed, changes nothing without tx load) and `--sim-no-drop-score` (stock node
skips height-drop scoring). Both in patches/monero-sim-pop.patch.

## In flight (02:23Z 10-31)

| box | running | progress | queue after it |
|---|---|---|---|
| box80 | dsweep_gamma share_sop_d10_a045_f6_s1 | 51 % | dsweep_slow honest_sop_d20_a047_l6_s1, seed2_gamma share_sop_a045_f6_s2, seed2_slow honest_stock_a047_l6_s2 |
| box81 | dsweep_slow honest_sop_d10_a047_l6_s1 (avail 1 GiB) | 55 % | dsweep_slow honest_sop_d20_a047_l12_s1, seed2_slow honest_sop_a047_l6_s2 |
| box82 | dsweep_gamma share_sop_d20_a045_f6_s1 | 54 % | dsweep_slow honest_sop_d10_a047_l12_s1, seed2_gamma share_sop_a045_f3_s2 |
| phantom | dsweep_param share_sop2_param_d20_a047_s1 | 87 % | dsweep_param d20_a045, adopt_lowalpha share_k2_a030_s1, seed2_adopt share_k2_a045_s2 |
| lithium | dsweep_param share_sop2_param_d10_a047_s1 | 48 % | dsweep_param d10_a045, adopt_lowalpha share_k1_a030_s1, adopt_nodrop share_k2_nodrop_a045_s1, seed2_adopt share_k1_a045_s2, adopt_lowalpha d2_k0_a030_s1 |

Queue runners: `.claude/campaign9/chain_queue.sh <box>` (background, started
10-30 19:31Z, run 72 h) pop `.claude/campaign9/queues/<box>.txt` whenever the
box has no lane, launch via rerun_cell.sh, and for slow / gamma / dsweep cells
run check_paths at 25 min into `queues/<box>.paths.log`. Logs `queues/<box>.log`.
Append lines to add work. If the session restarts the runners are gone: restart
them (one per box, `run_in_background`). Each box also had a watch_lane_sync.sh
watcher; memguard_lanes.sh "lithium phantom" 8 80 runs (restart it if it exits).

Binaries: lithium and phantom monerod-sim have both new flags (built 10-30
19:39Z by simbin_build.sh); box80/81/82 run the 10-24 binary (neither flag), so
knob / nodrop cells go to lithium / phantom only.

## Next steps

1. As each cell syncs: score (`score_pool.sh <spec>`), write it into the doc,
   commit. Slow-miner cells: per-miner loss via analysis/slow_loss.py (globs
   sop_v4_slow_72h runs; extend the glob to sop_v4_dsweep_slow_72h and
   sop_v4_seed2_slow_72h). Adoption cells: per-side shares via analysis/
   split_shares3.py (add the run dir). Check paths.log for each launched
   slow / gamma cell.
2. d sweep expectations: slow l6 at d10 and both latencies at d20 should look
   like l3 at d5 (2.6 %); gamma f6 at d10 / d20 should fall toward 0.486; param
   a045 / a047 at d10 / d20 (d5: 0.431 / 0.451) show what a larger d gives away.
   Write "the d sweep" as a doc subsection when the 10 cells are in.
3. nodrop cell: at 25 min, check that its stock daemons log "SIM: peer height
   drops not scored" (lithium); then whether the split disappears.

## Verified vs assumed

- Verified by test: 45 tests in scripts/test_selfish_matrix.py (run on lithium):
  every new spec is pinned to its twin (dsweep: only sim-sop-delay-s on exactly
  the SoP daemons; seed2: only the sample attribute; lowalpha: only hashrates;
  nodrop: only the flag on the six stock daemons + relay-002 on monerod-sim).
- Verified by generator run: --sim-sop-delay-s=10 reaches all 16 SoP daemons of a
  dsweep gamma cell and no other daemon.
- Verified by smoke: the seen-at-notify stamp lands on the receipt millisecond.
- Not verified: the nodrop flag in a run (first use is the queued cell); the
  cause of SM1's ~5 s tie reaction (suspect agent polling over the 0.5 s link).
- Two runs of one config are NOT replays (10 ms divergence from the first block):
  compare by seed spread or mechanism, never block for block.

## Rejected approaches / pitfalls (do not redo)

- Gamma v1 / v2 topologies (single edges > 5 s RTT never connect: monerod's 5 s
  P2P timeouts); slow paths are chains of 1.5 s hops. Eclipsed hosts need
  priority seeds. Bridges need feed_parents. Wallet logs at ERROR.
- Solves or the full test suite beside a lane on lithium (memguard killed a lane).
- `setup.sh --sim-binary` beside running lanes: step 7 dies on "Text file busy";
  use `.claude/campaign9/simbin_build.sh` (sim binary only, install by rename).
- Inline `ssh box '...pgrep -f "[s]etup..."'` self-matches; use script files.
- The pool host dropped rsync 10-30 16:35-17:00Z; runs stay local. Re-sync from
  the originating box: analysis/resync.sh (calls run_lane.sync_run).
- Watchers only notify; boxes idled 3-7 h when the session stalled -> the
  queue runners. On resume, check every box (analysis/fleet_state.sh) first.
- The frugal hook blocks a 6th inline read per prompt; delegate reads to an
  extractor agent (it resets after the agent completes).

## Open for the owner

- Push the 46 commits.
- Multi-node propagation data from the stressnet monitoring hub (hub operator).
- A transaction-load cell for the seen-at-notify knob (needs a tx-generating cell
  design and box rebuilds).
- Fixing the attacker agent's tie reaction (block notifications instead of polling).
- Upper bound: block-granular abstraction (days) or 5/5 caps on the 256 GB box.
- N = 8 honest miners and the large-network adoption ladder (256 GB box setup).

## Helpers (.claude/campaign9/, git-ignored; scratchpad = this session's)

rerun_cell.sh, chain_queue.sh + queues/, watch_lane_sync.sh, memguard_lanes.sh,
score_pool.sh, check_paths.sh, simbin_build.sh, sync_tree.sh, push_files.sh.
Analysis helpers copied to `.claude/campaign9/analysis/`: fleet_state.sh (every
box at a glance), slow_loss.py (per-miner found/kept; edit its glob), split_shares3.py
(per-side shares; edit RUNS), tie_steer.py (tie reaction / steering), resync.sh
(re-sync one run from its box), stressnet_parse.py / stressnet_run.sh /
stressnet_stats.py (stressnet logs), knob_gate.sh. Paths inside some still point at
the old scratchpad; adjust when reused.
Pool: /mnt/remote_spinny/20261024_monerosim_research_effort/<host>/archived_runs
(box80 = box80-host, box81 = box81-host, box82 = box82-host, phantom, lithium).
