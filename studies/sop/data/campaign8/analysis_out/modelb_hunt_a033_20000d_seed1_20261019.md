# Model B deep-reorg hunter: release_depth=10, days=20000.0 (fixed-rate), seed=1
# Every reveal orphans >= release_depth honest blocks. Rates are per CANONICAL day/year; the object give-up (oN) is SoP-only.

| alpha | rule | give-up | reveals | canon days | #>=10 | per day | per year | days per | mean reorg | max reorg | revenue share | orphan frac |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.33 | sop | d1 | 8 | 13402.9 | 8 | 0.0006 | 0.218 | 1675.36 | 10.12 | 11 | 0.0000 | 1.0000 |
| 0.33 | sop | d2 | 13 | 13402.9 | 13 | 0.0010 | 0.354 | 1031.00 | 10.31 | 12 | 0.0000 | 1.0000 |
| 0.33 | sop | o5 | 0 | 13402.9 | 0 | 0.0000 | 0.000 | inf | 0.00 | 0 | 0.0000 | 1.0000 |
| 0.33 | stock | d1 | 63003 | 13606.8 | 63003 | 4.6303 | 1691.201 | 0.22 | 10.00 | 10 | 0.0793 | 0.8365 |
| 0.33 | stock | d2 | 79716 | 13629.0 | 79716 | 5.8490 | 2136.346 | 0.17 | 10.07 | 15 | 0.0984 | 0.7968 |

(elapsed: 336.5s)
