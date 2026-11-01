commit: `34cd8ad5`
# Matrix stubborn_h10_long_rep

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 54321  stop_time: 240h
- cells: 2  failures: 0

| arm | countermeasure | alpha | depth | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| block | stock | a033 | d2 | 0.330 | 0.287 | 0.287 | - | 0.004 | 0.285 | 0.202 | 45.012 | 7102 | PASS (2) | ok | 20260930_190000_stubborn_h10_long_rep__block_stock_a033_d2 |
| share | sop2 | a033 | d2 | 0.330 | 0.024 | 0.024 | - | 0.001 | 0.950 | 0.320 | 70.177 | 7024 | FAIL (2) | ok | 20261004_155751_stubborn_h10_long_rep__share_sop2_a033_d2 |
