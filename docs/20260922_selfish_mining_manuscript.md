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

### E3 — Eclipse composition (RQ3) ✅ mechanics closed at α_eff=0.667

`docs/20260921_selfish_eclipse_results.md` (the full v1→v13 arc, seven
localized defects). Headline results: naive mirror/pull loses to monerod
first-seen semantics at every level (v1–v3); eclipse-as-DoS alone moves the
attacker 0.192→0.385 (ω=0 vs 0.2); ancestor-verified, adoption-committed
releases took the attacker from 0.000 to 0.463 (v11); and with the full
lifecycle (v13: mirror gated at the fork + honest feed capped at the fork)
the composition CONTROLS the majority: **0.559 controlled share, victim
recruitment at 0.213 canonical, γ still 0.000**. Recruitment pays the
coalition, not the attacker (its solo share falls to 0.346 with 0.309
self-orphans), and network damage stays severe (orphan rate 0.52) in every
variant — the harm/profit asymmetry extends to the eclipse regime. The
monerod-API findings below are themselves contributions.

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

## 6. Limitations

- Micro-topology (8–13 hosts, 2–5 miners): honest-fragmentation effects at
  larger scale are unmeasured here; single runs per point,
  `native_preemption: true` (share σ≈0.05); A/A byte-determinism requires
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

(v6 was killed early — the `mine_after_height` gate held a victim whose
daemon was stuck at height 1 by the then-undiagnosed count bug; no result.)

Reproduce any row:

```bash
git checkout <commit> && nice -n10 ./run_sim.sh --config <config> --name <label> --no-monitor
venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run>
```

## 8. Planned work

1. Close E3's remaining science: ω-sweep re-run under working recruitment
   (v13 semantics) including the sub-majority frontier (α_eff < 1/2) where
   the theory says the composition should become marginal; repeats for
   error bars.
2. The matrix runner (`scripts/selfish_matrix.py`): strategy ×
   countermeasure × α cells → configs → paired runs → one table.
3. First countermeasure patches: Publish-or-Perish and undercutting
   avoidance as flag-gated `monerod-sim` patches; detective mining as an
   agent. Large parallel matrices move to the 256-thread/1 TB machine.
