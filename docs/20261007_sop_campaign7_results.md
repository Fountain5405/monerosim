# Share-or-Perish (MRL #146) on the corrected simulator: campaign 7 results (2026-09-30 to 2026-10-07)

**Status: DRAFT, 2026-10-07.** Sections 1–5 and 7–9 report finished,
checked runs. Section 6 (the P2P ban cascade) reports a verified mechanism.
Its fix is committed (`002cd40c`), but the runs that test it
(`stubborn_h10_banfix{,_rep,_rep2}`) end about 2026-10-08 10:00–11:00 UTC,
so §6.4 is still open. Nothing here has been reported outside this
repository. Whether and what to report on MRL #146 is the owner's decision.

## Summary

| # | Result | Confidence |
|---|---|---|
| 1 | SoP defeats the spec's own stubborn attacker at α ≤ 0.45: it earns less than its hashrate share in every cell. At α = 0.33 its share falls from 0.30 (stock) to about 0.02. The margin shrinks with α: 0.11–0.19 at α = 0.40 and 0.37 at α = 0.45. | High at α = 0.33 (13 runs of 240 h). Moderate at 0.30/0.40/0.45 (6 h, n = 3). |
| 2 | An independent race model (Model B) reproduces the simulator: attacker share, reveal rate, orphan rates, race shapes and, once replicated, reorg depth. | High for this attacker and topology. |
| 3 | Reorgs of 10+ blocks depend on how long the attacker holds on. At α = 0.33 (Model B): 1 per 2.9 canonical years at give-up depth 2, 1 per 1.5 at depth 3, and 1 per 5 months at depth 5. The spec's "about 1 per 3 years" holds only at depth 2. | Moderate–high (model, validated against the simulator at shallower depths). |
| 4 | **P2P ban cascade.** A SoP node legitimately switches to a branch with fewer blocks. Stock monero scores a peer down for that height drop and bans it for 24 h once its never-decaying fail score passes 10. Honest nodes banned each other in 3 of 5 depth-5 runs. | High for the mechanism (67 of 67 bans replayed exactly). The fix is committed; its check is pending (§6.4). |
| 5 | Spec gaps: (a) which chains are compared after a reorg is unspecified, and the two readings give very different attacker revenue; (b) as implemented, unmodified v0.18 nodes reject share-carrying blocks; (c) the per-time claims assume a fixed block rate; (d) the 10+ reorg claim assumes give-up depth 2. | High for (a), (c), (d). (b) depends on an encoding the spec does not define (§7.2). |

Every SoP number recorded before 2026-10-04 is superseded (§1), including
manuscript finding 10 as it stood and the "SoP lost both ES cells" result
of `docs/20260926_exact_uncles_and_sop_controls.md` §6. The manuscript is
corrected in the same commit as this draft.

## 1. Why earlier SoP numbers are superseded

1. **The simulator deviated from the spec in four ways** (audit of
   2026-09-30 against the text of MRL #146; corrected in `0b9e8089`; rules
   and conventions in `docs/20260930_sop_conformance.md`):
   - Past the k·w = 48-object window, the fallback compared plain
     cumulative difficulty. The spec keeps its share-counted weight there:
     a recent block weighs `diff/w · (1 + its workshares)`.
   - Blocks carried only their own miner's shares. The spec has every
     block carry the published shares it knows.
   - Lateness was measured against the wrong reference time.
   - Blocks displaced by a reorg were re-judged one at a time, not as a
     whole branch.

   Every SoP fork decision now logs a `SIM-SoP-DEC` record, and
   `scripts/sop_oracle.py check` re-derives each one from the spec.
