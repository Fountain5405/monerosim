# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.33 | 1 | sop | True | 3602 | 1355.0 | 2.6583 | 2.503 | 2.173 | 8 | 1174 | 0 | 0.0000 | 0.0204 | 0.9583 |
| 0.33 | 1 | sop | False | 0 | 1338.3 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.33 | 1 | stock | False | 153177 | 1614.4 | 94.8821 | 106.435 | 1.000 | 1 | 0 | 0 | 0.0000 | 0.3028 | 0.2599 |
| 0.33 | 1 | sop | True + honest shares | 8679 | 1370.1 | 6.3345 | 6.031 | 1.856 | 9 | 1930 | 0 | 0.0000 | 0.0395 | 0.9180 |
| 0.33 | 2 | sop | True | 4251 | 1354.4 | 3.1386 | 2.954 | 2.559 | 9 | 1937 | 0 | 0.0000 | 0.0231 | 0.9527 |
| 0.33 | 2 | sop | False | 0 | 1338.3 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.33 | 2 | stock | False | 148808 | 1600.2 | 92.9915 | 103.400 | 1.131 | 8 | 3311 | 0 | 0.0000 | 0.3097 | 0.2497 |
| 0.33 | 2 | sop | True + honest shares | 10022 | 1368.1 | 7.3254 | 6.964 | 2.238 | 9 | 3428 | 0 | 0.0000 | 0.0446 | 0.9077 |

(elapsed: 57.1s)
