commit: `34cd8ad5`
# Matrix pop_sop2_h10_fixed_rep

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 54321  stop_time: (base)
- cells: 2  failures: 0

| strategy | countermeasure | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| es_r2 | sop2 | 0.400 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.441 | -0.885 | 90 | FAIL (1) | no-forks | 20261004_111002_pop_sop2_h10_fixed_rep__es_r2_sop2 |
| es | sop2 | 0.400 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.355 | 0.480 | 107 | FAIL (3) | no-forks | 20261004_111002_pop_sop2_h10_fixed_rep__es_sop2 |
