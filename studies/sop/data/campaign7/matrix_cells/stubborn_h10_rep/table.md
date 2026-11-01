commit: `34cd8ad5`
# Matrix stubborn_h10_rep

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 54321  stop_time: (base)
- cells: 12  failures: 0

| arm | countermeasure | alpha | depth | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| block | sop2 | a040 | d2 | 0.400 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.403 | -1.151 | 95 | FAIL (3) | ok | 20261004_155751_stubborn_h10_rep__block_sop2_a040_d2 |
| block | sop2 | a045 | d2 | 0.450 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.432 | 0.499 | 96 | FAIL (3) | no-forks | 20261004_155751_stubborn_h10_rep__block_sop2_a045_d2 |
| block | stock | a030 | d2 | 0.300 | 0.229 | 0.229 | - | 0.000 | 0.396 | 0.209 | 6.810 | 140 | PASS (2) | ok | 20260930_212706_stubborn_h10_rep__block_stock_a030_d2 |
| block | stock | a040 | d1 | 0.400 | 0.338 | 0.338 | - | 0.000 | 0.257 | 0.206 | 6.729 | 154 | FAIL (3) | ok | 20260930_231027_stubborn_h10_rep__block_stock_a040_d1 |
| block | stock | a040 | d2 | 0.400 | 0.399 | 0.399 | - | 0.077 | 0.191 | 0.225 | 5.714 | 138 | FAIL (3) | ok | 20260930_230809_stubborn_h10_rep__block_stock_a040_d2 |
| block | stock | a040 | d3 | 0.400 | 0.468 | 0.468 | - | 0.091 | 0.132 | 0.250 | 6.447 | 141 | PASS (3) | ok | 20260930_231057_stubborn_h10_rep__block_stock_a040_d3 |
| block | stock | a045 | d2 | 0.450 | 0.537 | 0.537 | - | 0.000 | 0.081 | 0.222 | 7.309 | 147 | FAIL (3) | ok | 20260930_231227_stubborn_h10_rep__block_stock_a045_d2 |
| share | sop2 | a030 | d2 | 0.300 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.333 | -0.205 | 114 | FAIL (2) | no-forks | 20261004_111002_stubborn_h10_rep__share_sop2_a030_d2 |
| share | sop2 | a040 | d1 | 0.400 | 0.132 | 0.132 | - | 0.000 | 0.773 | 0.328 | 9.222 | 129 | FAIL (3) | ok | 20261004_111002_stubborn_h10_rep__share_sop2_a040_d1 |
| share | sop2 | a040 | d2 | 0.400 | 0.287 | 0.287 | - | 0.024 | 0.545 | 0.322 | 9.646 | 122 | FAIL (3) | ok | 20261004_111002_stubborn_h10_rep__share_sop2_a040_d2 |
| share | sop2 | a040 | d3 | 0.400 | 0.234 | 0.234 | - | 0.024 | 0.612 | 0.335 | 8.149 | 111 | FAIL (3) | ok | 20261004_111002_stubborn_h10_rep__share_sop2_a040_d3 |
| share | sop2 | a045 | d2 | 0.450 | 0.470 | 0.470 | - | 0.029 | 0.427 | 0.375 | 8.547 | 100 | FAIL (3) | ok | 20261004_155751_stubborn_h10_rep__share_sop2_a045_d2 |