2. **A miner bug stored some blocks under a share's id** (fixed in
   `e2955754`, 2026-10-03). The share log cached the share's hash in the
   mining block object and nothing cleared it when the nonce changed. A
   block found before the next template refresh was stored locally under
   the share's id while peers hashed the true one. The node then saw its
   own block return as a tie with itself, broken by a random draw. One
   pre-fix 240 h run split the network for good. Every SoP run before
   2026-10-04 was affected. A stress smoke (`stale_id_stress`, one
   8-of-10 h/s miner, w = 64) went from 6 stale ids and 62 % orphaning of
   the dominant miner to 0 and 0 %. The health check now flags stale ids,
   lasting chain splits, invalid chains and agent crashes (`516b68fe`,
   `e4905a2b`). `scripts/test_monero_sim_patch.py` pins the fix.
3. **Consequence.** The earlier "SoP lost both ES cells, {0.405, 0.495},
   past its fail-safe window" (results doc 2026-09-26 §6) is an artifact
   of the plain-difficulty fallback. Under the spec's weight, an attacker
   that embeds no shares weighs one unit per block against about 16 per
   honest block, so it cannot win past the window either. The corrected
   simulator measures 0.000 for the same attacker (§8). The pre-fix SoP
   rows of campaign 7 itself are kept in `.claude/campaign7/pre_stale_fix/`
   for the record and are not used below.

## 2. Setup

- **Topology** (`test_configs/selfish_micro_sop.yaml`): 12 daemons on the
  1200-node CAIDA graph. The attacker's offline miner plus its bridge, two
  honest miners, two relays and six declared seeds, plus a monitor host.
  Total hashrate 10 h/s: the attacker 10·α, the honest miners split the
  rest equally. Chain snapshot `h10` (994 preloaded blocks, real LWMA from
  block one). Native RandomX mining; block target 120 s.
- **SoP:** `monerod-sim --sim-share-or-perish`, w = 16, k = 3, d = 5 s,
  whole-branch comparison. All honest miners, relays, seeds and the
  bridge are flagged.
- **Attacker** (`window_stubborn`, `agents/selfish_strategy.py`). It
  withholds; it reveals once its branch holds at least 48 work objects
  AND outweighs honest; it gives up once honest leads by the give-up depth
  d. It is rejection-aware (it concedes a reveal the bridge rejects). The
  "share" arm embeds its own shares; the "block" arm embeds none.
- **Runs.** Every cell was checked with re-scored health (0 stale ids, 0
  splits, 0 invalid chains, 0 agent tracebacks in every run below, except
  one invalid chain noted in §6), the oracle (0 mismatches in every run)
  and the flip-back scan (0 undone switches outside the rejudge cells).

| matrices | cells | length, n | binary / Shadow | run dirs |
|---|---|---|---|---|
| `stubborn_h10{,_rep,_rep2}` | share/block × stock/sop2 × α 0.30–0.45 × d1–d3 | 6 h, n = 3 | fixed (pop `2d6499a8`) / v0.2.4; the first two draws' stock rows ran 2026-09-30 | `20261004_*`, `20260930_*` |
| `stubborn_h10_long{,_rep,_rep2}` | share_sop2 and block_stock, α 0.33, d2 | 240 h, n = 3 | same | `20261004_155751_*`, `20260930_190000_*` |
| `stubborn_h10_long_depth{,_rep}` | share_sop2 α 0.33 at d3, d5 | 240 h, n = 2 | same | `20261004_155751_*` |
| `stubborn_h10_banlog{,_rep,_rep2}` | the d5 cell + net.cn:DEBUG | 240 h, n = 3 | same | `20261006_033956_*` |
| `stubborn_h10_rejudge{,_rep}`, `pop_sop2_h10_fixed{,_rep}`, `sop2_h10_honest{,_rep}` | controls (§8) | 6 h, n = 2 | same | `20261004_111002_*` |
| `stubborn_h10_banfix{,_rep,_rep2}` | the banlog cells on the §6 fix | 240 h, n = 3 | pop `a51b85b0` / **v0.2.5** | `20261007_103711_*` (running) |

