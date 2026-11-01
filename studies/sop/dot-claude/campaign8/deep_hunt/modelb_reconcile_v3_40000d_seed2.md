# Model B against tevador's simulator: alpha=0.3333, SoP, attacker embeds, days=40000.0 (fixed-rate), seed=2
# Switches are cumulative. Rates per CANONICAL day/year.

| attacker | reveals | canon days | #>=10 | days per | per year |
|:--|--:|--:|--:|--:|--:|
| Model B (o5, release_depth 10) | 6 | 26673 | 6 | 4446 | 0.082 |
| + equal start after a give-up | 12 | 26673 | 12 | 2223 | 0.164 |
| + embeds early honest shares, positional IDs | 26 | 26673 | 26 | 1026 | 0.356 |
| + window on either branch | 25 | 26673 | 25 | 1067 | 0.342 |
| + wins half of exact ties (= tevador) | 24 | 26673 | 24 | 1111 | 0.329 |
| union of early honest shares (his UNIQUE_SHARES = False; the slot rule forbids it) | 2481 | 26642 | 2481 | 11 | 34.013 |

(elapsed: 731.9s)
