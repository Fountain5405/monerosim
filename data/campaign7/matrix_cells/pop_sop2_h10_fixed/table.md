commit: `34cd8ad5`
# Matrix pop_sop2_h10_fixed

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 12345  stop_time: (base)
- cells: 2  failures: 0

| strategy | countermeasure | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| es_r2 | sop2 | 0.400 | 0.015 | 0.015 | - | 0.000 | 0.975 | 0.379 | 9.074 | 131 | FAIL (1) | ok | 20261004_111002_pop_sop2_h10_fixed__es_r2_sop2 |
| es | sop2 | 0.400 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.382 | 0.291 | 110 | FAIL (3) | no-forks | 20261004_111002_pop_sop2_h10_fixed__es_sop2 |
