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

Apparatus: the matrix runner (§3) + three flag-gated `monerod-sim` PoP
modes (`docs/20260922_pop_countermeasure_design.md` pre-registers every
prediction before its run). All cells 6 h, same seed, α=0.4, flags on the
honest miners only (the covert bridge keeps stock rules — attackers don't
upgrade).

**Full readout (attacker canonical share; honest controls in text):**

| strategy | stock | pop-core (random tie) | pop-core (det tie) | +uncles deviated (random/det) | +uncles EXACT (det) |
|---|---|---|---|---|---|
| ES (textbook) | 0.492 | 0.022, 0.123 | 0.244, 0.296 | 0.024 / 0.337 | **0.134** |
| conservative lead-2 | 0.309 | — | — | — | — |
| honest control (share vs α=0.4) | 0.397 | 0.408 | — | 0.402 | 0.322 ⚠️ |

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
4. **Uncles are a no-op against ES at micro scale** (0.024 ≈ core) but
   **halve the det-tie leak in the EXACT form** (0.134 vs core's 0.27
   mean, and vs 0.337 for the DEVIATED node-local variant — the variant
   A/B against pre-registration). Only 3 embeddings occurred per 6 h: two
   honest miners essentially never race. The honest_exact control dipped
   (0.322, orphan 2.5×) — the mechanism starves and what little it does
   shows as inter-node weight disagreement. Scale (rung 4, in flight:
   6 miners + 16 relays mid; 12+32 committed for the senior box) is the
   variable that settles it.
5. **Vandalism persists under every PoP variant** (net orphan 0.31–0.45
   vs 0.312 stock attack; MSB detectability stays high, z +7.4 to +14.9):
   PoP removes the profit, not the DoS.

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
8. **Publish-or-Perish's fork-choice core alone nearly eliminates ES
   revenue at Monero speeds** (E4 pilot, pre-registered): attacker share
   0.492 → 0.022 at α=0.4 with the attacker orphaning 97% of its finds
   (73/77 fork decisions KEEP honest), while the honest control is
   unaffected (0.408 ≈ α, orphan 0.02, throughput unchanged). But the
   attack's network damage RISES under PoP (orphan 0.312 → 0.447) and its
   MSB detectability too (+7.9 → +14.9): PoP removes the profit, not the
   vandalism — incentive-removal and DoS-resilience are separate
   countermeasure properties.

## 6. Limitations

- Micro-topology (8–13 hosts, 2–5 miners): honest-fragmentation effects at
  larger scale are unmeasured here; single runs per point except where
  repeats are noted (n=2 at α_eff 0.467 and 0.667),
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

(PoP cells ran the 5-patch monerod-sim, build 2026-09-22T13:05Z, flag ON
on the honest miners only; matrix table at `matrix_runs/pop_pilot/table.md`
— gitignored workdir, rows reproduced here and in the design doc.)

(v6 was killed early — the `mine_after_height` gate held a victim whose
daemon was stuck at height 1 by the then-undiagnosed count bug; no result.)

Reproduce any row:

```bash
git checkout <commit> && nice -n10 ./run_sim.sh --config <config> --name <label> --no-monitor
venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run>
```

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
