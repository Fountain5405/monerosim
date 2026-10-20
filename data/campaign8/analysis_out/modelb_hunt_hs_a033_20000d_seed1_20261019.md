# Model B deep-reorg hunter: release_depth=10, days=20000.0 (fixed-rate), seed=1
# SoP attacker uses honest shares as the slot rule allows: its first block embeds the honest shares found before either side's first block, and it restarts level after a give-up.
# Every reveal orphans >= release_depth honest blocks. Rates are per CANONICAL day/year; the object give-up (oN) is SoP-only.

| alpha | rule | give-up | reveals | canon days | #>=10 | per day | per year | days per | mean reorg | max reorg | revenue share | orphan frac |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.33 | sop | d1 | 13 | 13402.9 | 13 | 0.0010 | 0.354 | 1031.00 | 10.31 | 12 | 0.0000 | 1.0000 |
| 0.33 | sop | d2 | 24 | 13403.0 | 24 | 0.0018 | 0.654 | 558.46 | 10.33 | 12 | 0.0000 | 0.9999 |
| 0.33 | sop | o5 | 7 | 13402.8 | 7 | 0.0005 | 0.191 | 1914.68 | 10.14 | 11 | 0.0000 | 1.0000 |

(elapsed: 203.5s)
