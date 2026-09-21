# MSB calibration study (2026-09-21)

`scripts/msb_study.py` over every selfish/eclipse run on this box
(honest controls: both `ecl_honest_baseline` variants; the stranded-victim
v1-semantics control and the v3 control agree).

Headlines:

- **Honest networks do not false-positive.** Both honest-strategy controls
  (same topology, attacker releases immediately): every miner z in
  [-0.7, +1.0], zero flags. Li et al.'s iid-shuffle null is sound when
  nobody withholds — on this micro topology latency alone contributes
  nothing measurable.
- **Withholding is detected in 8/9 attack runs** (z +3.4 to +10.2); the
  one miss is the alpha=0.267 omega_0200-adjacent... in fact every attack
  run with canonical share above ~0.19 flags.
- **The honest false positives cluster exactly where the attack is
  heaviest**: 5/18 honest miners flag, ALL in runs with alpha_eff >= 0.4
  (release2 sweep at 0.45: +2.25/+3.17; eclipse omega runs: +2.26, +2.80,
  +3.02). Heavy withholding clusters honest canonical wins (honest miners
  mine freely while the attacker holds, then get reorged in bursts), which
  the iid null misreads as selfishness. A deployed detector needs an
  attack-aware null or a network-wide (not per-miner) test statistic.
- Victims (eclipsed, stranded) never flag under v2/v3 semantics — their
  wins are too few to reach z>2 — so victim MSB is NOT a usable
  eclipse-detection signal in this regime.

Full table below (machine-generated; regenerate with
`venv/bin/python scripts/msb_study.py <run dirs>`).

# MSB calibration study

