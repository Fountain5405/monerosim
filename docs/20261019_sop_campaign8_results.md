# Share-or-Perish (MRL #146) under the 2026-10-15 revision: campaign 8 results (2026-10-14 to 2026-10-19)

**Status: DRAFT, 2026-10-19.** Every number below comes from finished,
checked runs. Not reported on
MRL #146; posting is the owner's call. Campaign 7
(`docs/20261007_sop_campaign7_results.md`) ran the issue's earlier text.
Campaign 8 re-ran its cells twice: first on the old build under the n_f
reading the author described (`sim-sop-nf-rule: either`), then on a build
that follows the issue's 2026-10-15 revision ("rev2"). It also added
40-daemon runs.

Seeds don't reproduce runs (monerod is partly non-deterministic), so every
comparison between builds or campaigns below is between unpaired draws.

## Summary

| # | Result | Confidence |
|---|---|---|
| 1 | **The revision keeps SoP's effect on revenue.** At α = 0.33 the rev2 attacker's share is 0.019–0.029 in six 240 h runs and 0.027–0.032 in three 48 h runs at 40 daemons. Stock gives 0.303 at 40 daemons (campaign 7: 0.302 at 12). The old build gave 0.020–0.037. At α = 0.40, all nine 6 h rev2 draws are below 0.40 (0.000–0.286; sign test p = 0.002). At α = 0.45, one 72 h run gave 0.379; two of four 6 h draws are above 0.45. | High at 0.33. Solid at 0.40. At 0.45, one long run below α: suggestive, not established. |
| 2 | **The rule behaves as written.** Over the ten long runs: 41,261 SoP decisions, 0 mismatches against the spec oracle; 5,208 switches, 0 that would switch straight back under the `either` reading (1,985 under the alt-only reading). Re-judging every decision under the spec's exact rules changes no outcome. | High. |
| 3 | **The reveal rate replicates: about 3.3 reveals per canonical day** at α = 0.33 (2.7–4.1 across six 240 h runs; campaign 7: 2.98). That is about 33× the spec's "once per 10 days". At α = 0.45: 51 a day (one 72 h run). | High at 0.33 (six 240 h runs on the revised build; campaign 7 on the earlier text). |
| 4 | **Its cause replicates at α = 0.33.** At the moment of each of 208 reveals (eight runs), honest-001 had received a median of 40 honest shares that no block yet carried. Had those counted, 204 of the 208 reveals (98 %) would have been blocked; the 40-daemon replicate adds 7 of 7. Campaign 7: 87 of 87, from three runs. At α = 0.45 the cause is weaker: 85 of 140 (61 %). | High at 0.33. One run at 0.45. |
| 5 | **Reorg depth.** At α = 0.33, against stock, SoP cuts reveals about 28× and orphaned honest blocks about 10×. But each reveal it allows is deeper: a mean of 2.6–3.2 honest blocks against 1.1. No α = 0.33 run orphaned 10+ honest blocks; the deepest was 8 (SoP, d5) and stock's deepest 7. **At α = 0.45 (72 h), two events took 10 blocks off every node's tip in 2.73 canonical days:** a reveal that orphaned 10 honest blocks, and a 10-block attacker branch that a 7-block honest branch undid 4 s later. | Moderate at 0.33: the 10+ tail is too rare for these runs. At 0.45: one run and no stock baseline beyond 6 h. This attacker is not a deep-reorg hunter (§6). |
| 6 | **40 daemons.** SoP holds: 0.032 and 0.027 at d2 (two runs) and 0.027 at d5, against stock's 0.303. The three "Sent invalid chain" errors in the stock run were relays on unmodified monerod reorganizing just before they relayed. They aren't caused by the SoP patch. | High for the share. Two runs at d2, one per other cell. |
| 7 | **tevador's "about 1 per 3 years" reproduces in Model B, for a stronger attacker than ours.** With his attacker, which uses the honest shares found on the fork point and restarts level after giving up, Model B gives one 10+ reorg every 2.9 years at α = 1/3 (95 %: 2.2–3.8), and six runs of his script 2.1 (1.3–3.7). Model B as built gave 21 years. Our daemon attacker's miner is offline and embedded 0 gossiped shares, so it is Model B as built (§6). | High for the models: 51 events in Model B, 16 in his script. The daemon attacker's share handling: the code and one smoke run's logs. |