Concurrent runs ran unpinned from 2026-10-04 15:57 UTC
(`MONEROSIM_SHADOW_CPU_PINNING=0`, `34cd8ad5`). That no result depends on
CPU placement is assumed, not tested.

## 3. Attacker revenue

Attacker canonical share. Simulator means with the range over runs, and
Model B (`scripts/sop_race_model.py`, 2000 fixed-rate days per cell).

| α | d | stock: sim (n) | stock: B | SoP: sim (n) | SoP: B |
|---|---|---|---|---|---|
| 0.30 | 2 | 0.256 (3; 0.229–0.278) | 0.263 | 0.000 (3) | 0.009 |
| 0.33 | 2 | 0.302 (3 × 240 h; 0.287–0.310) | 0.310 | 0.021 (3 × 240 h; 0.016–0.024) | 0.023 |
| 0.33 | 3 | — | 0.299 | 0.025 (2 × 240 h; 0.024, 0.025) | 0.023 |
| 0.33 | 5 | — | — | 0.019 (5 × 240 h; 0.015–0.025) | 0.020 |
| 0.40 | 1 | 0.377 (3) | 0.411 | 0.113 (3; 0.033–0.174) | 0.131 |
| 0.40 | 2 | 0.409 (3) | 0.425 | 0.187 (3; 0.126–0.287) | 0.142 |
| 0.40 | 3 | 0.459 (3) | 0.422 | 0.127 (3; 0.037–0.234) | 0.142 |
| 0.45 | 2 | 0.496 (3) | 0.510 | 0.373 (3; 0.220–0.470) | 0.356 |

- Under SoP the attacker earns less than α in every cell, so the
  stubborn strategy does not pay up to α = 0.45. The 6 h cells are noisy
  (one α = 0.45 draw reached 0.470, above α), but their means sit on
  Model B.
- The block arm (an attacker that embeds no shares) earns 0.000 in all six
  SoP draws at α = 0.40 and 0.45.
- Damage is not removed. At α = 0.33 the network orphan rate is
  0.320–0.329 under SoP against 0.202–0.209 under stock. Almost all of it
  is the attacker's own blocks (attacker orphan rate 0.95–0.97). Honest
  miners lose far less than under stock.

## 4. The simulator against Model B

Model B simulates the same attacker event by event (Poisson work objects,
fixed difficulty, no latency). Simulator side: a "reveal" is a reorg on
honest-001 whose new blocks include attacker-found blocks, and its depth is
the honest blocks it orphaned, as in Model B. Model B side: 1000 fixed-rate
years per cell, about 677 canonical years. A canonical day is 720
canonical blocks. α = 0.33, 240 h runs.

| config | runs | reveals | per 1000 found: sim / B | per canonical day: sim / B | mean depth: sim / B | attacker orphan rate: sim / B |
|---|---|---|---|---|---|---|
| stock d2 | 3 | 2692 | 100.4 / 103.0 | 91.1 / 92.7 | 1.14 / 1.13 | 0.272 / 0.252 |
| SoP d2 | 3 | 87 | 2.81 / 2.95 | 2.98 / 3.13 | 2.28 / 2.52 | 0.956 / 0.953 |
| SoP d3 | 2 | 66 | 3.19 / 3.01 | 3.39 / 3.20 | 3.21 / 2.87 | 0.949 / 0.953 |
| SoP d5 | 5 | 126 | 2.42 / 2.63 | 2.59 / 2.81 | 3.55 / 3.35 | 0.962 / 0.959 |

Checked further, to test whether the simulator reproduces Model B's
mechanics and not just its averages:

- **Share budget.** The attacker embeds 54 % (d2) and 72 % (d5) of the
  shares it finds, and Model B's attacker 55.5 % and 69.8 %. Shares mined
  on a tip the attacker abandons are lost in both. Honest blocks embed
  about 96 % of honest shares (Model B: 98.5 %), about 15 per block.
