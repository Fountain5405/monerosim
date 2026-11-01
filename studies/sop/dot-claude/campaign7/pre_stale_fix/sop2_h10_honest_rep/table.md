commit: `e4905a2b`
# Matrix sop2_h10_honest_rep

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 54321  stop_time: (base)
- cells: 3  failures: 0

| attacker | countermeasure | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| connected | sop2 | 0.400 | 0.346 | 0.346 | - | 0.000 | 0.000 | 0.000 | -0.790 | 156 | FAIL (3) | no-forks | 20260930_181907_sop2_h10_honest_rep__connected_sop2 |
| connected | stock | 0.400 | 0.465 | 0.465 | - | 1.000 | 0.000 | 0.005 | 1.147 | 200 | FAIL (3) | ok | 20260930_181907_sop2_h10_honest_rep__connected_stock |
| upgraded | sop2 | 0.400 | 0.392 | 0.392 | - | 0.000 | 0.000 | 0.006 | 1.017 | 153 | FAIL (3) | ok | 20260930_181907_sop2_h10_honest_rep__upgraded_sop2 |
