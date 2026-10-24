# Share-or-Perish (MRL #146) under the 2026-10-20 revision: v4 campaign results (2026-10-21 to 2026-10-22)

First campaign on the rule as revised 2026-10-20 (log v4; the issue body has
not changed since — edit history checked 2026-10-22). Companion to
`docs/20261019_sop_campaign8_results.md`, which measured the 2026-10-15 text
(log v3) on the same cells. Design: `docs/superpowers/specs/2026-10-21-sop-rev20261020-design.md`;
conformance: `docs/20260930_sop_conformance.md` (revised 2026-10-20 section).

> **Caveat (2026-10-23):** the attacker in every run below gives up only
> when honest leads by `give_up_depth` *blocks*; past the window and behind
> by weight its block count keeps pace with honest's, so it sat stranded
> (no reveal, no concession, every block orphaned) for 17-27 h of each 72 h
> alpha-0.45 run. Measured 2026-10-23 (`sop_v4_o5_72h`, two 72 h draws):
> the same cell with the objects give-up (`give_up_objects 5`) earns
> **0.209 and 0.210** against the 0.054 below, with 0 h stranded; the race
> model says 0.36. The collapse below is therefore mostly the attacker's
> give-up rule, not the revision alone; see
> `docs/20261023_sop_scale_n300_smoke.md` §3.1.

## Summary

- **The revised rule collapses the attack at every alpha tested.** Attacker
  share of blocks over 72 h, one run per cell: 0.000 at alpha 1/3 (built, d2),
  0.025 at 0.40 (hs, d2), 0.054 at 0.45 (hs, d5), 0.078 at 0.45 (hs, d2).
  The same cells under the old rule: 0.019-0.036, 0.169, 0.503-0.520
  (the 0.45 d2 cell was not run under v3). The gap is far outside run noise.
- **Per-run noise is ~±0.03 at the 0.10 cell** (n=2 per arm, see §4): single
  72 h runs do not resolve fine comparisons; the headline collapse does not
  need them to.
- **The reveal-test finding:** an attacker that counts its own tip shares in
  its reveal test (A2) makes reveals the bridge rejects, because A3 delivers
  those shares only after the switch and the fork choice runs on block
  arrival only (author, MRL meeting 2026-10-21). Excluding them
  (`count_own_tip_shares 'false'`) eliminates the rejections — but changes
  the attacker's share not at all at n=2 (§4).

## 1. Builds and specs

- v4 build: `5cc8df48` (implementation) + `d8cc1d45` (slot collision,
  first-seen per slot) + `22f0c09c` (merge of origin/main); binary built
  2026-10-21 19:27Z. Campaign spec `test_configs/matrix/sop_v4_h10_72h.yaml`
  (`ce767c3d`); noown follow-up `sop_v4_noown_72h.yaml` + attacker flag
  (`89047312`); second-sample specs (`928dc193`). All runs used seed 27791,
  12 daemons, stop 72 h; runs are not seed-reproducible.
- Every run gated by `check_run.py` (gitignored, `.claude/campaign9/`):
  oracle, pool-rule, probes (R3 share-arrival flips, R4 alt tips), A3
  delivery counts, alt-share pooling, lateness, embed, reveal stats. All
  runs PASS; the alpha-1/3 cell is WARN only because the attacker never
  revealed (A3 untested). **Oracle: 0 mismatches on all 12 nodes in every
  run**, including all second samples.

## 2. Attacker revenue

| cell (72 h) | v4 share | blocks | reveals (deliv./rej.) | race model | old rule (v3) |
|---|---|---|---|---|---|
| a033 built d2 | 0.000 | 1979 | 0 | 0.0004-0.0009 | 0.019-0.036 |
| a040 hs d2 | 0.025 | 1899 | 23 (12/11) | 0.013-0.023 | 0.169 |
| a045 hs d5 | 0.054 | 1886 | 54 (31/23) | 0.052-0.073 | 0.503-0.520 |
| a045 hs d2 | 0.078 | 1893 | 67 (37/30) | 0.076-0.105 | not run |
| a045 hs d2, 2nd | 0.113 | 1934 | 77 (52/25) | | |
| a045 hs d2 noown | 0.112 | 1926 | 41 (41/0) | 0.094 (noown preset) | |
| a045 hs d2 noown, 2nd | 0.087 | 1930 | 37 (36/1) | | |

