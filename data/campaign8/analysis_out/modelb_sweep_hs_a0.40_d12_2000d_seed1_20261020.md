# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.4 | 1 | sop | True | 20894 | 1292.5 | 16.1661 | 14.518 | 2.583 | 18 | 8975 | 79 | 22.3255 | 0.1307 | 0.7890 |
| 0.4 | 1 | sop | False | 0 | 1198.5 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.4 | 1 | stock | False | 193411 | 1579.8 | 122.4312 | 134.392 | 1.000 | 1 | 0 | 0 | 0.0000 | 0.4114 | 0.1880 |
| 0.4 | 1 | sop | True + honest shares | 30646 | 1321.0 | 23.1997 | 21.294 | 2.345 | 18 | 11054 | 78 | 21.5672 | 0.1682 | 0.7223 |
| 0.4 | 2 | sop | True | 23295 | 1284.3 | 18.1389 | 16.187 | 2.981 | 20 | 12761 | 134 | 38.1103 | 0.1419 | 0.7724 |
| 0.4 | 2 | sop | False | 0 | 1198.5 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.4 | 2 | stock | False | 189760 | 1561.0 | 121.5613 | 131.855 | 1.141 | 10 | 4919 | 1 | 0.2340 | 0.4249 | 0.1712 |
| 0.4 | 2 | sop | True + honest shares | 34594 | 1310.1 | 26.4062 | 24.038 | 2.741 | 18 | 16657 | 131 | 36.5231 | 0.1857 | 0.6961 |

(elapsed: 57.1s)
