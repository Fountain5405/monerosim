# Model B sweep: days=2000.0 (fixed-rate), seed=1
# 'True + honest shares': the SoP attacker's first block after a fork also embeds the honest shares found on the fork point, one per slot.
# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the
# canonical chain); 'canon days' shows how many of those the run covered.

| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |
|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.45 | 3 | sop | True | 61535 | 1275.7 | 48.2368 | 42.758 | 3.481 | 35 | 39084 | 1198 | 343.0072 | 0.3712 | 0.4733 |
| 0.45 | 3 | sop | False | 0 | 1099.7 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.45 | 3 | stock | False | 203784 | 1510.3 | 134.9281 | 141.600 | 1.292 | 18 | 14881 | 93 | 22.4908 | 0.5140 | 0.1366 |
| 0.45 | 3 | sop | True + honest shares | 76745 | 1299.8 | 59.0457 | 53.327 | 3.229 | 35 | 45296 | 1050 | 295.0651 | 0.4187 | 0.3947 |
| 0.45 | 5 | sop | True | 57411 | 1219.4 | 47.0807 | 39.892 | 4.096 | 43 | 39968 | 2242 | 671.5428 | 0.3661 | 0.5035 |
| 0.45 | 5 | sop | False | 0 | 1099.7 | 0.0000 | 0.000 | 0.000 | 0 | 0 | 0 | 0.0000 | 0.0000 | 1.0000 |
| 0.45 | 5 | stock | False | 174078 | 1445.2 | 120.4545 | 120.959 | 1.596 | 38 | 19926 | 2150 | 543.3852 | 0.5061 | 0.1866 |
| 0.45 | 5 | sop | True + honest shares | 73852 | 1237.3 | 59.6869 | 51.316 | 3.798 | 43 | 48568 | 2095 | 618.4306 | 0.4261 | 0.4137 |

(elapsed: 66.2s)
