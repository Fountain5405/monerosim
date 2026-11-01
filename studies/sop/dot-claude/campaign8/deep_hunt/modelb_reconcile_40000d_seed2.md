# Model B against tevador's simulator: alpha=0.3333, SoP, attacker embeds, days=40000.0 (fixed-rate), seed=2
# Switches are cumulative. Rates per CANONICAL day/year.

| attacker | reveals | canon days | #>=10 | days per | per year |
|:--|--:|--:|--:|--:|--:|
| Model B (o5, release_depth 10) | 6 | 26673 | 6 | 4446 | 0.082 |
| + equal start after a give-up | 12 | 26673 | 12 | 2223 | 0.164 |
| + embeds early honest shares | 2556 | 26651 | 2556 | 10 | 35.030 |
| + window on either branch | 2527 | 26651 | 2527 | 11 | 34.632 |
| + wins half of exact ties (= tevador) | 2481 | 26642 | 2481 | 11 | 34.013 |

(elapsed: 589.4s)
