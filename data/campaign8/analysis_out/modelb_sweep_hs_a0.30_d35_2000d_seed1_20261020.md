# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.3 | 3 | sop | True | 1749 | 1404.4 | 1.2453 | 1.215 | 2.707 | 9 | 943 | 0 | 0.0000 | 0.0088 | 0.9794 |
| 0.3 | 3 | sop | False | 0 | 1398.6 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.3 | 3 | stock | False | 118507 | 1599.5 | 74.0912 | 82.345 | 1.223 | 14 | 6416 | 14 | 3.1970 | 0.2514 | 0.3300 |
| 0.3 | 3 | sop | True + honest shares | 5663 | 1411.7 | 4.0114 | 3.935 | 2.293 | 9 | 2217 | 0 | 0.0000 | 0.0220 | 0.9481 |
| 0.3 | 5 | sop | True | 1551 | 1402.6 | 1.1058 | 1.078 | 3.164 | 9 | 949 | 0 | 0.0000 | 0.0077 | 0.9820 |
| 0.3 | 5 | sop | False | 0 | 1398.6 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.3 | 5 | stock | False | 95646 | 1560.1 | 61.3084 | 66.460 | 1.329 | 22 | 6971 | 244 | 57.1259 | 0.2166 | 0.4369 |
| 0.3 | 5 | sop | True + honest shares | 4793 | 1407.4 | 3.4055 | 3.330 | 2.682 | 9 | 2284 | 0 | 0.0000 | 0.0189 | 0.9556 |

(elapsed: 56.0s)