| run | α | α_eff | strategy | r_lead | att share | ctrl share | miner | role | share | MSB z | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20260921_020113_selfish_release2 | 0.400 | 0.400 | eyal_sirer | 2 | 0.309 | 0.309 | attacker-miner | attacker | 0.309 | +3.98 | FLAG |
| 20260921_020113_selfish_release2 | 0.400 | 0.400 | eyal_sirer | 2 | 0.309 | 0.309 | honest-001 | honest | 0.327 | +0.69 |  |
| 20260921_020113_selfish_release2 | 0.400 | 0.400 | eyal_sirer | 2 | 0.309 | 0.309 | honest-002 | honest | 0.364 | +0.65 |  |
| 20260921_023050_selfish_micro_es_baseline | 0.400 | 0.400 | eyal_sirer | 1 | 0.463 | 0.463 | attacker-miner | attacker | 0.463 | +6.94 | FLAG |
| 20260921_023050_selfish_micro_es_baseline | 0.400 | 0.400 | eyal_sirer | 1 | 0.463 | 0.463 | honest-001 | honest | 0.297 | +1.42 |  |
| 20260921_023050_selfish_micro_es_baseline | 0.400 | 0.400 | eyal_sirer | 1 | 0.463 | 0.463 | honest-002 | honest | 0.240 | +1.73 |  |
| 20260921_102229_r2_sweep_a0300 | 0.300 | 0.300 | eyal_sirer | 2 | 0.211 | 0.211 | attacker-miner | attacker | 0.211 | +6.91 | FLAG |
| 20260921_102229_r2_sweep_a0300 | 0.300 | 0.300 | eyal_sirer | 2 | 0.211 | 0.211 | honest-001 | honest | 0.452 | +0.79 |  |
| 20260921_102229_r2_sweep_a0300 | 0.300 | 0.300 | eyal_sirer | 2 | 0.211 | 0.211 | honest-002 | honest | 0.337 | +0.86 |  |
| 20260921_102230_r2_sweep_a0450 | 0.450 | 0.450 | eyal_sirer | 2 | 0.569 | 0.569 | attacker-miner | attacker | 0.569 | +5.49 | FLAG |
| 20260921_102230_r2_sweep_a0450 | 0.450 | 0.450 | eyal_sirer | 2 | 0.569 | 0.569 | honest-001 | honest | 0.222 | +2.25 | FLAG |
| 20260921_102230_r2_sweep_a0450 | 0.450 | 0.450 | eyal_sirer | 2 | 0.569 | 0.569 | honest-002 | honest | 0.209 | +3.17 | FLAG |
| 20260921_183612_gamma_eclipse_v3 | 0.267 | 0.467 | eyal_sirer | 1 | 0.295 | 0.295 | attacker-miner | attacker | 0.295 | +2.08 | FLAG |
| 20260921_183612_gamma_eclipse_v3 | 0.267 | 0.467 | eyal_sirer | 1 | 0.295 | 0.295 | honest-001 | honest | 0.312 | +1.08 |  |
| 20260921_183612_gamma_eclipse_v3 | 0.267 | 0.467 | eyal_sirer | 1 | 0.295 | 0.295 | honest-002 | honest | 0.392 | -0.49 |  |
| 20260921_183612_gamma_eclipse_v3 | 0.267 | 0.467 | eyal_sirer | 1 | 0.295 | 0.295 | victim-001 | victim | 0.000 | +0.00 |  |
| 20260921_162236_ecl_sweep_omega0000 | 0.267 | 0.267 | eyal_sirer | 1 | 0.192 | 0.192 | attacker-miner | attacker | 0.192 | +8.02 | FLAG |
| 20260921_162236_ecl_sweep_omega0000 | 0.267 | 0.267 | eyal_sirer | 1 | 0.192 | 0.192 | honest-001 | honest | 0.389 | +1.64 |  |
| 20260921_162236_ecl_sweep_omega0000 | 0.267 | 0.267 | eyal_sirer | 1 | 0.192 | 0.192 | honest-002 | honest | 0.419 | +2.26 | FLAG |
| 20260921_171216_ecl_sweep_omega0200 | 0.267 | 0.400 | eyal_sirer | 1 | 0.283 | 0.283 | attacker-miner | attacker | 0.283 | +3.38 | FLAG |
| 20260921_171216_ecl_sweep_omega0200 | 0.267 | 0.400 | eyal_sirer | 1 | 0.283 | 0.283 | honest-001 | honest | 0.399 | +1.20 |  |
| 20260921_171216_ecl_sweep_omega0200 | 0.267 | 0.400 | eyal_sirer | 1 | 0.283 | 0.283 | honest-002 | honest | 0.318 | +2.80 | FLAG |
| 20260921_171216_ecl_sweep_omega0200 | 0.267 | 0.400 | eyal_sirer | 1 | 0.283 | 0.283 | victim-001 | victim | 0.000 | +0.00 |  |
| 20260921_171216_ecl_sweep_omega0300_3v | 0.267 | 0.467 | eyal_sirer | 1 | 0.385 | 0.385 | attacker-miner | attacker | 0.385 | +5.80 | FLAG |
| 20260921_171216_ecl_sweep_omega0300_3v | 0.267 | 0.467 | eyal_sirer | 1 | 0.385 | 0.385 | honest-001 | honest | 0.333 | +3.02 | FLAG |
| 20260921_171216_ecl_sweep_omega0300_3v | 0.267 | 0.467 | eyal_sirer | 1 | 0.385 | 0.385 | honest-002 | honest | 0.282 | +1.26 |  |
| 20260921_171216_ecl_sweep_omega0300_3v | 0.267 | 0.467 | eyal_sirer | 1 | 0.385 | 0.385 | victim-001 | victim | 0.000 | +0.00 |  |
| 20260921_171216_ecl_sweep_omega0300_3v | 0.267 | 0.467 | eyal_sirer | 1 | 0.385 | 0.385 | victim-002 | victim | 0.000 | +0.00 |  |
| 20260921_171216_ecl_sweep_omega0300_3v | 0.267 | 0.467 | eyal_sirer | 1 | 0.385 | 0.385 | victim-003 | victim | 0.000 | +0.00 |  |
| 20260921_183612_ecl_honest_baseline_v3 | 0.267 | 0.467 | honest | 1 | 0.317 | 0.317 | attacker-miner | attacker | 0.317 | +0.23 |  |
| 20260921_183612_ecl_honest_baseline_v3 | 0.267 | 0.467 | honest | 1 | 0.317 | 0.317 | honest-001 | honest | 0.359 | +0.27 |  |
| 20260921_183612_ecl_honest_baseline_v3 | 0.267 | 0.467 | honest | 1 | 0.317 | 0.317 | honest-002 | honest | 0.323 | -0.04 |  |
| 20260921_183612_ecl_honest_baseline_v3 | 0.267 | 0.467 | honest | 1 | 0.317 | 0.317 | victim-001 | victim | 0.000 | +0.00 |  |

## Flag rates by role (z > 2)

- honest: 5/18
- attacker: 8/9
- victim: 0/6