Attacker orphan rates 0.85-0.96 (the 999 attacker blocks at alpha 1/3 were
100% orphaned); network orphan rate ~0.40-0.43 at alpha 0.45. "FAIL (3)" in
the matrix tables is the Eyal-Sirer verdict set, which SoP is expected to
fail. Race model: `scripts/sop_race_model.py` 20-Oct preset, 2000 d,
embeds/+honest-shares rows; the model has no network delay and (as §4 shows)
no rejected-reveal mechanism.

## 3. Rule checks (all runs)

- `--pool-rule all` (every pooled share counted, the R2 alternative reading)
  changes 0 outcomes in any run.
- R3 probe: a later-arriving share would have flipped 77 of 2358 decisions
  (3.3%) in the a045 d5 run; 0 flips at alpha 1/3. The probe is
  unit-tested only, not validated against ground truth.
- R4: `alt_tips >= 2` in most decisions, but it counts stale one-block
  orphans (network orphan rate 0.40), so it overstates third-chain
  contention; a pairwise-against-every-alt-tip probe is the honest version
  (not built).
- The alternate-share path (D4) ran: honest-001 pooled tip-0 shares in every
  cell (38/56/81/45/37/57/40 across the table's runs).

## 4. The reveal test: rejected reveals, and n=2

The attacker's reveal test (A2) counted its own miner's tip shares on the
private tip; A3 delivers them only after the bridge has switched. Under
"fork choice runs only on a new block or chain" (author, MRL meeting
2026-10-21) those shares can never count at reveal time, so the bridge
sometimes kept main, rejected the reveal, and the attacker popped its
private branch: 30/67 and 25/77 rejections in the two counting-attacker
runs. `count_own_tip_shares 'false'` (commit `89047312`, default 'true'
preserves the campaign behavior) drops them from the test: rejections
collapse to 0/41 and 1/37, tip-share deliveries rise (21 and 11 vs 8).

**The share does not move.** Counting {0.078, 0.113}, mean 0.096; noown
{0.112, 0.087}, mean 0.100 — fully overlapping at n=2 per arm. The rejected
branches were genuine losers (that is why the bridge rejected them); the
counting attacker's extra, occasionally-forced reveals and the noown
attacker's fewer, always-accepted ones net out the same. The race model's
predicted arm difference (-0.011, preset `20261020_noown` vs `20261020`) is
also inside this noise, so the model is contradicted by nothing here — but
it cannot represent the mechanism at all.

Per-run noise at this cell is therefore ~±0.03 around 0.10: single runs
cannot rank attackers this close, and any future fine comparison (rule
variants, w/k sweeps, learned policies) needs multiple samples per cell.

## 5. Not established

- Any share difference between the counting and noown attackers (§4).
- Fine ordering among the n=1 cells (0.025 vs 0.054): each is one run;
  noise presumably scales with the share, but only the 0.10 cell is measured.
- Whether the model's central values hold at other cells (it sat below the
  sim on cell 4, above it on noown, both within noise).
- How much of the alpha-0.45 collapse is the block-depth give-up: the
  attacker was stranded 17-27 h per run (2026-10-23 caveat above).
- The scale question: all of the above is 12 daemons. `sop_scale_n1000`
  (1000 nodes, 300-node smoke first) is the pending test of the same rule
  at realistic fan-out.

## 6. Reproduction

- Specs: `test_configs/matrix/sop_v4_h10_72h.yaml`, `sop_v4_noown_72h.yaml`,
  `sop_v4_h10_72h_s2.yaml`, `sop_v4_noown_72h_s2.yaml` (runs are not
  seed-reproducible; same seed = independent sample).
- Per-run tables and configs: `matrix_runs/<spec>/`; archived runs under
  `archived_runs/` (names in each cell JSON). Check outputs:
  `.claude/campaign9/<run>/summary.txt` and the `queue.log` timeline
  (gitignored, on-disk only).
- Model sweeps: `data/campaign8/analysis_out/modelb_sweep_rev20261020.md`
  and `modelb_sweep_rev20261020_noown.md` (untracked; regenerate with
  `scripts/sop_race_model.py sweep --rule-version 20261020[_noown]
  --honest-shares --alphas 0.33 0.40 0.45 --ds 2 5 --days 2000 --seed 1`).
- Campaign automation: `.claude/campaign9/` (chain, queue, check_run,
  status, followup, repeats runner), gitignored.
