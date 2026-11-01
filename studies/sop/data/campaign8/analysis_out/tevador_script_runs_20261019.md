# tevador's deep-reorg simulator: 8 runs (2026-10-19)

Script: github.com/tevador/scratchpad, `share-or-perish/blockhain-sim.py`, commit 59d6094c (2026-10-17). Settings as published: HONEST_HR 6 and ATTACK_HR 3 (α = 1/3), W 16, K 3, STUBBORNNESS 5, GAMMA 0.5, MIN_REORG_DEPTH 10, SIM_ROUNDS 1,000,000, UNCLE_BLOCKS False. Runs 1–6 are unmodified (`UNIQUE_SHARES = True`); union 1–2 change only that line to `UNIQUE_SHARES = False`. Each ran with `python3 -I`. The script doesn't seed `random`, so the runs are independent draws. A day is 86,400 simulated seconds, in which the honest side finds 720 blocks; an attack is a success, which orphans at least 10 honest blocks.

| run | UNIQUE_SHARES | simulated days | attacks | days per attack |
|:--|:--|--:|--:|--:|
| run1 | True | 2,052.3 | 2 | 1,026.2 |
| run2 | True | 2,052.1 | 6 | 342.0 |
| run3 | True | 2,051.9 | 3 | 684.0 |
| run4 | True | 2,052.8 | 2 | 1,026.4 |
| run5 | True | 2,054.8 | 2 | 1,027.4 |
| run6 | True | 2,051.6 | 1 | 2,051.6 |
| union1 | False | 2,788.3 | 256 | 10.9 |
| union2 | False | 2,790.5 | 246 | 11.3 |
| **runs 1–6** | True | 12,315.6 | 16 | 769.7 (95 %: 474.0–1,346.6) |
| **union 1–2** | False | 5,578.8 | 502 | 11.1 (95 %: 10.2–12.2) |

Runs 1–6 together: one attack every 2.11 years (95 %: 1.30–3.69).
