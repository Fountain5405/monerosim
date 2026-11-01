# Model B against tevador's simulator: alpha=0.3333, SoP, attacker embeds, days=40000.0 (fixed-rate), seed=1
# Switches are cumulative. Rates per CANONICAL day/year.

| attacker | reveals | canon days | #>=10 | days per | per year |
|:--|--:|--:|--:|--:|--:|
| Model B (o5, release_depth 10) | 1 | 26670 | 1 | 26670 | 0.014 |
| + equal start after a give-up | 11 | 26670 | 11 | 2425 | 0.151 |
| + embeds early honest shares, positional IDs | 23 | 26669 | 23 | 1160 | 0.315 |
| + window on either branch | 21 | 26669 | 21 | 1270 | 0.288 |
| + wins half of exact ties (= tevador) | 27 | 26665 | 27 | 988 | 0.370 |
| union of early honest shares (his UNIQUE_SHARES = False; the slot rule forbids it) | 2462 | 26645 | 2462 | 11 | 33.749 |

(elapsed: 735.6s)
