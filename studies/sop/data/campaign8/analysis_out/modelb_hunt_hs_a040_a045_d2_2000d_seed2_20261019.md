# Model B deep-reorg hunter: release_depth=10, days=2000.0 (fixed-rate), seed=2
# SoP attacker uses honest shares as the slot rule allows: its first block embeds the honest shares found before either side's first block, and it restarts level after a give-up.
# Every reveal orphans >= release_depth honest blocks. Rates are per CANONICAL day/year; the object give-up (oN) is SoP-only.

| alpha | rule | give-up | reveals | canon days | #>=10 | per day | per year | days per | mean reorg | max reorg | revenue share | orphan frac |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.4 | sop | d2 | 483 | 1204.5 | 483 | 0.4010 | 146.460 | 2.49 | 11.37 | 24 | 0.0087 | 0.9869 |
| 0.45 | sop | d2 | 7048 | 1145.7 | 7048 | 6.1517 | 2246.916 | 0.16 | 12.10 | 46 | 0.1416 | 0.8193 |

(elapsed: 15.5s)
