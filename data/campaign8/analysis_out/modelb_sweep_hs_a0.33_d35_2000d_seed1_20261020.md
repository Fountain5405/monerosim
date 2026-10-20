# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.33 | 3 | sop | True | 4392 | 1352.3 | 3.2478 | 3.052 | 2.898 | 9 | 2514 | 0 | 0.0000 | 0.0234 | 0.9520 |
| 0.33 | 3 | sop | False | 0 | 1338.3 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.33 | 3 | stock | False | 135729 | 1575.2 | 86.1686 | 94.312 | 1.245 | 13 | 8169 | 28 | 6.4927 | 0.2994 | 0.2861 |
| 0.33 | 3 | sop | True + honest shares | 9913 | 1363.0 | 7.2727 | 6.888 | 2.566 | 9 | 4620 | 0 | 0.0000 | 0.0441 | 0.9091 |
| 0.33 | 5 | sop | True | 3788 | 1347.5 | 2.8112 | 2.632 | 3.395 | 12 | 2480 | 3 | 0.8132 | 0.0200 | 0.9591 |
| 0.33 | 5 | sop | False | 0 | 1338.3 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.33 | 5 | stock | False | 109811 | 1528.7 | 71.8348 | 76.302 | 1.390 | 24 | 9235 | 454 | 108.4764 | 0.2632 | 0.3908 |
| 0.33 | 5 | sop | True + honest shares | 8446 | 1354.3 | 6.2363 | 5.869 | 3.009 | 12 | 4647 | 4 | 1.0788 | 0.0379 | 0.9223 |

(elapsed: 56.7s)
