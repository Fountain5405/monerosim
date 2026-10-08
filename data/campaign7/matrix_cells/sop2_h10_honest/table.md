commit: `34cd8ad5`
# Matrix sop2_h10_honest

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 12345  stop_time: (base)
- cells: 3  failures: 0

| attacker | countermeasure | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| connected | sop2 | 0.400 | 0.387 | 0.387 | - | 0.000 | 0.000 | 0.000 | 0.097 | 173 | FAIL (3) | no-forks | 20261004_111002_sop2_h10_honest__connected_sop2 |
| connected | stock | 0.400 | 0.385 | 0.385 | - | 1.000 | 0.000 | 0.005 | 1.085 | 182 | FAIL (3) | ok | 20260930_181907_sop2_h10_honest__connected_stock |
| upgraded | sop2 | 0.400 | 0.380 | 0.380 | - | 0.000 | 0.000 | 0.006 | -0.802 | 171 | FAIL (3) | ok | 20261004_111002_sop2_h10_honest__upgraded_sop2 |