## 1. Builds and specs

- **Old build** (`matrix_runs/sop_either_*`): the pop patch at `072f9b63`, run with `--sim-sop-nf-rule either` on every SoP node.
- **rev2** (`matrix_runs/sop_rev2_*`): the patch at `1f7ac1fb`, which follows the revision. main_seen is fixed per height, and shares are counted from version_major (`version_minor = version_major + N`). Still run with `--sim-sop-nf-rule either`. Installed monerod-sim sha256 `43dd67f7…` (built 2026-10-15). Every rev2 run used that binary, as does each run in §8.
- **Network:** the campaign-7 12-daemon network (`test_configs/selfish_micro_sop.yaml`), and a 40-daemon network (`test_configs/selfish_n40_sop.yaml`: 8 honest miners with the same total hashrate, 24 relays, 6 seeds, the attacker's miner and bridge). Both use the 1200-node CAIDA topology (per-link latency, e.g. 25–60 ms).
- **Binaries per role:**
  - honest miners and seeds run monerod-sim in every run;
  - relays and the bridge run monerod-sim with SoP in the sop2 arm, and unmodified monerod in the stock arm (`test_configs/matrix/sop_rev2_n40.yaml:39-53`);
  - the attacker's miner runs `--offline` and copies honest blocks over RPC.
- **Attacker:** `window_stubborn` (`agents/selfish_strategy.py:217-253`).
  - It reveals its whole branch as soon as the branch holds 48 work objects and outweighs the honest one.
  - It gives up when the honest branch leads by d blocks (`give_up_depth`).
  - It embeds its own shares (the `share` arm).

| stage | specs (cells) | sim time | runs | wall time |
|---|---|---|---|---|
| A | `sop_rev2_h10{,_rep,_rep2}` (α 0.40 d1/d2/d3, α 0.45 d2) | 6 h | 12 | 0.5–0.8 h each |
| B1 | `sop_rev2_h10_long{,_rep}` d2, `sop_rev2_h10_long_depth` d3 | 240 h | 3 | 19.6–22.0 h |
| B2 | `sop_rev2_h10_long_depth` d5, `sop_rev2_h10_long_depth_rep` d3, d5 | 240 h | 3 | 41.1–42.1 h (CPU stacking, see `.claude/HANDOFF.md`) |
| n40 | `sop_rev2_n40` share_sop2 d2, block_stock d2; `sop_rev2_n40_depth` d5 | 48 h | 3 | 26.3 h (stacked), 5.7 h, 6.8 h |
| overnight (§8) | `sop_rev2_n40_rep` share_sop2 d2 (40 daemons); `sop_rev2_h10_a045_72h` share_sop2_a045_d2 | 48 h; 72 h | 2 | 6.6 h; 6.2 h |

## 2. Attacker revenue

Attacker share of main-chain blocks (`share` in `matrix_runs/<spec>/table.md`). Honest mining would earn α.

| α | d | rev2 | old build | campaign 7 sim, mean (n) | campaign 7 stock |
|---|---|---|---|---|---|
| 0.33 | 2 | 0.025, 0.029 (240 h); 0.032, 0.027 (40 daemons, 48 h) | 0.020, 0.037 (240 h); 0.038 (40 daemons, 6 h) | 0.021 (3 × 240 h) | 0.302 (3 × 240 h); rev2 at 40 daemons: 0.303 |
| 0.33 | 3 | 0.021, 0.021 (240 h) | 0.024 (240 h) | 0.025 (2) | — |
| 0.33 | 5 | 0.029, 0.019 (240 h); 0.027 (40 daemons, 48 h) | — | 0.019 (5) | — |
| 0.40 | 1 | 0.102, 0.032, 0.033 | 0.146, 0.035, 0.038 | 0.113 (3) | 0.377 |
| 0.40 | 2 | 0.158, 0.112, 0.219 (smoke: 0.082) | 0.106, 0.321, 0.155 | 0.187 (3) | 0.409 |
| 0.40 | 3 | 0.157, 0.000, 0.286 (smoke: 0.114) | 0.110, 0.120, 0.155 | 0.127 (3) | 0.459 |
| 0.45 | 2 | **0.379 (72 h)**; 0.362, 0.536, 0.233 (6 h; smoke: 0.508) | 0.359, 0.444, 0.564 | 0.373 (3) | 0.496 |

- Apart from the 72 h run, α 0.40 and 0.45 cells are 6 h runs (about 100–130 main-chain blocks). The smoke (`matrix_runs/sop_rev2_smoke`) ran on the rev2 binary with stage A's seed.
- **At α = 0.45 the 72 h run gave 0.379, 0.071 below α,** over 1,965 main-chain blocks; 47 % of the attacker's blocks were orphaned. Its three failed verdicts are the two Eyal–Sirer curves and "attacker beats honest baseline". All three mean the attacker earned less, as in every SoP run here.
  - The 6 h draws straddle α, so this is one long draw against four short ones.
  - It is suggestive, not established; a replicate would settle it.

## 3. Rule checks

| check | runs | result |
|---|---|---|
| Spec oracle (`scripts/sop_oracle.py check`) | stage A with part of B1 (2026-10-16); the eight long runs | 4,361 decisions, 0 mismatches; 25,380 decisions on 152 nodes, 0 mismatches |
| Lateness probe (`python -m scripts.sop_lateness_probe replay`) | the eight long runs | 15,949 decisions judged; 3,238 switches (513 subjective). Straight back under `either`: 0. Under alt-only: 1,125 |
| Flip-back scan (`scripts/selfish_mining/flipback_scan.py`) | the eight long runs and the 40-daemon stock run | No reorg onto the attacker undone within 1 s. Two flagged events were both a newer, heavier branch arriving (below) |
| Late-start scan (`.claude/campaign8/late_start_scan.py`, all 166 archived SoP dirs, rerun after §8) | everything | `rev2_spec_outcome_diff 0`; 62 nodes, all relays, came online 1–3 blocks late (36, 22 and 4 nodes by 1, 2 and 3 blocks; 18 in 14 of 70 twelve-daemon runs, 44 in the three 40-daemon runs); 4 decisions change regime, none outcome |

- **h10_long_rep, 809,133 s, seen by all 11 nodes.**
  - First, every node switched to the attacker's 4-block release (fork 7547, objective, 3162 vs 2346).
  - Then, 0.15–0.84 s later, each switched to a heavier 3-block branch off the same fork (5712 vs 3162). That branch is the honest chain plus a new block.
- **long_depth_rep d3, attacker-bridge only, 104,219 s.** The bridge took the attacker's blocks over RPC (fork 1682: KEEP, KEEP, then SWITCH at 3233 vs 2968). 0.17 s later a 4-block branch at 5459 arrived over P2P: the old honest main plus a new block.
- **Late starters** are covered by the spec-only build (§7).
- **The two overnight runs (§8),** checked the same way (`data/campaign8/analysis_out/*_overnight_20261019.*`):
  - oracle: 15,881 decisions on 52 nodes, 0 mismatches;
  - lateness probe: 10,153 decisions judged, 1,970 switches (60 subjective); straight back under `either` 0, under alt-only 860;
  - late-start scan: one relay per run came online a block late; no decision changes outcome;
  - flip-back scan: one flagged event, on the attacker-bridge only (α 0.45, 229,075 s). The bridge switched to the attacker's 8-block branch (fork 2695, 4183 vs 4089), and 0.11 s later a heavier branch (4559) arrived. It is the same pattern as the bridge event above; it was not examined further.

## 4. Reveal rate

Reveals are reorgs on honest-001 that apply attacker blocks (`scripts/selfish_mining/sop_reveals.py stats`). A canonical day is 720 main-chain blocks.

| run (α = 0.33) | d | reveals | canonical days | per day |
|---|---|---|---|---|
| h10_long | 2 | 34 | 9.78 | 3.48 |
| h10_long_rep | 2 | 40 | 9.74 | 4.11 |
| h10_long_depth | 3 | 29 | 9.70 | 2.99 |
| h10_long_depth_rep | 3 | 28 | 9.73 | 2.88 |
| h10_long_depth | 5 | 37 | 9.71 | 3.81 |
| h10_long_depth_rep | 5 | 26 | 9.71 | 2.68 |
| all six | | 194 | 58.4 | 3.32 |
| n40 (40 daemons) | 2 | 8 | 1.76 | 4.55 |
| n40_depth (40 daemons) | 5 | 6 | 1.72 | 3.48 |
| n40_rep (40 daemons) | 2 | 7 | 1.74 | 4.03 |

- **At α = 0.45** (the 72 h run, d2): 140 reveals in 2.73 canonical days, 51 a day.
- Campaign 7 measured 2.98 per canonical day at d = 2 (Model B 3.13). The spec says the attacker can expect to avoid the lateness penalties "on average once per 10 days", which is 0.1 a day. The revision didn't touch the part of the rule that drives the rate (below).
- **The pending-share check** (`python -m scripts.selfish_mining.sop_pending`, run from the repo root):
  - What it counts: honest shares received on honest-001 between the last main-chain block and the switch, with receipts within 2 s collapsed. A reveal counts as blocked if the attacker's object lead would not survive adding those shares.
  - Result: 208 reveals in the eight runs. Pending shares: median 40, mean 40.8, maximum 83. The attacker's lead at the reveal: median 6 objects (mean 10.6). Blocked if counted: 204 of 208.
  - By run: 33/34, 39/40, 29/29, 37/37, 27/28, 26/26; and at 40 daemons, 7/8, 6/6.
  - Campaign 7's three banfix runs, the only ones with share receipts then: 87 of 87, median 40.
  - The 40-daemon replicate (§8): 7 of 7, median 33.
  - **At α = 0.45 (§8): 85 of 140 (61 %),** median backlog 14 (mean 16.3, maximum 57). Across that run and the 40-daemon replicate, the attacker's lead at the reveal was a median 10 objects, against 6 at α = 0.33. At α = 0.45 the attacker more often wins on a real lead, so counting pending shares would block fewer reveals.
- **So the mechanism of campaign 7 §4.1 holds under the revision and at 40 daemons.**
  - The fork choice counts a share only once a block carries it. Honest blocks come about 180 s apart with about 15 shares each.
  - The attacker wins by revealing while the honest side holds a large uncommitted backlog.
  - Whether that's acceptable or a design problem is for the thread.
- **The other item campaign 7 left open, "a check at non-zero network delay":** the simulator already runs on the CAIDA topology with per-link latency. So this item can only mean Model B, which has no delay. It hasn't been done.

## 5. Reorg depth: SoP against stock

Honest blocks orphaned per reveal on honest-001, α = 0.33, 240 h runs (`sop_reveals.py stats`, `depths={...}`). Stock is campaign 7's three `stubborn_h10_long*` block_stock runs. They use the same `window_stubborn` attacker weighing by difficulty, with no window.

| arm | d | runs | reveals | 1 | 2 | 3 | 4 | 5 | 6–9 | 10+ | mean | honest blocks orphaned per run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SoP rev2 | 2 | 2 | 74 | 16 | 22 | 16 | 16 | 3 | 1 | 0 | 2.62 | 97 |
| SoP rev2 | 3 | 2 | 57 | 10 | 12 | 14 | 14 | 4 | 3 | 0 | 3.00 | 86 |
| SoP rev2 | 5 | 2 | 63 | 11 | 15 | 11 | 10 | 10 | 6 | 0 | 3.22 | 102 |
| stock | 2 | 3 | 2,692 | 2,398 | 237 | 45 | 8 | 3 | 1 | 0 | 1.14 | 1,020 |

- **SoP turns many shallow reorgs into a few deeper ones.**
  - Each reveal under SoP needs a branch of 48+ objects, about 3 blocks' worth.
  - Reorgs of 5+ honest blocks: 2 per run at d2, 3.5 at d3 and 8 at d5, against 1.3 for stock at d2. At equal d the counts are too small to separate (4 in 2 runs against 4 in 3).
- **The 10+ tail:**
  - none in 58.4 canonical days of rev2, nor in 3.5 at 40 daemons; the deepest orphaned 8 honest blocks (d5);
  - campaign 7 saw two in 48.7 days at d5;
  - Model B (campaign 7 §5) expects 2.44 a year at d5 and 0.35 at d2, so about 0.13 events in the 19.4 d5 days here. Zero is consistent with that, and campaign 7's two remain the outlier (Poisson p about 0.04).
- **The flip-back scan's "+N" is not this depth.** It counts attacker blocks added. Under SoP it reaches +10 to +13 in four runs, while no reveal orphaned more than 8 honest blocks. Quote honest blocks orphaned from `sop_reveals.py stats`.
- The 40-daemon replicate: 7 reveals of 2–5 honest blocks (2: 3, 3: 2, 5: 2).

### α = 0.45, d2: the 72 h run (2.73 canonical days)

- **Reveals:** 140 reveals orphaned 398 honest blocks: 1: 29, 2: 42, 3: 28, 4: 19, 5: 12, 6–9: 9, 10+: 1; mean 2.84. That is about 146 honest blocks a canonical day, against about 10 at α = 0.33.
- **Two events took 10 blocks off the tip of every node** (`sop_reveals.py depths`; times are simulated, from honest-001's log):
  - 2000-01-03 18:57:19, split 2791: the attacker's 12-block branch replaced 10 honest blocks.
  - 2000-01-03 12:29:39, split 2592: the attacker's 10-block branch replaced 6 honest blocks. 4.1 s later, honest-001's own miner found a block on the old honest tip. That 7-block branch has less cumulative difficulty (2,573,825 against 2,576,040) but more SoP weight, and every node switched to it, popping all 10 attacker blocks.
  - A smaller case of the second kind, at 2000-01-02 22:58: a 3-block honest branch popped 8 attacker blocks 2.9 s after the reveal, again led by a block from honest-001's miner.
- **Why honest-001's miner was still on the old tip, 2.9 s and 4.1 s after its node switched: unmodified monerod's built-in miner** (v0.18.5.1, `sibling_repos/monero`):
  - Blocks that arrive over P2P go through `try_add_next_blocks`, which calls `handle_incoming_block(..., false)` (`cryptonote_protocol_handler.inl:1539-1543`). So the miner's template is not refreshed when they are added, even when they cause a reorg.
  - The miner picks up a new template only on its idle timer, `once_a_time_seconds<5> m_update_block_template_interval` (`miner.h:139`, `miner.cpp:184-190`), so for up to 5 s it keeps mining on the old tip. A block it finds itself refreshes the template at once (`cryptonote_core.cpp:1307`).
  - None of the simulator's patches touches this; `monero-sim-mining.patch` only throttles hashing and shifts template timestamps.
  - It is rare: 0–11 of about 800–3,500 blocks per honest miner were logged as "not added to the main chain (stale template or lost race)" in the α = 0.45 run, a rev2 240 h run and a stock 240 h run.
  - Under stock rules such a block just goes stale. Under SoP a block on the old tip can carry enough shares to outweigh a longer branch, which is how both honest retakes happened.
- **Against Model B:** it expects 253 reveals of 10+ a year at α = 0.45 d2 (campaign 7 §5), about 1.9 in 2.73 days. One is consistent with that.
- **No stock baseline:** stock runs at α = 0.45 are 6 h long, so these runs can't say whether SoP raises or lowers 10-block tip pops at α = 0.45.

## 6. An attacker that wants deep reorgs

- **The runs in §§2–5 and campaign 7 had no attacker trying to cause deep reorgs.**
  - `window_stubborn` reveals at the first chance; for the deep-reorg rate, d alone matters (campaign 7 §5).
  - `deep_hunt` (2026-10-19) is that attacker. It holds its branch until the honest branch is 10 blocks deep, then follows `window_stubborn`, and it gives up 2 blocks behind. Its daemon runs are under way: stock at α = 0.33, 0.40 and 0.45 for 48 h each, and SoP at α = 0.45 for 72 h and α = 0.40 for 240 h. This section has the model side only.
- **The α = 0.45 run (§5) is the one simulator measurement where Model B expects 10+ reorgs most days.** It saw two 10-block tip pops in 2.73 days, from an attacker that wasn't trying for them.
- Animated walk-through of the share mechanics below: `docs/assets/sop/shares_at_a_fork.html`.

### 6.1 Model B against tevador's simulator

tevador's simulator (github.com/tevador/scratchpad, `share-or-perish/blockhain-sim.py`, commit 59d6094c of 2026-10-17) is the source of the spec's "about 1 per 3 years" at α = 1/3. Its attacker abandons the fork once more than 5 work objects behind. It succeeds when the honest branch holds 10 blocks and its own branch is at least as heavy. Model B as built gave about 1 per 21 years for that attacker. `sop_race_model.py reconcile` switches his attacker's differences on one at a time. α = 1/3; two seeds of 40,000 days, pooled; the switches are cumulative.

| attacker | 10+ reorgs per year | about one every |
|:--|--:|--:|
| Model B as built: its first block carries only its own shares, and it restarts with none after giving up | 0.048 | 21 years |
| + restarts level with honest after giving up | 0.157 | 6.4 years |
| + its first block carries the honest shares found before either side's first block, one per slot | 0.335 | 3.0 years |
| + the window ends on either branch | 0.315 | 3.2 years |
| + wins half of exact ties (= tevador's attacker) | 0.349 | 2.9 years |
| tevador's script, 6 runs of 12,316 days in all | 0.47 (0.27–0.77) | 2.1 years |

- **The two models agree** once the attacker uses honest shares the way his does: 2.2–3.8 years for Model B and 1.3–3.7 for his script (95 % ranges). Two differences close the gap: the level restart (about 3×) and the honest shares on the fork point (about 2×). The window and tie rules change almost nothing at depth 10.
- **Why the attacker can use those honest shares, and only those.**
  - A share fits only a child of the block it was mined on, in the slot it was mined for (`docs/20260930_sop_conformance.md:28-30`, `:64-67`).
  - Honest shares found on the fork point, before either side's first block, fit the attacker's rival first block as well as the honest one. They sit in both, so they stop counting as an honest lead.
  - Once the honest side has its first block, its new shares are mined on that block and fit nothing of the attacker's. After both first blocks, the parents differ and nothing is shared.
  - After giving up, the attacker adopts the honest tip, and the honest shares already found on it are public.
- **The slot rule caps the gain.**
  - A block carries one share per slot, so an attacker share clashes with the honest share at the same slot. The attacker's first block carries the honest run plus its own shares above it, not the sum of both.
  - His script models this by naming each share by its position (`UNIQUE_SHARES = True`).
  - Counting every share instead, as his `UNIQUE_SHARES = False` does, gives an attack every 11 days, in his script (11.1) and in Model B (10.8) alike. The slot rule forbids it.

### 6.2 Our daemon attacker uses no honest shares

- **The attacker's miner runs `--offline`** (`test_configs/selfish_micro_sop.yaml:91`).
  - A node pools a share only from its own miner or from P2P gossip, never from a block it is handed (`patches/monero-sim-pop.patch:645` and its two callers).
  - The agent forwards only blocks (`agents/selfish_miner.py:449`).
- **Checked at runtime.** In the `deep_hunt` smoke run (`20261019_111740_deep_hunt_smoke__share_sop2_a045_d2`), the attacker's miner built 1,199 templates embedding its own shares 14,273 times and gossiped ones 0 times. Each honest node's templates were about half gossiped shares, matching the other honest node's own count, so none of the attacker's shares reached them either (`data/campaign8/analysis_out/attacker_embedding_check_20261019.txt`).
- **So our daemon attacker is Model B as built**, and that is the like-for-like model for the `deep_hunt` daemon runs. Model B's 10+ reorg rate at their settings (give up 2 blocks behind, reveal at 10 deep):

| α | as built: our daemon attacker | with honest shares (`hunt --honest-shares`) | ratio |
|--:|--:|--:|--:|
| 0.33 | 0.35 per year (13 in 13,403 days) | 0.65 per year (24) | about 2× |
| 0.40 | 0.30 per day | 0.40 per day | 1.35× |
| 0.45 | 5.3 per day | 6.15 per day | 1.16× |

- **About the table.**
  - α = 0.33 is one seed of 20,000 days. α = 0.40 and 0.45 are seeds 1 and 2 of 2,000 days each, within 2 % of each other. Rates are per canonical day or year.
  - At tevador's object give-up (o5) the ratio is larger: 2.5× at α = 0.40 and 1.7× at α = 0.45. At α = 0.33 it is 0 against 7 reorgs in 13,403 days.
  - Stock, same attacker (d2): 2,136 per year at α = 0.33, about 6,000 times SoP's as-built rate.
- **The daemon runs can't tell the two columns apart.** At α = 0.45, over 2.7 canonical days, Model B expects about 14 reveals as built against 17 with honest shares. Read the runs against the as-built column.
- **A daemon attacker that uses honest shares** would need a way to hand gossiped shares to its offline miner, because blocks don't carry the shares still pending on their tip. That needs an agent change and a new RPC; not done.

### 6.3 Reading the rule

- **The window doesn't protect deep forks.**
  - The lateness penalty only applies while both branches hold fewer than k·w = 48 objects past the fork. A 10-block fork is far past that and is judged on plain weight.
  - Plain weight counts a share as diff/w, the same as a header (`docs/20260930_sop_conformance.md:32-35`).
  - Any protection against deep reorgs therefore comes from weight granularity, which only shares carried in blocks provide (§4), not from lateness. That is a reading of the rule, not a measurement.
- **Against a majority attacker no fork-choice rule helps,** and SoP doesn't claim to.

## 7. Spec-only build (after the queue)

- **What it is:** `.claude/campaign8/after_queue/monero-sim-pop.patch`, the revision with nothing optional. It changes three things:
  - n_f: the `--sim-sop-nf-rule` option is gone, and the revised n_f is the only rule;
  - the window test is `h0 + 1 < hf`;
  - h_0 is the node's tip at its first sync (DB tip for `--offline`), and decisions before that are objective. Log v3.
- **Effect on archived data: none** (§3, `rev2_spec_outcome_diff 0`).
- **Status:**
  - compiles (2026-10-19, 0 errors);
  - applied by `apply.py` after the runs in §8 (it strips `sim-sop-nf-rule` from the specs, which the rev2 binary still read). Installed by the owner's `./setup.sh --sim-binary` at 10:13Z. The binary's provenance lists the spec-only `monero-sim-pop.patch` (sha256 `b8b15002…`), and the binary no longer contains `sim-sop-nf-rule`;
  - **12-daemon smoke** (`.claude/campaign8/after_queue/sop_v3_smoke.yaml`, share_sop2_a040_d2, 6 h):
    - 319 decision records, all log v3;
    - oracle: 29 decisions on each of 12 nodes, 0 mismatches;
    - lateness probe: 33 switches, 0 straight back under `either`;
  - **late-start checks (v3):** `h_0` logged correctly in 77 of 77 decisions, and the `online` flag correct in all 77; one online banner per node (52); no `h_0` check failures; no decision before its node came online;
  - **40-daemon smoke** (3 h): SoP armed and online on all 40 nodes, but the run saw no fork (health `no-forks`), so it logged no decisions. The oracle exits 2 on a run with no decisions. The two queued 48 h 40-daemon runs on this build (`sop_v3_n40_rep2`, `sop_v3_n40_depth_rep`) will exercise decisions.

## 8. Overnight runs (2026-10-19 03:07–09:44 UTC, rev2 binary): done

| spec | cell | why | wall time | result |
|---|---|---|---|---|
| `sop_rev2_n40_rep` (seed 54321) | share_sop2_a033_d2, 40 daemons, 48 h | Second draw at 40 daemons | 6.6 h (18 cores) | share 0.027 (§2); 7 reveals (§4) |
| `sop_rev2_h10_a045_72h` (seed 24680) | share_sop2_a045_d2, 12 daemons, 72 h | Revenue at α 0.45 beyond 6 h draws. Model B predicts 10+ reorgs most days at α 0.45 (253 a year at d2); the simulator never measured that | 6.2 h (14 cores) | share 0.379 (§2); two 10-block tip pops (§5) |

- **Queue:** `.claude/campaign8/run_queue_overnight.py` (log `queue_overnight.log`).
- **Checks:** the queue ran the per-job checks on both runs at the end: the oracle, the lateness probe, the flip-back and late-start scans, `sop_reveals.py stats` and `depths`, and `sop_pending` (§3–§5).
  - Its `sop_pending` step called the script by path and failed on the import. It was rerun as a module.
  - Copies of the outputs: `data/campaign8/analysis_out/*_overnight_20261019.*`.

## 9. Not established

- **Revenue at α = 0.45:** one 72 h run (0.379) below α, against four 6 h draws that straddle it. A second 72 h run would settle it.
- **Error bars at 40 daemons:** two runs at share_sop2 d2, one each at block_stock d2 and share_sop2 d5. For a write-up, 2–3 per cell.
- **The deep-reorg rate in the daemons for an attacker that wants deep reorgs, under stock and under SoP:** the `deep_hunt` runs are under way. Model B has it (§6.2).
- **A daemon attacker that uses honest shares, as tevador's does.** Ours never sees them (§6.2). Model B puts the difference at 1.16× (α = 0.45) to about 2× (α = 0.33) at the daemon runs' settings.
- **10-block tip pops at α = 0.45 under stock:** stock has no run there longer than 6 h (§5).
- **How common the honest retakes of §5 would be on mainnet.** Their cause is known: it is unmodified monerod (§5), so a real solo miner behaves the same. But mainnet hashrate mines mostly through pools and p2pool, which get a push on every new block, so the sim's 5 s exposure is an upper bound.
- **The reveal-rate cause at non-zero delay in Model B (§4).**
- **The reveals that pending shares would not have blocked:** four at α = 0.33 (one each in h10_long, h10_long_rep, long_depth_rep d3 and n40 d2) and 55 at α = 0.45 haven't been examined.

## 10. Reproduction

- **Specs:** `test_configs/matrix/sop_rev2_*.yaml` and `sop_either_*.yaml`. Run with `venv/bin/python scripts/selfish_matrix.py <spec> --cells <cell>`. Tables: `matrix_runs/<spec>/table.md` and `results.json`.
- **Queues:** `.claude/campaign8/run_queue.py` (old build), `run_queue_rev2.py`, `run_queue_overnight.py`.
- **Checks:**
  - as in §3;
  - reveal rate and depth: `venv/bin/python scripts/selfish_mining/sop_reveals.py stats OUT.json <runs>` and `... depths OUT.json <runs>`;
  - pending shares: `venv/bin/python -m scripts.selfish_mining.sop_pending <runs>`. Run it as a module from the repo root; a script path fails on the import.
- **Outputs behind §§3–5:** `data/campaign8/analysis_out/`. They hold the per-job check outputs for B2 and the 40-daemon stock run (`*_20261019.txt`), the flip-back "+N" histogram per run for every rev2 and archived stock run (`flipback_plusN_by_run_20261019.txt`), and the reveal, depth and pending-share outputs, and every check on the two overnight runs (`*_overnight_20261019.*`). They are re-creatable with the commands above in under a minute.
- **Model B and tevador's script (§6):**
  - `venv/bin/python -m scripts.sop_race_model reconcile --days 40000 --seed 1` (and `--seed 2`);
  - `... hunt --alphas 0.33 --days 20000 --seed 1` and `--alphas 0.40 0.45 --days 2000`, each with and without `--rules sop --honest-shares`;
  - his script ran with `python3 -I`, as published and with `UNIQUE_SHARES = False`;
  - the embedding check: `venv/bin/python .claude/campaign8/embed_check.py <run>`;
  - outputs: `data/campaign8/analysis_out/modelb_*_20261019.md`, `tevador_script_runs_20261019.md` and `attacker_embedding_check_20261019.txt`.
