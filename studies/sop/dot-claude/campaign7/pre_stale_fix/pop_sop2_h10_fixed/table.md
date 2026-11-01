commit: `e4905a2b`
# Matrix pop_sop2_h10_fixed

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 12345  stop_time: (base)
- cells: 2  failures: 0

| strategy | countermeasure | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| es_r2 | sop2 | 0.400 | 0.009 | 0.009 | - | 0.014 | 0.986 | 0.400 | 1.295 | 108 | FAIL (1) | ok | 20260930_181907_pop_sop2_h10_fixed__es_r2_sop2 |
| es | sop2 | 0.400 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.372 | 0.646 | 113 | FAIL (3) | no-forks | 20260930_181907_pop_sop2_h10_fixed__es_sop2 |