- **Validation.** In the two runs checked (d2 and d5), for all 256
  attacker blocks honest-001 judged, the share count it counted equals the
  count the attacker's miner embedded. No share set was voided.
- **Give-up.** In the seven runs checked, the honest lead before every
  revealed race stayed below d: at most 4 at d5, 2 at d3, 1 at d2.
- **Race shapes.** Blocks per side, shares per block on both sides and
  work objects at the reveal all match Model B within noise.
- **Depth.** The first two d5 runs read deeper than Model B: mean 3.83, 7
  reveals of 7+ blocks against 2.8 expected, and two of 10 blocks. On
  resampling against Model B's reveal distribution that gives p 0.02,
  0.02 and 0.008. The three banlog runs, the same cell, did not replicate
  it: mean 3.31 (B 3.35, p 0.59), 3 reveals of 7+ against 3.3 expected,
  none of 10. Pooled (126 reveals): mean 3.55, p 0.11. d2 read
  shallower (2.28, p 0.04) and d3 deeper (3.21, p 0.03) with 2–3 runs
  each. No mechanism was found (all four checks above came out clean).
  These are treated as sampling variation.

## 5. Deep reorgs and the give-up depth

Rates of reorgs orphaning 10+ honest blocks, α = 0.33, SoP, attacker
embedding its shares (Model B, about 677 canonical years per cell):

| give-up depth d | 10+ reorgs per canonical year | one per |
|---|---|---|
| 2 | 0.347 | 2.9 years |
| 3 | 0.677 | 1.5 years |
| 5 | 2.44 | 5 months |

- MRL #146's "about one reorg of 10+ blocks per 3 years" matches d = 2
  only. An attacker that holds on until honest leads by 5 causes them
  about 7× as often. The spec does not fix d, so the claim needs it
  stated. Earlier estimates in the spec comments of the depth matrices
  were shorter runs: d3 there read 1 per 1.35 years.
- Per real day these rates are higher. Difficulty retargets on the
  canonical chain, and under this attack about a third of all found blocks
  are orphaned. So about 1.49× as many blocks are found per day as at a
  fixed rate (10,443 found against 7,013 canonical in the first d5 run).
  Model B now reports canonical-day rates (`e1b6b9db`). The spec's
  per-time figures assume a fixed rate.
- The simulator cannot observe these rates directly. It saw two
  10-block reorgs in 48.7 canonical days at d5, where Model B expects
  0.33 (Poisson p about 0.04; see §4 on depth), and none at d2 (29.2
  days) or d3 (19.5 days).
  - 2000-01-09 05:23, long_depth d5: a 7-block branch beat 10, eight
    seconds after the second ban wave of §6.
  - 2000-01-06 17:45, long_depth_rep d5: 13 over 10, in a run with no bans.

## 6. P2P ban cascade

### 6.1 What happened

In the first d5 run, honest nodes, relays and seeds banned each other: 48
"Host X blocked." lines covering all 11 other hosts, in three waves (sim
01-08 19:39, 01-09 05:22, 01-09 05:57). relay-002 sat on a stale 4-block
branch for 13.7 sim-hours. It resynced when its first ban expired, exactly
24 h after it began. Its resync logged the run's one "Sent invalid chain",
a harmless race with a peer that reorganized mid-sync. Both honest nodes
banned the attacker's bridge for 24 h.

### 6.2 Mechanism (verified)

Stock monero (`cryptonote_protocol_handler.inl`, three sites) calls
`hit_score(context, 1)` whenever a peer reports a lower height than it did
before ("Claims N, claimed M before"). The second hit on a connection drops
it with ban score 5 (`add_host_fail`). A host whose fail score passes
`P2P_IP_FAILS_BEFORE_BLOCK` (10) is blocked for `P2P_IP_BLOCKTIME` (24 h),
and its score resets to 5. The score never decays within a node's uptime.
Under SoP a node legitimately switches to a branch with FEWER blocks but
more share weight, and its peers see that as a height drop.

