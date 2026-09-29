# Selfish mining on Monero — working manuscript and backing-material index

**Status:** working notes for a planned manuscript, 2026-09-22. Branch
`feat/selfish-mining-experiments`. Everything below is backed by committed
code, archived runs, and dated result documents in this repository; §7 maps
every number to its run directory and commit. Companion index:
`docs/SELFISH_MINING.md` §10.

## 1. Research questions

- **RQ1** — Do the classical selfish-mining revenue predictions (Eyal–Sirer
  γ=0; Lee–Kim's conservative-release modification) hold on a *faithful*
  Monero network simulation with real monerod binaries and real PoW?
- **RQ2** — What does an attacker's observed 2025 behaviour (Qubic:
  conservative release at lead 2, fine-grained toggling) actually cost, in
  revenue and in network damage?
- **RQ3** — Can an attacker composing selfish mining with eclipse attacks
  (hashrate recruitment through an isolated "island" view) convert eclipsed
  hashrate into canonical-chain share — and what does the composition cost
  when recruitment fails?
- **RQ4** — Can deployed detectors (Li et al. 2020 MSB) distinguish
  withholding attackers from honest miners, and where do they break?
- **RQ5** — Which countermeasures (MRL #144 Publish-or-Perish and its
  variants; later #146 Share-or-Perish) work against which strategies, at
  what cost to the honest network — measured on faithful monerod rather
  than assumed from the papers' models?

## 2. Related work

Full digest with source manifest: `docs/20260920_selfish_mining_literature.md`
(20 papers from moneroresearch.info, ingested 2026-09-20). Anchor results:
Eyal–Sirer γ=0 profitability threshold ≈ 1/3; Lee & Kim 2025 measured the
Qubic campaign (α 0.23–0.34, empirical γ 0.007–0.059, mostly unprofitable,
conservative lead-2 release); Li et al. 2020 MSB detection; Gervais et al.
2016 quantitative security framework; Nayak et al. eclipse+stubborn
composition.

## 3. Methods — the apparatus

- **Native mining** (`docs/NATIVE_MINING.md`): patched `monerod-sim`
  throttles hash attempts so expected block time is D/H for declared H;
  real RandomX, real LWMA. All miners, honest and attacker, mine with the
  same mechanism.
- **Selfish apparatus** (`docs/SELFISH_MINING.md` §1–2): attacker = offline
  miner + bridge relays + `SelfishMinerAgent` (forward honest in, release
  private out, per-tick strategy state machine). Strategies: honest,
  eyal_sirer, three stubborn variants, `release_lead` cash-out knob.
- **Eclipse composition** (§10.3 + the results doc): orchestrator
  `peers:`/`attributes.eclipsed` isolation knobs; offline island bridges
  relaying blocks by RPC between the attacker's miner and eclipsed victims;
  cash-on-lead lifecycle with ancestor-verified, adoption-committed
  releases.
- **Measurement** (`scripts/selfish_mining_analysis.py`,
  `scripts/selfish_externality.py`, `scripts/msb_study.py`): canonical-chain
  attribution against theory curves (ES, R_mod), realized γ (victim-aware),
  orphan/reorg/MSB/SpEC externality metrics; per-run verdicts; cross-run
  calibration.
- **Validation discipline**: every gate same-seed A/B; smoke runs before
  full runs; each code change unit-tested (559 Python + 113 Rust tests at
  time of writing); golden tests pin orchestrator output byte-identity.

## 4. Experiments and results

### E1 — Conservative release (RQ1, RQ2) ✅ complete

`docs/20260921_selfish_release2_results.md`. A/B at α=0.4: ES 0.463 vs
lead-2 0.309 (profit→loss), network orphan rate 0.274→0.214, reorg depths
collapse, MSB detectability drops. α-sweep 0.30/0.40/0.45: 0.211/0.309/
0.569 — the conservative policy's profitability crossover moves from ≈1/3
into (0.40, 0.45); at α=0.30 the measurement sits ON the Lee–Kim modified
curve (0.211 vs 0.205). Qubic's observed policy reproduces: mostly
unprofitable at their α, still damaging.

### E2 — Detection calibration (RQ4) ✅ complete

`docs/msb_calibration_20260921.md`. Honest controls (same topology,
strategy: honest): zero MSB flags. Attacks detected 8/9 (z +3.4 to +10.2).
Honest false positives cluster exactly in the heaviest attacks
(α_eff ≥ 0.4): withholding clusters honest wins, so the iid-shuffle null
over-flags honest miners precisely when it matters. Deployed detectors need
an attack-aware null; our runs can calibrate it.

### E3 — Eclipse composition (RQ3) ✅ mechanics closed at α_eff=0.667;
ω-sweep complete 2026-09-22

`docs/20260921_selfish_eclipse_results.md` (the full v1→v13 arc, seven
localized defects, then the ω-sweep). Headline results: naive mirror/pull
loses to monerod first-seen semantics at every level (v1–v3);
eclipse-as-DoS alone moves the attacker 0.192→0.385 (ω=0 vs 0.2);
ancestor-verified, adoption-committed releases took the attacker from
0.000 to 0.463 (v11); and with the full lifecycle (v13: mirror gated at
the fork + honest feed capped at the fork) the composition CONTROLS the
majority: **0.559 controlled share, victim recruitment at 0.213 canonical,
γ still 0.000**. Recruitment pays the coalition, not the attacker (its
solo share falls to 0.346 with 0.309 self-orphans), and network damage
stays severe (orphan rate 0.52) in every variant — the harm/profit
asymmetry extends to the eclipse regime. The monerod-API findings below
are themselves contributions.

**ω-sweep under v13 semantics (6 runs, 2 repeats):** controlled share
rises with ω (0.166 → 0.297 → ~0.31 ± 0.06 → 0.559/0.879 at majority) but
the composed-revenue model R_mod(α_eff) is REJECTED in the sub-majority
regime: at α_eff=0.467 victim banking is ≈0 in both 1-victim repeats
(band FAILs at −0.113/−0.235) because the island branch (3 h/s) can never
out-run the free honest chain (8 h/s) to reach the cash-out lead.
Recruitment only banks above island-vs-honest hashrate parity (ω=6 vs
honest 5: majority verdict passes twice, 0.559 and 0.879, with a
fat-variance internal split 0.346/0.213 vs 0.121/0.758 attacker/victim —
each cash-out is winner-take-all on the island race). The attacker's solo
share still climbs with ω (0.166 → 0.258–0.421) purely from eclipse-DoS
de-hashing. **The composition's payoff is thresholded at
island/honest parity, not smooth in α_eff — the Nayak-style aggregation
over-predicts exactly where a rational attacker would operate.**

### E4 — Countermeasures (RQ5: which countermeasure beats which strategy)

> **STRANDING CAVEAT (2026-09-27, same doc §5):** in every PoP/SoP attack
> cell the attacker's bridge keeps stock fork choice, so after releasing a
> long branch the attacker sees it "win" on the bridge while the flagged
> miners reject it, and keeps mining on it for up to 47 blocks. SoP cells
> lost 28–57 % of the attacker's blocks this way (0.000 headline stands, but
> mixes fork-choice losses with self-inflicted ones); PoP cells 0–88 %, and
> stranding explains most of the PoP spread. Re-runs with a bridge that runs
> the honest rule are an open owner decision.
>
> **FLAGGED-BRIDGE RE-RUN (2026-09-27/28, same doc §6): stranding NOT
> removed.** 12 cells re-ran ES and lead-2 with the bridge running the
> countermeasure rule (`pop_sop2_h10_fbridge`, `pop_exact_h10_fbridge`,
> `pop_exact_mid_fbridge`, + `_rep`). Measured at the attacker's own
> daemon, it still abandons branches of up to 29 blocks (originals: up to
> 38). The flagged bridge only hides them from honest nodes. The cause is
> the attacker's strategy, which assumes every reveal wins and compares
> heights only, so the caveat above stands for these rows too. The fix is a
> rejection-aware attacker (owner decision, not run). PoP shares stay
> below α and below stock (ES micro {0.157, 0.190}, mid {0.181, 0.236};
> lead-2 micro {0.272, 0.366}, mid {0.328, 0.291}), but realized γ is now
> 0.02–0.20, so these rows are a sensitivity check, not replacements.
> **SoP lost both ES cells** ({0.405, 0.495}): see finding 10.
>
> **STRANDING-FREE RE-RUN (2026-09-29, same doc §8; supersedes the two
> notices above for these cells).** The attacker is now rejection-aware
> (`reject_aware`: concedes a rejected reveal or a dropped commit at once)
> and the bridge runs the countermeasure. Micro cells run on the corrected
> `h10` preset, with stock pairs re-run on it. n = 2, α = 0.4.
> - SoP: ES {0.000, 0.000} and lead-2 {0.000, 0.000} vs stock {0.519,
>   0.544} / {0.491, 0.500}.
> - PoP exact, micro: ES {0.156, 0.256}, lead-2 {0.263, 0.307}.
> - PoP exact, mid: ES {0.223, 0.229} vs stock {0.376, 0.518}; lead-2
>   **{0.353, 0.419} vs stock {0.455, 0.351}**, so PoP does not stop lead-2
>   at mid scale.
>
> Realized γ in PoP cells is 0.11–0.33 (the flagged bridge announces tie
> blocks). Residual stranding: pops after a dropped commit, 0–6 per cell,
> at most 17 blocks. These are the rows to quote.
>
> **EXACT RE-RUN (2026-09-26/27, `docs/20260926_exact_uncles_and_sop_controls.md`):**
> after two more daemon fixes (review F5c: uncle sibling anchor; F5d:
> template refresh on a sibling at the tip) the MRL #144 exact cells were
> re-run at n=2. Micro (h10 base): 0 uncle headers embedded in any cell —
> at γ ≈ 0 the attacker's tie block never reaches an honest miner on its own,
> so exact = det-tie by construction there (ES {0.169, 0.199} vs stock
> {0.377, 0.441}; lead-2 {0.284, 0.292} vs {0.305, 0.469}). Mid (genesis
> base, 6 miners): uncles live but rare (12–22 embedded per cell); ES
> {0.253, 0.303} vs stock {0.376, 0.518}, lead-2 {0.241, 0.251} vs stock
> {0.455, 0.351}, honest control ≈ α. A same-daemon det-tie-only pair
> (2026-09-27): ES {0.159, 0.162}, lead-2 {0.293, 0.389} — same pooled mean
> as exact (0.251 vs 0.262), and every mid uncle was honest-vs-honest, so the
> reduction is PoP-core + det-tie; the uncle term adds nothing measurable
> against a γ ≈ 0 attacker. Relaying-bridge matrix (2026-09-27, doc §4):
> honest miners embedded 138 attacker blocks as uncles, yet 0 uncles entered
> any fork decision (ES/lead-2 abandon a race before an uncle-bearing block
> is weighed); visible ties give the attacker γ 0.10–0.43 under det-tie, and
> PoP then leaves ES ≈ 0.34–0.37 (stock 0.45), lead-2 0.28–0.42 (stock 0.38).
> The #144 uncle term had no measurable effect in any setting. Finding 9
> stays retracted; its replacement is this paragraph.
>
> **RE-RUN (2026-09-26, `docs/20260926_sop_h10_rerun.md`):** the SoP v2
> cells were re-run at n=2 on the fixed daemon and the `h10` chain-snapshot
> base (real DAA from block one, attacker at 0 s). Result: ES {0.035, 0.000}
> vs stock {0.377, 0.441}; lead-2 {0.000, 0.000} vs stock {0.305, 0.469};
> honest controls ≈ α. Every SoP decision carried share weight; no daemon
> threw. Finding 10 below is rewritten from that data. The 2026-09-25
> notice that follows is kept for the record.
>
> **REVIEW NOTICE (2026-09-25, `docs/20260925_e4_code_data_review.md`):**
> the SoP v2 verdict (finding 10), the SoP v1/v2 arc in finding 8 and
> finding 9 are **RETRACTED** pending re-runs on a fixed binary — the SoP
> build could not reorganize (a hard-fork bookkeeping hole, review F1),
> its embedded-share term never verified (F2), longer alt chains threw
> (F3), and the MRL #144 EXACT uncle bonus never counted in ANY run,
> parser fix included (F4): every `exact` cell below is pop-core +
> det-tie. PoP-core, det-tie, deviated-uncle and mid-scale results stand
> with that relabeling. Numbers transcribed from `table.md` files are
> column-shifted (F6); the cell JSONs are authoritative.

