commit: `34cd8ad5`
# Matrix sop2_h10_honest_rep

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 54321  stop_time: (base)
- cells: 3  failures: 0

| attacker | countermeasure | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| connected | sop2 | 0.400 | 0.382 | 0.382 | - | 0.000 | 0.000 | 0.000 | 1.033 | 178 | FAIL (3) | no-forks | 20261004_111002_sop2_h10_honest_rep__connected_sop2 |
| connected | stock | 0.400 | 0.465 | 0.465 | - | 1.000 | 0.000 | 0.005 | 1.147 | 200 | FAIL (3) | ok | 20260930_181907_sop2_h10_honest_rep__connected_stock |
| upgraded | sop2 | 0.400 | 0.406 | 0.406 | - | 0.000 | 0.000 | 0.000 | 0.660 | 175 | PASS (3) | no-forks | 20261004_111002_sop2_h10_honest_rep__upgraded_sop2 |