The three `stubborn_h10_banlog` runs (the d5 cell with `net.cn:DEBUG` on
every daemon) logged every hit and every scored drop:

| seed | shorter-branch switches (summed over nodes) | height-drop hits | scored drops | bans logged | bans replayed and matched |
|---|---|---|---|---|---|
| 24680 | 78 | 645 | 267 | 57 | 57 / 57 |
| 12345 | 45 | 489 | 209 | 10 | 10 / 10 |
| 54321 | 11 | 118 | 0 | 0 | — |

- Replaying the fail score from the logged drops predicts every ban, on
  the same host and within 5 ms. No ban is unexplained.
- Every scored drop (474 of score 5, 2 of score 1) followed height-drop
  hits on its connection.
- Every hit came at most 63 s (median 14–44 s) after the claiming peer's
  SoP switch to a shorter branch.
- More shorter-branch switches meant more bans.

Example, seed 24680: honest-001 bans the attacker's bridge (3.0.0.11).
Hits on 01-04 and 01-05 lead to a drop (+5). Two hits on 01-07 lead to a
drop (10). Hits at 01-08 06:15 and 20:33:51.352 lead to a drop (15 > 10),
and "Host 3.0.0.11 blocked." is logged at 20:33:51.352.

### 6.3 Incidence

Bans occurred in 3 of 5 d5 runs (48, 57 and 10 bans; 0 and 0), in none of
the d2 (3) or d3 (2) runs, and never in stock runs. Shorter-branch switches
come in network-wide episodes. With one or two connections per peer pair, a
pair bans after about 4–6 episodes. The first d5 run had 8 episodes, the
most of the depth runs, and its first wave came at the 4th.

### 6.4 Fix (committed; check pending)

`002cd40c`: with `--sim-share-or-perish`, `hit_score` logs "SIM-SoP: peer
height drop not scored" and returns. Stock and PoP-only nodes keep stock
scoring. `stubborn_h10_banfix{,_rep,_rep2}` re-run the banlog cells on that
binary. The pass criteria are the hits still logged, each followed by the
not-scored line, no score-5 drop and no ban. **Result: pending
(2026-10-08).** These runs use Shadow v0.2.5; every other run here used
v0.2.4. The pass criteria do not depend on it, and attack rates will be
compared with the banlog runs as a check.

### 6.5 What it means for a deployment

As specified, SoP would run on a P2P layer that treats a falling peer
height as misbehaviour. A sustained stubborn attacker that holds on (d5)
then makes honest nodes ban each other, isolating some for up to 24 h at a
time. A deployment must change that scoring. How often it would bite on the
real network, with real peer counts and peer churn, is not measured.

## 7. Spec findings (candidates for MRL #146; the owner decides)

