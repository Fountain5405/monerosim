# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.4 | 3 | sop | True | 23369 | 1270.2 | 18.3977 | 16.238 | 3.360 | 18 | 14878 | 189 | 54.3470 | 0.1423 | 0.7742 |
| 0.4 | 3 | sop | False | 0 | 1198.5 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.4 | 3 | stock | False | 175932 | 1530.4 | 114.9607 | 122.247 | 1.284 | 13 | 12472 | 62 | 14.7974 | 0.4218 | 0.1933 |
| 0.4 | 3 | sop | True + honest shares | 34901 | 1290.6 | 27.0424 | 24.251 | 3.102 | 18 | 20200 | 195 | 55.1864 | 0.1878 | 0.6971 |
| 0.4 | 5 | sop | True | 20630 | 1244.8 | 16.5732 | 14.335 | 3.941 | 21 | 14573 | 439 | 128.8138 | 0.1279 | 0.8011 |
| 0.4 | 5 | sop | False | 0 | 1198.5 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.4 | 5 | stock | False | 145366 | 1469.7 | 98.9053 | 101.008 | 1.538 | 34 | 15569 | 1409 | 350.1532 | 0.3958 | 0.2732 |
| 0.4 | 5 | sop | True + honest shares | 30973 | 1257.3 | 24.6351 | 21.522 | 3.649 | 19 | 20258 | 453 | 131.6011 | 0.1716 | 0.7304 |

(elapsed: 59.6s)
