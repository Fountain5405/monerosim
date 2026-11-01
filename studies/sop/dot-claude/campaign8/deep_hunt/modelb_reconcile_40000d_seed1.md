# Model B against tevador's simulator: alpha=0.3333, SoP, attacker embeds, days=40000.0 (fixed-rate), seed=1
# Switches are cumulative. Rates per CANONICAL day/year.

| attacker | reveals | canon days | #>=10 | days per | per year |
|:--|--:|--:|--:|--:|--:|
| Model B (o5, release_depth 10) | 1 | 26670 | 1 | 26670 | 0.014 |
| + equal start after a give-up | 11 | 26670 | 11 | 2425 | 0.151 |
| + embeds early honest shares | 2414 | 26648 | 2414 | 11 | 33.087 |
| + window on either branch | 2386 | 26649 | 2386 | 11 | 32.703 |
| + wins half of exact ties (= tevador) | 2462 | 26645 | 2462 | 11 | 33.749 |

(elapsed: 592.6s)
