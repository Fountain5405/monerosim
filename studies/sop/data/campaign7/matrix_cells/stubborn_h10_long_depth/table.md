commit: `34cd8ad5`
# Matrix stubborn_h10_long_depth

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 12345  stop_time: 240h
- cells: 2  failures: 0

| arm | countermeasure | alpha | depth | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| share | sop2 | a033 | d3 | 0.330 | 0.024 | 0.024 | - | 0.001 | 0.950 | 0.323 | 69.319 | 7013 | FAIL (2) | ok | 20261004_155751_stubborn_h10_long_depth__share_sop2_a033_d3 |
| share | sop2 | a033 | d5 | 0.330 | 0.020 | 0.020 | - | 0.003 | 0.960 | 0.328 | 68.256 | 7013 | FAIL (2) | INVALID-CHAIN 1 | 20261004_155751_stubborn_h10_long_depth__share_sop2_a033_d5 |
