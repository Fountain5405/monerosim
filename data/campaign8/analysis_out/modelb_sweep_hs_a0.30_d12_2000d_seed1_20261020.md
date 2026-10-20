# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.3 | 1 | sop | True | 1310 | 1405.0 | 0.9324 | 0.910 | 2.002 | 8 | 372 | 0 | 0.0000 | 0.0071 | 0.9834 |
| 0.3 | 1 | sop | False | 0 | 1398.6 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.3 | 1 | stock | False | 134881 | 1633.5 | 82.5721 | 93.722 | 1.000 | 1 | 0 | 0 | 0.0000 | 0.2585 | 0.2966 |
| 0.3 | 1 | sop | True + honest shares | 4910 | 1415.2 | 3.4695 | 3.412 | 1.621 | 8 | 749 | 0 | 0.0000 | 0.0195 | 0.9540 |
| 0.3 | 2 | sop | True | 1687 | 1405.2 | 1.2006 | 1.172 | 2.388 | 8 | 692 | 0 | 0.0000 | 0.0086 | 0.9798 |
| 0.3 | 2 | sop | False | 0 | 1398.6 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.3 | 2 | stock | False | 130429 | 1621.1 | 80.4559 | 90.629 | 1.124 | 7 | 2655 | 0 | 0.0000 | 0.2628 | 0.2900 |
| 0.3 | 2 | sop | True + honest shares | 5729 | 1414.5 | 4.0503 | 3.981 | 1.995 | 8 | 1515 | 0 | 0.0000 | 0.0224 | 0.9472 |

(elapsed: 54.2s)
