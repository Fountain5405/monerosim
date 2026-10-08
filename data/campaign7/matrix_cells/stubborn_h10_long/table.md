commit: `34cd8ad5`
# Matrix stubborn_h10_long

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 12345  stop_time: 240h
- cells: 2  failures: 0

| arm | countermeasure | alpha | depth | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| block | stock | a033 | d2 | 0.330 | 0.310 | 0.310 | - | 0.011 | 0.266 | 0.209 | 45.350 | 7078 | PASS (2) | ok | 20260930_190000_stubborn_h10_long__block_stock_a033_d2 |
| share | sop2 | a033 | d2 | 0.330 | 0.016 | 0.016 | - | 0.001 | 0.966 | 0.321 | 66.328 | 7002 | FAIL (2) | ok | 20261004_155751_stubborn_h10_long__share_sop2_a033_d2 |
