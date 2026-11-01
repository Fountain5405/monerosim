# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.45 | 1 | sop | True | 52913 | 1326.8 | 39.8806 | 36.767 | 2.678 | 35 | 23189 | 539 | 148.3811 | 0.3195 | 0.5285 |
| 0.45 | 1 | sop | False | 0 | 1099.7 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.45 | 1 | stock | False | 218511 | 1564.0 | 139.7132 | 151.833 | 1.000 | 1 | 0 | 0 | 0.0000 | 0.4909 | 0.1461 |
| 0.45 | 1 | sop | True + honest shares | 64095 | 1354.9 | 47.3056 | 44.537 | 2.456 | 35 | 24698 | 420 | 113.2213 | 0.3498 | 0.4730 |
| 0.45 | 2 | sop | True | 59747 | 1308.0 | 45.6795 | 41.515 | 3.096 | 35 | 32964 | 825 | 230.3827 | 0.3557 | 0.4826 |
| 0.45 | 2 | sop | False | 0 | 1099.7 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.45 | 2 | stock | False | 216584 | 1543.0 | 140.3648 | 150.494 | 1.140 | 9 | 5670 | 0 | 0.0000 | 0.5095 | 0.1256 |
| 0.45 | 2 | sop | True + honest shares | 73456 | 1335.4 | 55.0066 | 51.041 | 2.857 | 35 | 36848 | 673 | 184.0742 | 0.3948 | 0.4137 |

(elapsed: 62.2s)
