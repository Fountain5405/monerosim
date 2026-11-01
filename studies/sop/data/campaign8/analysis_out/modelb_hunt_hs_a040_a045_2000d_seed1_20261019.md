# Model B deep-reorg hunter: release_depth=10, days=2000.0 (fixed-rate), seed=1
# SoP attacker uses honest shares as the slot rule allows: its first block embeds the honest shares found before either side's first block, and it restarts level after a give-up.
# Every reveal orphans >= release_depth honest blocks. Rates are per CANONICAL day/year; the object give-up (oN) is SoP-only.

| alpha | rule | give-up | reveals | canon days | #>=10 | per day | per year | days per | mean reorg | max reorg | revenue share | orphan frac |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.4 | sop | d1 | 336 | 1200.9 | 336 | 0.2798 | 102.189 | 3.57 | 11.40 | 20 | 0.0064 | 0.9903 |
| 0.4 | sop | d2 | 483 | 1201.3 | 483 | 0.4020 | 146.848 | 2.49 | 11.42 | 20 | 0.0087 | 0.9869 |
| 0.4 | sop | o5 | 329 | 1196.9 | 329 | 0.2749 | 100.402 | 3.64 | 10.34 | 16 | 0.0025 | 0.9962 |
| 0.45 | sop | d1 | 5907 | 1143.8 | 5907 | 5.1642 | 1886.209 | 0.19 | 12.08 | 50 | 0.1253 | 0.8406 |
| 0.45 | sop | d2 | 7030 | 1143.7 | 7030 | 6.1466 | 2245.028 | 0.16 | 12.16 | 50 | 0.1423 | 0.8190 |
| 0.45 | sop | o5 | 8264 | 1082.7 | 8264 | 7.6327 | 2787.848 | 0.13 | 10.47 | 19 | 0.0953 | 0.8852 |

(elapsed: 34.4s)