1. **The fork-choice loop is unspecified.** The spec does not say whether
   blocks displaced by a reorg are judged again one at a time or as a
   whole branch (conformance doc, convention 6). The readings differ
   materially. Under the per-block "rejudge" reading
   (`--sim-sop-rejudge-displaced`), switches were undone within a second
   (flip-backs on the attacker's bridge: up to 3 per run, in 3 of 4 runs), so nodes can
   disagree, and the attacker earned {0.043, 0.000} at α = 0.40 and
   {0.000, 0.000} at α = 0.45. Under the whole-branch reading it earned
   0.187 and 0.373 (§3).
2. **Not a soft fork, as implemented.** In run `20260930_161539` an
   unmodified v0.18 bridge rejected share-carrying blocks ("has old
   version", `blockchain.cpp`; vote check in `hardfork.cpp`). Our
   implementation carries the share count in the block's minor version
   (conformance doc, convention 8), which legacy nodes treat as a
   hard-fork vote. The spec does not define how a block carries its shares
   in a form legacy nodes accept. Verify against the issue text before
   reporting this one.
3. **The per-time claims assume a fixed block rate.** About 1.49× as many
   blocks are found per real day under this attack (§5).
4. **The 10+ reorg rate depends on the give-up depth**: about 1 per 3
   years only at d = 2, about 1 per 5 months at d = 5 (§5).
5. **The P2P ban cascade (§6)**: the spec's weight-based fork choice
   conflicts with monero's height-based peer scoring. Pending the fix
   check.

## 8. Controls

- **Honest fairness** (`sop2_h10_honest`, α = 0.40 played honestly, 6 h,
  n = 2): a fully SoP-flagged honest miner earns {0.380, 0.406}.
  The stock pair is {0.385, 0.465}.
- **Textbook attackers** (`pop_sop2_h10_fixed`, α = 0.40, n = 2): ES
  {0.000, 0.000} and lead-2 {0.015, 0.000} under SoP. The corrected-preset
  stock pairs of 2026-09-29 are {0.519, 0.544} and {0.491, 0.500}.
- **"Connected" control** (a miner that does not share on an SoP network):
  {0.387, 0.382}, consistent with α by z −0.45 and −1.88. It is NOT an
  upgrade-transition result: every simulated daemon skips the hard-fork
  vote check (sim patch), so it is not a real non-upgraded node (cf. §7.2).

## 9. Not established

- **Network scale.** 12 daemons, 2 equal honest miners, fast propagation.
  Honest blocks here embed about 96 % of honest shares. With many pools on
  a global network, more shares could miss the next block template, and
  lighter honest blocks help the attacker. The 5 s lateness window and the
  ban cascade (§6.5) also need realistic peer counts and latencies. This is
  the roadmap's stepped-up replica (about 300 nodes).
- **Other attackers.** Only the spec's stubborn attacker, a non-embedding
  variant, ES and lead-2 were run. No attacker with a network advantage
  (γ > 0) was run.
- **Mixed networks** (upgraded alongside non-upgraded nodes): see §8.
- **α other than 0.33 at long horizons.** The 0.30/0.40/0.45 rows are 6 h,
  n = 3.
- **The depth-tail reading** of §4 (sampling variation, not a mechanism).
- **The ban fix** (§6.4), pending.

## 10. Reproduction

- **Specs:** `test_configs/matrix/<name>.yaml`. Run with
  `venv/bin/python scripts/selfish_matrix.py <spec>` and re-score with
  `--reanalyze`. Each cell's marker is `matrix_runs/<name>/cells/<cell>.json`
  (run dir, health, share).
- **Checks:** `venv/bin/python scripts/sop_oracle.py check <SoP run dirs>`
  (exit 0: no mismatches; exit 2: a run had no SoP decisions);
  `.claude/campaign7/flipback_scan.py <run dirs>`.
- **Model B:** `scripts/sop_race_model.py sweep --days 2000` and
  `... deep --years N`. The 1000-year runs and per-reveal shapes come from
  the analysis tooling below.
- **Analysis tooling** for §§4–6: `.claude/campaign7/analysis/`. It is
  outside the package and git-ignored; moving it into `scripts/` with
  tests is an open item. Outputs are in `out/`, and Model B results in
  `modelb/`.

| script | what it computes |
|---|---|
| `reveal_stats.py` | reveals and honest-orphan depths on honest-001, blocks found |
| `compare_modelb.py` | the §4 table and depth tail tests (`modelb/run_one.py` makes its inputs) |
| `depth_mc.py` | the depth resampling tests of §4 |
| `modelb_shapes.py` | Model B with per-reveal shapes and share budgets |
| `share_budget.py`, `embed_vs_judged.py` | shares found, embedded and judged per miner |
| `race_leads.py` | the largest honest lead in every revealed race |
| `reorg_depths.py` | reorg depth histograms per node |
| `ban_replay.py` | the fail-score replay of §6 (needs net.cn:DEBUG logs) |