Apparatus: the matrix runner (§3) + three flag-gated `monerod-sim` PoP
modes (`docs/20260922_pop_countermeasure_design.md` pre-registers every
prediction before its run). All cells 6 h, same seed, α=0.4, flags on the
honest miners only (the covert bridge keeps stock rules — attackers don't
upgrade).

**Full readout (attacker canonical share; honest controls in text):**

| strategy | stock | pop-core (random tie) | pop-core (det tie) | +uncles deviated (random/det) | +uncles EXACT (det) |
|---|---|---|---|---|---|
| ES (textbook) | 0.492 | 0.022, 0.123 | 0.244, 0.296 | 0.024 / 0.337, 0.209 | 0.134, 0.215 |
| conservative lead-2 | 0.309 | — | — | — | — |
| honest control (share vs α=0.4) | 0.397 | 0.408 | — | 0.402 | 0.322, 0.378 |

**Correction (2026-09-24, defect audit during the SoP build):** the
"+uncles EXACT" column's weight bonus never engaged in any E4 run — its
header parser read the tx-count varint from the 32-byte tx-tree-hash
offset and rejected every real blob (P(pass) ≈ 2⁻³²), so every
`*_exact` cell measured **pop-core + det-tie** plus an inert coinbase
payload. (The DEVIATED variant counts from local alt storage and did
work.) All "exact" numbers above and in findings 6–7 keep their
measured values but carry the corrected label; the n=2 exact-vs-
deviated dead heat is fully explained. Parser fixed 2026-09-24
(`docs/20260923_sop_design.md` §step 2) — **but the review of 2026-09-25
(F4) shows the bonus STILL never counts after that fix** (the verifier
rebuilds the block and its hashing blob can never match): no `exact`
cell to date measures anything but pop-core + det-tie.

1. **P1 confirmed at ~10× margin**: pop-core nearly eliminates textbook
   ES revenue (0.492 → 0.02–0.12; attacker orphans 97% of finds; 73/77
   fork decisions KEEP honest). Mechanism verified in-daemon logs.
2. **PoP-core is blind to proactive releases**: the conservative lead-2
   attacker is untouched (0.309 → 0.349/0.326, possibly slightly helped)
   because lead-2 releases at h=0 — before honest mines the contested
   height — so its blocks arrive first-at-height = in-time. Lateness
   punishes catch-up-triggered reveals (ES) but not proactive ones
   (Qubic's observed policy). Measured support for tevador's SoP
   motivation (MRL #146).
3. **The tie policy matters more than the paper suggests**: det-tie
   (MRL #144's choice) is consistently ~4× weaker than the paper's random
   tie (0.244/0.296 vs 0.022/0.123, non-overlapping at n=2). Tie-win
   frequencies alone don't explain it (43% vs 34%) — which ties are won
   (deep vs shallow) does.
4. **Uncles are a no-op against ES at micro scale** (0.024 ≈ core), and
   the exact-vs-deviated variant A/B — the trustless-counting question —
   is NOT resolvable at n=2: exact {0.134, 0.215} vs deviated {0.337,
   0.209} (means 0.175 vs 0.273, overlapping spreads; the paired second
   draw is a dead heat, +0.006). The n=1 reading — "header uncles halve
   the det-tie leak" — is fully explained by the correction above: the
   exact variant had no uncle term at all. Only 3
   embeddings occurred per 6 h: two honest miners essentially never race
   (scale is what feeds the mechanism — finding 6). The honest_exact
   micro dip (0.322) also did not replicate: 0.378 ≈ α, orphan 0.029.
5. **Vandalism persists under every PoP variant** (net orphan 0.31–0.45
   vs 0.312 stock attack; MSB detectability stays high, z +7.4 to +14.9):
   PoP removes the profit, not the DoS.
6. **Mid-scale (6 honest miners + 16 relays) settles the rung-3 watch
   item, n=2**: the exact variant's honest-control dip was starvation/
   noise — controls sit at α in every scaled draw (0.367, 0.431; the
   micro 0.322 did not replicate either: 0.378), uncle embeddings rise
   3 → 17 with miner count as pre-registered, and the countermeasure
   holds with CLEAN SEPARATION (attacker {0.387, 0.463} stock vs
   {0.170, 0.285} exact — every exact draw below every stock draw).
   "Scale alone shrinks the stock attacker" did NOT survive n=2 (micro
   {0.463, 0.492} vs mid {0.387, 0.463} overlap, 0.463 in both sets;
   if real, ~−0.05). Residual exact-variant cost: ~9–10% honest
   throughput, twice measured (158/176 and 160/175 blocks per 6 h).
   Full-scale (12 miners + 32 relays) is the committed senior-box leg.
7. **Scale erases the micro-scale strategy separation (mid-scale,
   n=2)**: the ranking inversion seen at n=1 (lead-2 0.477 > ES 0.387)
   did NOT survive replication — ES drew 0.463 on its second mid-scale
   run, interleaving the stock sets (ES {0.387, 0.463}, lead-2 {0.477,
   0.396}; means 0.425 vs 0.437, statistically indistinguishable). At 6
   miners, textbook ES and the observed conservative lead-2 policy earn
   alike — the attack Monero actually observed cannot be dismissed as
   the weaker variant (micro had them separated by 0.18: 0.492 vs
   0.309). PoP-exact's blind spot is partial at scale and REPLICATES
   TIGHTLY: lead-2 lands at break-even in both draws (0.353/0.347 vs
   fair 0.40) while ES falls to 0.170/0.285 — lateness punishes
   catch-up reveals roughly twice as hard as proactive ones (−0.20 vs
   −0.09 on means); the residue is exactly what SoP's share-lateness
   rule targets. First nonzero realized γ appears only at this scale
   (0.03–0.10): propagation races need a fabric big enough to have
   them.
8. **Share-or-Perish v1 falsified on stability (rung 5, pre-registered
   falsifier)**: the #146 weight table implemented on gossip-pool
   weights fragments the honest network — the honest control earns
   0.547 ≠ α=0.4 with self-orphaning 18× the pre-registered threshold,
   and the attack cells collapse to 9–22 canonical blocks per 6 h
   (honest miners hold 180+-block local views; 6k–9.5k invalid-span
   drops per node). The l_w mechanism itself works — the attacker's
   share and γ both go to 0.000 with 100% attacker orphaning — but at
   the cost of the chain: weights derived from node-local gossip state
   cannot stay consistent across nodes. #146's in-block share embedding
   (omitted in v1 as an unexercised deviation) exists precisely to make
   weights node-independent; v2 with embedding is the indicated fix.
   **[The v1 fragmentation above is review-F3 (longer alt chains threw), not
   pool-derived weights; the v2 arc below is review-F1 — RETRACTED.]**
   **v2 (embedded shares, full subjectivity machinery, run same day)
   initially falsified differently** — a mixed-fleet inversion (0.723)
   and a terminal 182-vs-5 split — until the apparatus itself was
   corrected: fixed difficulty from genesis (the fakechain LWMA ramp
   manufactured bankable bootstrap islands, sub-w weight degeneracy,
   and fork-0 races that strand lagging nodes — stock converges on the
   identical topology) and an attacker that joins after bootstrap (the
   real-Monero shape). On the corrected topology the failures vanish
   (§E4 finding 10).
9. **RETRACTED 2026-09-25 (review F4 — the bonus never counted; these are
   det-tie draws).** ~~The correctly-implemented exact variant punishes lead-2, magnitude
   unresolved at n=2~~ (rung-5 re-measurement after the parse fix):
   lead-2 under exact = {0.127, 0.294} (mean 0.211) vs the inert-bonus
   era's {0.326, 0.349} and stock {0.309–0.356} — direction confirmed
   (non-overlapping), but the striking first draw (0.127) was largely
   run-to-run luck; report ~0.21 with wide spread. The residual "PoP
   blind spot" was therefore substantially the parse defect. ES is
   unchanged (0.210 ≈ 0.134/0.215 — uncles stay a no-op vs ES at micro,
   third replication).

## 5. Findings (manuscript-claim-ready)

1. The Eyal–Sirer γ=0 curve and the Lee–Kim conservative-release curve are
   both reproduced by the simulator within statistical tolerance, and the
   conservative policy's profitability crossover sits in (0.40, 0.45) —
   conservative release is a *delay*, not a *cure*.
2. Conservative release shrinks the PUBLIC harm (orphan rate, reorg depth,
   throughput dips) even as it cuts attacker revenue — the attacker's
   private loss and the network's damage decouple.
3. MSB detection is sound on honest networks and breaks under heavy
   attack by flagging honest miners — an attack-aware null is required.
4. monerod API facts, established by local repro and now encoded as tests:
   orphaned/`submit_block` rejections return HTTP 200 + status≠OK (silent
   unless checked); `get_info` height is a count (top+1); RPC-submitted
   blocks are never relayed over P2P; a "synchronized" node does not poll
   for them; offline daemons accept submits immediately, isolated-online
   ones answer BUSY forever; first-seen semantics govern alt-vs-main at
   every level.
5. Eclipse-recruited hashrate is only bankable through an island lifecycle
   that (a) keeps the victim the sole miner above the fork (mirror gated at
   the fork), (b) keeps the miner's withholding main free of honest
   adoptions (feed capped at the fork), (c) releases from the
   hash-verified common ancestor, and (d) commits only on adoption. With
   all four: controlled share 0.559 > 1/2 at α_eff=0.667 with victim
   recruitment at 0.213 canonical. Without them: eclipse-DoS plus
   self-destruction (measured 0.000–0.442 across variants).
6. The composed attack pays the coalition, not the attacker: recruitment
   costs the attacker own-block orphans (0.309) and drops its solo share
   below its no-eclipse selfish share — the eclipse only pays when the
   recruited hashrate is spent as one chain.
7. The eclipse composition's payoff is **thresholded at island-vs-honest
   hashrate parity, not smooth in α_eff** (ω-sweep, 6 runs): below parity
   the R_mod(α_eff) composed-revenue prediction is rejected (victim banking
   ≈ 0, band FAILs at α_eff=0.467 in both repeats) while the attacker still
   gains from eclipse-DoS alone; above parity the majority verdict passes
   twice. The coalition-internal split has fat run-to-run variance
   (0.346/0.213 vs 0.121/0.758) — each island cash-out is winner-take-all.
10. **Share-or-Perish v2 (#146, embedded shares) neutralizes both the
   textbook and the conservative lead-2 attacker at α = 0.4, n = 2, on a
   realistic difficulty schedule** (2026-09-26 re-run on the fixed daemon
   and the `h10` chain-snapshot base, `docs/20260926_sop_h10_rerun.md`):
   ES earns {0.035, 0.000} (0.000 against the honest network's own chain)
   vs stock {0.377, 0.441}; lead-2 — the policy PoP was blind to — earns
   {0.000, 0.000} vs stock {0.305, 0.469}. Every one of the 2,822 subjective
   fork decisions on SoP nodes carried share weight; the attacker's
   unshared, late blocks lose every race. Honest controls sit at α under
   both rules (stock {0.381, 0.410}; SoP {0.440, 0.326}). Costs: the
   attacker's 40 % of hashrate is discarded (103–143 canonical blocks per
   6 h vs ≈ 200 in the controls), the network orphan rate reads 0.36–0.52
   (vandalism stays, profit goes), and a miner that does not gossip shares
   weighs one unit in every tie — the SoP control's second draw lost 17
   such races (share 0.326, orphan 0.218), an upgrade-transition cost that
   n = 2 cannot yet size. The bridge (stock fork choice) is a biased
   reference under SoP: report SoP shares against an honest node's chain.
   **Fail-safe caveat (2026-09-28, `docs/20260926_exact_uncles_and_sop_controls.md`
   §6):** #146 applies lateness only within k·w = 48 work objects of a
   fork. Past that, fork choice is plain cumulative difficulty. In the
   flagged-bridge re-run, the ES attacker kept a rejected branch level with
   the honest chain for 49 and 51 blocks. Both times the honest miners
   switched to it on the objective rule, the second time to a branch one
   block shorter but heavier, and ES earned {0.405, 0.495}. That happened
   in 0 of 4 original SoP attack cells, and lead-2 stayed at {0.000, 0.000}.
   The attacker reached the window only because it could not see its
   reveals were rejected (the stranding bias). How often an α = 0.4
   attacker stays level that long, and whether a deliberately stubborn one
   could, is not measured. The 0.000 headline above holds only inside the
   fail-safe window and only on the stock-bridge apparatus.
   **Stranding-free re-run (2026-09-29, results doc §8): SoP holds.**
   With a rejection-aware attacker, ES earns {0.000, 0.000} and lead-2
   {0.000, 0.000} vs stock {0.519, 0.544} / {0.491, 0.500}. No honest node
   made a single past-window (OBJECTIVE) fork decision in any SoP cell, and
   the longest rejected reveal was 17 blocks. The {0.405, 0.495} above came
   from the stranding attacker. What remains open is a deliberately stubborn
   attacker that withholds past 48 work objects on purpose. That exposure
   is in the rule, and it has not been measured.
   **Earlier text, RETRACTED 2026-09-25 (review F1–F5) and superseded above:**
   ~~Share-or-Perish (#146, spec-exact v2) works on the corrected
   apparatus~~: with fixed genesis difficulty and a post-bootstrap
   attacker, the honest control is textbook — 0.405 ≈ α with ZERO
   orphaning, and the unflagged 40% miner (the upgrade-transition
   fleet) takes exactly its fair share — while textbook ES is
   annihilated (share 0.000, γ = 1.000, network healthy at 66 blocks
   vs stock's 89; a ~26% throughput cost is the price). The lead-2
   policy (the attack Monero observed) is log-verified neutralized:
   every fork evaluation of its releases returns weight 0 (l_b = 0 for
   released-late blocks, l_w = 0 for never-gossiped shares) and is
   kept off; its canonical output is bounded to outright tip wins, far
   under its stock 0.471 (the analysis row was lost twice to a
   covert-bridge freeze under release bursts — open defect, 2 of 8
   cells). Stocks pair cleanly (es 0.337, lead-2 0.471 — lead-2 again
   out-earns ES). The earlier v1/v2 falsifications traced to the
   simulator's degenerate bootstrap, not the rule: the lesson for the
   countermeasure literature is that timing-subjective fork choice
   must be evaluated on realistic difficulty schedules, or the
   evaluation itself manufactures failures.

8. **Publish-or-Perish's fork-choice core alone nearly eliminates ES
   revenue at Monero speeds** (E4 pilot, pre-registered): attacker share
   0.492 → 0.022 at α=0.4 with the attacker orphaning 97% of its finds
   (73/77 fork decisions KEEP honest), while the honest control is
   unaffected (0.408 ≈ α, orphan 0.02, throughput unchanged). But the
   attack's network damage RISES under PoP (orphan 0.312 → 0.447) and its
   MSB detectability too (+7.9 → +14.9): PoP removes the profit, not the
   vandalism — incentive-removal and DoS-resilience are separate
   countermeasure properties.
   **Update (2026-09-29, results doc §8; the pilot numbers above predate
   the review fixes).** On the fixed apparatus with a rejection-aware
   attacker, MRL #144 exact PoP cuts textbook ES by roughly half: micro
   0.206 vs stock 0.531, mid 0.226 vs 0.447 (n = 2 means). It does **not**
   stop the conservative lead-2 attacker at mid scale: 0.386 vs stock
   0.403, one draw 0.419 > α. Micro lead-2 falls to 0.285 vs 0.496.
   Realized γ is 0.11–0.33 in these cells.

## 6. Limitations

- **Every `h10` cell ran ~10 % fast** (2026-09-29,
  `docs/20260926_exact_uncles_and_sop_controls.md` §7): the `h10`
  snapshot handed its consumers a next-block difficulty of 1083 vs
  D0 1200, so blocks averaged ~106 s, not 120 s. The bias is shared by
  every cell on that base, so within-run share comparisons stand;
  absolute block and orphan rates are ~10 % high, and the extra natural
  forks feed γ slightly. The preset was regenerated 2026-09-29 behind a
  next-block-difficulty gate (+1.8 % vs D0); cells run after that are
  unaffected.
- Micro-topology (8–13 hosts, 2–5 miners): honest-fragmentation effects at
  larger scale are unmeasured here; single runs per point except where
  repeats are noted (n=2 at α_eff 0.467 and 0.667, and across E4 after
  the 2026-09-24 replication campaign — every quantitative E4 claim now
  carries n=2; the exact-vs-deviated magnitude remains unresolved),
  `native_preemption: true` (share σ≈0.05; the eclipse coalition-internal
  SPLIT has much fatter variance than the controlled total — each island
  cash-out is winner-take-all); A/A byte-determinism requires
  `native_preemption: false`.
- Phase-1 configs are transaction-free (bare-block relay); the externality
  metrics are attribution-complete only when all canonical blocks come from
  logged miners.
- The eclipse composition models a *successful* eclipse by configuration
  (peer pinning), not the attack mechanics themselves (peerlist poisoning
  is a separate harness, `analysis/eclipse/`).
- Chain-selection countermeasures (Publish-or-Perish etc.) deliberately
  not built: they change consensus behaviour; when built as sim-only flags
  they measure hypothetical future Monero, not today's.

## 7. Reproducibility ledger

Every run's archived directory carries its own `input_config.yaml`,
`shadow_agents.yaml`, daemon logs, and analysis output; runs execute the
commit listed (run_sim rebuilds nothing with `--no-build`, so the working
tree at run time = that commit).

| Run directory | Commit | Config | What it shows |
|---|---|---|---|
| `20260920_224552_native_micro_test` | (main, pre-branch) | `native_micro.yaml` | native-mining gate re-verified: 6/6 PASS |
| `20260921_023050_selfish_micro_es_baseline` | `22c8eebe` | `selfish_micro.yaml` | ES α=0.4: 0.463, on the γ=0 curve |
| `20260921_020113_selfish_release2` | `22c8eebe` | `selfish_release2.yaml` | lead-2 A/B: 0.309, below honest |
| `20260921_102229_r2_sweep_a0300` / `_a0450` | `22c8eebe` | `selfish_sweep_release2/` | sweep points 0.211 / 0.569 |
| `20260921_112254_gamma_eclipse` | `a83a467f` | `gamma_eclipse.yaml` (v1) | 0.161 — island-resync deadlock |
| `20260921_162235_gamma_eclipse_v2` | `1c78d348` | (v2) | 0.291 — victims bank exactly 0 |
| `20260921_162236_ecl_sweep_omega0000` | `1c78d348` | `omega_0000.yaml` | no-eclipse anchor 0.192 (PASS) |
| `20260921_171216_ecl_sweep_omega0200` / `_omega0300_3v` | `1c78d348` | ω-sweep (v2 semantics) | 0.283 / 0.385, victim share 0.000 |
| `20260921_180433_ecl_honest_baseline` | `1c78d348` | `honest_baseline.yaml` | honest control (v2 semantics) |
| `20260921_183612_gamma_eclipse_v3` / `_honest_baseline_v3` | `3fe13de5` | (v3) | 0.295; control proves plumbing |
| `20260921_194446_gamma_eclipse_majority` | `03d99687` | `gamma_eclipse_majority.yaml` (v4) | pulls fire, victims still 0 |
| `20260921_202404_gamma_eclipse_majority_v5` | `8559e5a1` | (v5) | 0.388 controlled; island chain 100% victim = genesis-fork clue |
| `20260921_212731_gamma_eclipse_majority_v7` | `207985b6` | (v7) | relay built; RPC timeouts pre-start (clue) |
| `20260921_215932_gamma_eclipse_majority_v8` | `02ebffea` | (v8) | island at height 0 = BUSY/status clue |
| `20260921_222242_gamma_eclipse_majority_v9` | `cc5b774c` | (v8b) | relay push errors past-the-top (count clue) |
| `20260921_224414_gamma_eclipse_majority_v10` | `445ec02a` | (v8c) | victim finally mines the fed chain; attacker 0.000 |
| `20260922_033212_gamma_eclipse_majority_v11` | `077c71d1` | (v11) | attacker 0.463, orphan 0.026; victim still 0 |
| `20260922_041348_gamma_eclipse_majority_v12` | `fe4f374a` | (v12) | mirror fork-gate alone: 0.442, victims 0 (miner main compounds 9 h/s) |
| `20260922_044845_gamma_eclipse_majority_v13` | `7ce8e384` | (v13) | honest feed capped at fork: **0.559 controlled — PASS**; victim 0.213 canonical |
| `20260922_105252_ecl13_omega0300_3v` | `8e26c6ba` | `omega_0300_3v.yaml` | ω-sweep v13: 3×1 victims, controlled 0.429, victim 0.008 (band PASS) |
| `20260922_105252_ecl13_frontier0467` | `8e26c6ba` | `gamma_eclipse.yaml` | frontier α_eff=0.467: controlled 0.372, victim 0.000 (band FAIL −0.113) |
| `20260922_124435_ecl13_frontier0467_rep` | `970b76bb`* | `gamma_eclipse.yaml` | frontier repeat: 0.250, victim 0.000 (band FAIL −0.235) |
| `20260922_114614_ecl13_omega0200` | `8e26c6ba` | `omega_0200.yaml` | ω=2: controlled 0.297, victim 0.039 (band PASS) |
| `20260922_114614_ecl13_majority0667_rep` | `8e26c6ba` | `gamma_eclipse_majority.yaml` | majority repeat: **0.879 controlled — PASS**; split swings to 0.121/0.758 |
| `20260922_124435_ecl13_omega0000` | `970b76bb`* | `omega_0000.yaml` | no-eclipse anchor: 0.166 on the ES curve at α=0.267 (unprofitable) |

(*agent code identical to `7ce8e384`; later commits are configs/docs only.
All six ω-sweep runs launched before the 13:05Z monerod-sim rebuild, i.e.
on the 4-patch binary — the PoP patch is flag-gated OFF in every ω-sweep
config, so daemon behavior is stock either way.)

| `20260922_140138_pop_pilot__es_none` | `5751f7df` | `pop_pilot` cell | E4 baseline: ES 0.492 on the curve (all verdicts PASS) |
| `20260922_140138_pop_pilot__es_pop` | `5751f7df` | `pop_pilot` cell | **PoP core: 0.022, attacker orphan 0.973** — P1 confirmed |
| `20260922_144601_pop_pilot__honest_none` | `5751f7df` | `pop_pilot` cell | honest control: 0.397 ≈ α |
| `20260922_144601_pop_pilot__honest_pop` | `5751f7df` | `pop_pilot` cell | PoP honest control clean: 0.408 ≈ α, no storms |
| `20260922_165018_pop_followup__es_pop_det` | `b5bfbf8b`* | `pop_followup` cell | det-tie: 0.244 — the single-run det-tie gap |
| `20260922_165018_pop_followup__es_r2_pop` | `b5bfbf8b`* | `pop_followup` cell | **PoP blind to lead-2**: 0.349 vs 0.309 stock |
| `20260922_173130_pop_followup__es_r2_pop_det` | `b5bfbf8b`* | `pop_followup` cell | 0.326; first nonzero realized γ 0.040 |
| `20260922_182536_pop_wave2__es_pop` / `_es_pop_det` | `404f3b9f`* | `pop_wave2` cells | repeats: 0.123 / 0.296 — det-tie gap holds at n=2 |
| `20260922_190749_pop_wave2__es_pop_uncles` | `404f3b9f`* | `pop_wave2` cell | deviated uncles: 0.024 ≈ core (no-op vs ES) |
| `20260922_190819_pop_wave2__honest_pop_uncles` | `404f3b9f`* | `pop_wave2` cell | control clean: 0.402 ≈ α |
| `20260923_012704_pop_exact__es_exact` | `2c86e6aa`* | `pop_exact` cell | **EXACT uncles: 0.134** — halves the det-tie leak |
| `20260923_012704_pop_exact__es_uncles_det` | `2c86e6aa`* | `pop_exact` cell | deviated at det-tie: 0.337 (variant A/B) |
| `20260923_020739_pop_exact__honest_exact` | `2c86e6aa`* | `pop_exact` cell | control dips: 0.322, orphan 0.050 — scale pending |
| `20260923_023639_pop_scale__es_none` | `ccc44897`* | `pop_scale` cell (mid) | mid-scale stock: 0.387 (scale shrinks the attacker) |
| `20260923_035522_pop_scale__es_exact` | `ccc44897`* | `pop_scale` cell (mid) | **exact holds at scale: 0.170**, 17 uncle embeddings |
| `20260923_045220_pop_scale__honest_none` | `ccc44897`* | `pop_scale` cell (mid) | mid control: 0.386 ≈ α |
| `20260923_160801_pop_scale__honest_exact` | `610158e5`* | `pop_scale` cell (mid) | control recovers at scale: 0.367 ≈ α — the dip was starvation |
| `20260923_170500_pop_scale_r2__es_r2_none` | `233ae38d`* | `pop_scale_r2` cell | **lead-2 at scale: 0.477 — out-earns textbook ES** |
| `20260923_175813_pop_scale_r2__es_r2_exact` | `233ae38d`* | `pop_scale_r2` cell | blind spot partial at scale: 0.353 ≈ break-even |
| `20260924_030014_pop_exact_rep__es_exact` | `cfd1dd6b`* | `pop_exact_rep` cell | exact rep: 0.215 — n=1 A/B gap deflates |
| `20260924_030014_pop_exact_rep__es_uncles_det` | `cfd1dd6b`* | `pop_exact_rep` cell | deviated rep: 0.209 (paired dead heat) |
| `20260924_034156_pop_exact_rep__honest_exact` | `cfd1dd6b`* | `pop_exact_rep` cell | control rep: 0.378 ≈ α — micro dip was noise |
| `20260924_040630_pop_scale_r2_rep__es_r2_none` | `306f8b9e`* | `pop_scale_r2_rep` cell | lead-2 stock rep: 0.396 — inversion margin thins |
| `20260924_045805_pop_scale_r2_rep__es_r2_exact` | `306f8b9e`* | `pop_scale_r2_rep` cell | blind-spot residue replicates: 0.347 (γ 0.098) |
| `20260924_055049_pop_scale_rep__es_none` | `550c8c2e`* | `pop_scale_rep` cell | mid stock rep: 0.463 — the n=1 inversion claim dies |
| `20260924_064254_pop_scale_rep__es_exact` | `550c8c2e`* | `pop_scale_rep` cell | mid exact rep: 0.285 — separation holds at n=2 |
| `20260924_073808_pop_scale_rep__honest_none` | `550c8c2e`* | `pop_scale_rep` cell | mid control rep: 0.400 ≈ α |
| `20260924_082914_pop_scale_rep__honest_exact` | `550c8c2e`* | `pop_scale_rep` cell | exact control rep: 0.431 ≈ α; throughput −8.6% |
| `20260924_121104_pop_sop__es_none` | `b046e0b1`* | `pop_sop` cell | stock ES: 0.492 — replicates the pilot exactly |
| `20260924_121104_pop_sop__es_sop` | `b046e0b1`* | `pop_sop` cell | SoP v1: 0.136 but 22 canonical blocks — collapse |
| `20260924_125116_pop_sop__es_exact` | `b046e0b1`* | `pop_sop` cell | fixed-parser exact vs ES: 0.210 ≈ inert era |
| `20260924_132719_pop_sop__es_r2_none` | `b046e0b1`* | `pop_sop` cell | stock lead-2: 0.356, in band |
| `20260924_133321_pop_sop__es_r2_sop` | `b046e0b1`* | `pop_sop` cell | SoP v1 vs lead-2: 0.000 on a 9-block chain — collapse |
| `20260924_140925_pop_sop__es_r2_exact` | `b046e0b1`* | `pop_sop` cell | **fixed-parser exact vs lead-2: 0.127 — the bonus bites** |
| `20260924_144929_pop_sop__honest_none` | `b046e0b1`* | `pop_sop` cell | control clean: 0.399 ≈ α |
| `20260924_144929_pop_sop__honest_sop` | `b046e0b1`* | `pop_sop` cell | **P-SoP3 falsified: 0.547, self-orphan 0.542 (18×)** |
| `20260924_152904_pop_sop__honest_exact` | `b046e0b1`* | `pop_sop` cell | fixed-parser exact control: 0.357 clean |
| `20260925_034724_pop_sop2__es_stock` | `de5fb7b7`* | `pop_sop2` cell | fixed-topology stock ES: 0.337 (late-join attacker) |
| `20260925_034724_pop_sop2__es_sop2` | `de5fb7b7`* | `pop_sop2` cell | **SoP v2: ES annihilated — 0.000, γ 1.000, network healthy** |
| `20260925_043207_pop_sop2__es_r2_stock` | `de5fb7b7`* | `pop_sop2` cell | stock lead-2: 0.471 — again out-earns ES |
| `20260925_050341_pop_sop2__honest_sop2` | `de5fb7b7`* | `pop_sop2` cell | **SoP v2 control: 0.405 ≈ α, ZERO orphaning — P-SoP3 passes** |
| `20260925_051212_pop_sop2__honest_stock` | `de5fb7b7`* | `pop_sop2` cell | stock control: 0.369 |
| `20260925_055045_pop_sop2__es_r2_sop2` | `de5fb7b7`* | `pop_sop2` cell | lead-2 under SoP: row lost to bridge freeze; log-verified every release → weight 0, kept off |
| `20260926_140803_pop_sop2_h10__es_sop2` | `703bdffe`† | `pop_sop2_h10` cell | **SoP v2 vs ES on h10: 0.035 (honest-ref 0.000)**, 720/720 decisions share-weighted |
| `20260926_140823_pop_sop2_h10_rep__es_sop2` | `703bdffe`† | `pop_sop2_h10_rep` cell | SoP v2 vs ES rep: 0.000 |
| `20260926_140803_pop_sop2_h10__es_stock` / `_rep__es_stock` | `703bdffe`† | `pop_sop2_h10*` cells | stock ES on h10: 0.377 / 0.441 |
| `20260926_140803_pop_sop2_h10__es_r2_sop2` / `_rep__es_r2_sop2` | `703bdffe`† | `pop_sop2_h10*` cells | **SoP v2 vs lead-2: 0.000 / 0.000** — the PoP blind spot closed |
| `20260926_140803_pop_sop2_h10__es_r2_stock` / `_rep__es_r2_stock` | `703bdffe`† | `pop_sop2_h10*` cells | stock lead-2 on h10: 0.305 / 0.469 |
| `20260926_140803_pop_sop2_h10__honest_sop2` / `_rep__honest_sop2` | `703bdffe`† | `pop_sop2_h10*` cells | SoP controls: 0.440 / 0.326 (rep lost 17 ties, orphan 0.218) |
| `20260926_140803_pop_sop2_h10__honest_stock` / `_rep__honest_stock` | `703bdffe`† | `pop_sop2_h10*` cells | stock controls: 0.381 / 0.410 ≈ α |

(All `pop_sop` SoP rows and all `pop_sop2` rows above are INVALID per the
2026-09-25 review — F1/F3: the daemon could not reorganize. The `*_exact`
rows measure pop-core + det-tie — F4. Kept for provenance.)

(PoP cells ran the 5-patch monerod-sim, build 2026-09-22T13:05Z, flag ON
on the honest miners only; matrix table at `matrix_runs/pop_pilot/table.md`
— gitignored workdir, rows reproduced here and in the design doc.)

(v6 was killed early — the `mine_after_height` gate held a victim whose
daemon was stuck at height 1 by the then-undiagnosed count bug; no result.)

| `20260926_203140_pop_exact_mid__es_exact` | `238aed7e` | `pop_exact_mid` cell ‡ | es_exact: share 0.253 (honest-ref 0.253), blocks 190, forks 6872, sw 65, health ok |
| `20260926_203201_pop_exact_mid_rep__es_exact` | `238aed7e` | `pop_exact_mid_rep` cell ‡ | es_exact: share 0.303 (honest-ref 0.303), blocks 195, forks 4144, sw 37, health ok |
| `20260926_203140_pop_exact_mid__es_none` | `238aed7e` | `pop_exact_mid` cell ‡ | es_none: share 0.376 (honest-ref 0.376), blocks 93, forks 1366, sw 0, health ok |
| `20260926_203201_pop_exact_mid_rep__es_none` | `238aed7e` | `pop_exact_mid_rep` cell ‡ | es_none: share 0.518 (honest-ref 0.518), blocks 195, forks 3507, sw 0, health ok |
| `20260926_203140_pop_exact_mid__es_r2_exact` | `238aed7e` | `pop_exact_mid` cell ‡ | es_r2_exact: share 0.241 (honest-ref 0.241), blocks 166, forks 3449, sw 44, health ok |
| `20260926_203200_pop_exact_mid_rep__es_r2_exact` | `238aed7e` | `pop_exact_mid_rep` cell ‡ | es_r2_exact: share 0.251 (honest-ref 0.251), blocks 175, forks 1939, sw 28, health ok |
| `20260926_230344_pop_exact_mid__es_r2_none` | `238aed7e` | `pop_exact_mid` cell ‡ | es_r2_none: share 0.455 (honest-ref 0.455), blocks 145, forks 2424, sw 0, health ok |
| `20260926_230504_pop_exact_mid_rep__es_r2_none` | `238aed7e` | `pop_exact_mid_rep` cell ‡ | es_r2_none: share 0.351 (honest-ref 0.351), blocks 194, forks 1758, sw 0, health ok |
| `20260926_231316_pop_exact_mid__honest_exact` | `238aed7e` | `pop_exact_mid` cell ‡ | honest_exact: share 0.416 (honest-ref 0.416), blocks 178, forks 41, sw 0, health ok |
| `20260926_231036_pop_exact_mid_rep__honest_exact` | `238aed7e` | `pop_exact_mid_rep` cell ‡ | honest_exact: share 0.367 (honest-ref 0.367), blocks 188, forks 106, sw 34, health ok |
| `20260926_231717_pop_exact_mid__honest_none` | `238aed7e` | `pop_exact_mid` cell ‡ | honest_none: share 0.405 (honest-ref 0.405), blocks 195, forks 90, sw 0, health ok |
| `20260926_231908_pop_exact_mid_rep__honest_none` | `238aed7e` | `pop_exact_mid_rep` cell ‡ | honest_none: share 0.470 (honest-ref 0.470), blocks 181, forks 46, sw 0, health ok |

| `20260927_014733_pop_dettie_mid__es_dettie` | `cd233568` | `pop_dettie_mid` cell ‡ | es_dettie: share 0.159 (honest-ref 0.159), blocks 164, forks 6329, sw 0, health ok |
| `20260927_014753_pop_dettie_mid_rep__es_dettie` | `cd233568` | `pop_dettie_mid_rep` cell ‡ | es_dettie: share 0.162 (honest-ref 0.162), blocks 198, forks 11776, sw 0, health ok |
| `20260927_014733_pop_dettie_mid__es_r2_dettie` | `cd233568` | `pop_dettie_mid` cell ‡ | es_r2_dettie: share 0.293 (honest-ref 0.293), blocks 164, forks 2025, sw 0, health ok |
| `20260927_014753_pop_dettie_mid_rep__es_r2_dettie` | `cd233568` | `pop_dettie_mid_rep` cell ‡ | es_r2_dettie: share 0.389 (honest-ref 0.389), blocks 180, forks 3637, sw 0, health ok |

| `20260927_032741_pop_exact_relay__es_dettie_relay` | `c7155952` | `pop_exact_relay` cell ‡ | es_dettie_relay: share 0.338 (honest-ref 0.338), blocks 157, forks 1115, sw 0, health ok |
| `20260927_032802_pop_exact_relay_rep__es_dettie_relay` | `c7155952` | `pop_exact_relay_rep` cell ‡ | es_dettie_relay: share 0.063 (honest-ref 0.063), blocks 127, forks 6276, sw 0, health ok |
| `20260927_032741_pop_exact_relay__es_exact_relay` | `c7155952` | `pop_exact_relay` cell ‡ | es_exact_relay: share 0.336 (honest-ref 0.336), blocks 146, forks 1683, sw 0, health ok |
| `20260927_032802_pop_exact_relay_rep__es_exact_relay` | `c7155952` | `pop_exact_relay_rep` cell ‡ | es_exact_relay: share 0.365 (honest-ref 0.365), blocks 156, forks 898, sw 0, health ok |
| `20260927_050234_pop_exact_relay__es_r2_dettie_relay` | `c7155952` | `pop_exact_relay` cell ‡ | es_r2_dettie_relay: share 0.415 (honest-ref 0.415), blocks 164, forks 1809, sw 0, health ok |
| `20260927_045723_pop_exact_relay_rep__es_r2_dettie_relay` | `c7155952` | `pop_exact_relay_rep` cell ‡ | es_r2_dettie_relay: share 0.313 (honest-ref 0.313), blocks 163, forks 1246, sw 0, health ok |
| `20260927_050534_pop_exact_relay__es_r2_exact_relay` | `c7155952` | `pop_exact_relay` cell ‡ | es_r2_exact_relay: share 0.281 (honest-ref 0.281), blocks 153, forks 633, sw 0, health ok |
| `20260927_050053_pop_exact_relay_rep__es_r2_exact_relay` | `c7155952` | `pop_exact_relay_rep` cell ‡ | es_r2_exact_relay: share 0.414 (honest-ref 0.421), blocks 133, forks 1086, sw 0, health ok |
| `20260927_032741_pop_exact_relay__es_r2_stock_relay` | `c7155952` | `pop_exact_relay` cell ‡ | es_r2_stock_relay: share 0.376 (honest-ref 0.376), blocks 165, forks 691, sw 0, health ok |
| `20260927_032802_pop_exact_relay_rep__es_r2_stock_relay` | `c7155952` | `pop_exact_relay_rep` cell ‡ | es_r2_stock_relay: share 0.384 (honest-ref 0.384), blocks 151, forks 800, sw 0, health ok |
| `20260927_032741_pop_exact_relay__es_stock_relay` | `c7155952` | `pop_exact_relay` cell ‡ | es_stock_relay: share 0.460 (honest-ref 0.460), blocks 139, forks 921, sw 0, health ok |
| `20260927_032802_pop_exact_relay_rep__es_stock_relay` | `c7155952` | `pop_exact_relay_rep` cell ‡ | es_stock_relay: share 0.445 (honest-ref 0.445), blocks 146, forks 850, sw 0, health ok |

| `20260927_130223_pop_sop2_h10_fbridge__es_r2_sop2` | `cf55ea8e` | `pop_sop2_h10_fbridge` cell ‡ | es_r2_sop2: share 0.000 (honest-ref 0.000), blocks 115, forks 91, sw 172, health ok |
| `20260927_130243_pop_sop2_h10_fbridge_rep__es_r2_sop2` | `cf55ea8e` | `pop_sop2_h10_fbridge_rep` cell ‡ | es_r2_sop2: share 0.000 (honest-ref 0.000), blocks 130, forks 51, sw 140, health ok |
| `20260927_130223_pop_sop2_h10_fbridge__es_sop2` | `cf55ea8e` | `pop_sop2_h10_fbridge` cell ‡ | es_sop2: share 0.405 (honest-ref 0.405), blocks 121, forks 980, sw 617, health ok |
| `20260927_130243_pop_sop2_h10_fbridge_rep__es_sop2` | `cf55ea8e` | `pop_sop2_h10_fbridge_rep` cell ‡ | es_sop2: share 0.495 (honest-ref 0.495), blocks 107, forks 1020, sw 562, health ok |
| `20260927_130303_pop_exact_h10_fbridge__es_exact` | `cf55ea8e` | `pop_exact_h10_fbridge` cell ‡ | es_exact: share 0.157 (honest-ref 0.157), blocks 121, forks 235, sw 20, health ok |
| `20260927_130323_pop_exact_h10_fbridge_rep__es_exact` | `cf55ea8e` | `pop_exact_h10_fbridge_rep` cell ‡ | es_exact: share 0.190 (honest-ref 0.190), blocks 121, forks 272, sw 0, health ok |
| `20260927_130303_pop_exact_h10_fbridge__es_r2_exact` | `cf55ea8e` | `pop_exact_h10_fbridge` cell ‡ | es_r2_exact: share 0.272 (honest-ref 0.272), blocks 151, forks 666, sw 0, health ok |
| `20260927_130323_pop_exact_h10_fbridge_rep__es_r2_exact` | `cf55ea8e` | `pop_exact_h10_fbridge_rep` cell ‡ | es_r2_exact: share 0.366 (honest-ref 0.366), blocks 161, forks 794, sw 0, health ok |
| `20260927_130344_pop_exact_mid_fbridge__es_exact` | `cf55ea8e` | `pop_exact_mid_fbridge` cell ‡ | es_exact: share 0.181 (honest-ref 0.181), blocks 160, forks 1334, sw 36, health ok |
| `20260927_130404_pop_exact_mid_fbridge_rep__es_exact` | `cf55ea8e` | `pop_exact_mid_fbridge_rep` cell ‡ | es_exact: share 0.236 (honest-ref 0.236), blocks 199, forks 3844, sw 39, health ok |
| `20260927_130344_pop_exact_mid_fbridge__es_r2_exact` | `cf55ea8e` | `pop_exact_mid_fbridge` cell ‡ | es_r2_exact: share 0.328 (honest-ref 0.328), blocks 189, forks 3019, sw 55, health ok |
| `20260927_130404_pop_exact_mid_fbridge_rep__es_r2_exact` | `cf55ea8e` | `pop_exact_mid_fbridge_rep` cell ‡ | es_r2_exact: share 0.291 (honest-ref 0.291), blocks 179, forks 3245, sw 16, health ok |

| `20260929_183459_pop_sop2_h10_reject__es_r2_sop2` | `42cd3715` | `pop_sop2_h10_reject` cell § | es_r2_sop2: share 0.000 (honest-ref 0.000), blocks 100, forks 74, sw 134, health ok |
| `20260929_183148_pop_sop2_h10_reject_rep__es_r2_sop2` | `42cd3715` | `pop_sop2_h10_reject_rep` cell § | es_r2_sop2: share 0.000 (honest-ref 0.000), blocks 108, forks 52, sw 93, health ok |
| `20260929_184200_pop_sop2_h10_reject__es_r2_stock` | `42cd3715` | `pop_sop2_h10_reject` cell § | es_r2_stock: share 0.491 (honest-ref 0.491), blocks 112, forks 620, sw 0, health ok |
| `20260929_184621_pop_sop2_h10_reject_rep__es_r2_stock` | `42cd3715` | `pop_sop2_h10_reject_rep` cell § | es_r2_stock: share 0.500 (honest-ref 0.500), blocks 136, forks 722, sw 0, health ok |
| `20260929_170204_pop_sop2_h10_reject__es_sop2` | `42cd3715` | `pop_sop2_h10_reject` cell § | es_sop2: share 0.000 (honest-ref 0.000), blocks 100, forks 70, sw 134, health ok |
| `20260929_170225_pop_sop2_h10_reject_rep__es_sop2` | `42cd3715` | `pop_sop2_h10_reject_rep` cell § | es_sop2: share 0.000 (honest-ref 0.000), blocks 99, forks 70, sw 138, health ok |
| `20260929_170204_pop_sop2_h10_reject__es_stock` | `42cd3715` | `pop_sop2_h10_reject` cell § | es_stock: share 0.519 (honest-ref 0.519), blocks 135, forks 840, sw 0, health ok |
| `20260929_170225_pop_sop2_h10_reject_rep__es_stock` | `42cd3715` | `pop_sop2_h10_reject_rep` cell § | es_stock: share 0.544 (honest-ref 0.544), blocks 114, forks 861, sw 0, health ok |
| `20260929_170245_pop_exact_h10_reject__es_exact` | `42cd3715` | `pop_exact_h10_reject` cell § | es_exact: share 0.156 (honest-ref 0.156), blocks 109, forks 266, sw 0, health ok |
| `20260929_170305_pop_exact_h10_reject_rep__es_exact` | `42cd3715` | `pop_exact_h10_reject_rep` cell § | es_exact: share 0.256 (honest-ref 0.256), blocks 121, forks 574, sw 0, health ok |
| `20260929_170245_pop_exact_h10_reject__es_r2_exact` | `42cd3715` | `pop_exact_h10_reject` cell § | es_r2_exact: share 0.263 (honest-ref 0.263), blocks 133, forks 458, sw 0, health ok |
| `20260929_170305_pop_exact_h10_reject_rep__es_r2_exact` | `42cd3715` | `pop_exact_h10_reject_rep` cell § | es_r2_exact: share 0.307 (honest-ref 0.307), blocks 137, forks 518, sw 0, health ok |
| `20260929_170325_pop_exact_mid_reject__es_exact` | `42cd3715` | `pop_exact_mid_reject` cell § | es_exact: share 0.223 (honest-ref 0.213), blocks 175, forks 1669, sw 41, health ok |
| `20260929_170345_pop_exact_mid_reject_rep__es_exact` | `42cd3715` | `pop_exact_mid_reject_rep` cell § | es_exact: share 0.229 (honest-ref 0.229), blocks 188, forks 1860, sw 28, health ok |
| `20260929_170325_pop_exact_mid_reject__es_r2_exact` | `42cd3715` | `pop_exact_mid_reject` cell § | es_r2_exact: share 0.353 (honest-ref 0.353), blocks 184, forks 2419, sw 45, health ok |
| `20260929_170345_pop_exact_mid_reject_rep__es_r2_exact` | `42cd3715` | `pop_exact_mid_reject_rep` cell § | es_r2_exact: share 0.419 (honest-ref 0.419), blocks 191, forks 2731, sw 35, health ok |

Reproduce any row:

```bash
git checkout <commit> && nice -n10 ./run_sim.sh --config <config> --name <label> --no-monitor
venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run>
```

§ as ‡ plus the alt-flush RPC (selfish-relay patch sha `4d4c86d6…`, installed 2026-09-29); micro § rows graft the regenerated `h10` preset (`4e02491e`). See results doc §8.

‡ daemon `monerod-sim` with review fixes F5c+F5d (pop patch sha `9492d7cb…`, installed 2026-09-26T20:30Z). See `docs/20260926_exact_uncles_and_sop_controls.md` for these and the micro exact / SoP-control rows.

† daemon `monerod-sim` built 2026-09-26T12:41Z from the patch stack at `4793ba5f`; analysis re-run at `703bdffe` (`--reanalyze`). See `docs/20260926_sop_h10_rerun.md`.

## 8. Planned work

1. ~~ω-sweep under v13 semantics~~ ✅ done 2026-09-22 (E3 above, finding 7):
   payoff thresholded at island/honest parity; R_mod rejected sub-majority;
   majority replicated twice; split has fat variance.
2. ~~Matrix runner~~ ✅ shipped 2026-09-22 (`scripts/selfish_matrix.py`,
   SELFISH_MINING §11): strategy × countermeasure × α specs → paired runs
   → one table with resume markers and commit provenance.
3. **Countermeasure campaign (E4)**: Publish-or-Perish fork-choice core
   shipped as `patches/monero-sim-pop.patch` (§12) and **pilot-confirmed
   2026-09-22** (finding 8; full table in
   `docs/20260922_pop_countermeasure_design.md`): 0.492 → 0.022 at α=0.4,
   honest control clean, damage/detection rise. Next: +uncles per MRL #144
   (isolates the uncle term), the det-tie axis, Share-or-Perish workshares
   (MRL #146), detective mining as an agent; the full
   strategy × countermeasure × α matrix on the 256-thread/1 TB machine
   ("senior").
4. Error bars: repeats exist at α_eff=0.467 and 0.667 (n=2 each); any
   quantitative split claim needs n≥3. The honest-baseline control was NOT
   re-run under v13 — v13's changes (mirror fork-gate, feed cap) only bind
   during withholding, which `strategy: honest` never does, so the v3-era
   honest control remains valid for plumbing neutrality.
5. **Published-work frontier (gap analysis 2026-09-25, vs the 20-paper
   manifest + MRL issues):**
   - **Stubborn × countermeasures** (next): Nayak's three stubborn
     variants shipped in phase 2 but never faced PoP/SoP — the natural
     completion of the E4 story (one matrix spec).
   - **Monero-faithful topology**: build the sim GML from Gao et al.
     2025's measured P2P topology (replacing CAIDA) — upgrades every
     scale result incl. the senior leg.
   - **Kopyciok et al. 2025 anomalous-peer detection**: network-layer
     detectability of our attackers (composes with E2's block-layer MSB
     calibration; sim telemetry already sufficient).
   - **Shi et al. NDSS 2025 eclipse mechanics**: drive the real
     peerlist-poisoning attack (E3 assumed a successful eclipse by
     configuration — the load-bearing assumption in the 0.559 result).
   - **Gervais et al. 2016**: propagation-vs-security curves vs
     faithful monerod (topology/delay sweep).
   - Blocked on the transaction layer: MRL #145 (lucky transactions,
     parked day one), Carlsten 2016 / Gong 2022 (fee markets), Jiang &
     Zhang 2024 (double-spends); Kawaguchi & Noda 2021 needs two
     networks. Covered/excluded: Lee&Kim, Li, Nayak-composition, #144,
     #146, Purkovic (covert-ASIC economics, not a selfish variant),
     Garay/Budish/Miller/Franzoni (not simulation-shaped).
   - Standing: n=2 repeats of the pop_sop2 verdict; the senior leg
     (user-run; spec swap + a fixed-difficulty selfish_scaled variant);
     the covert-bridge freeze defect.
