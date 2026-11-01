commit: `34cd8ad5`
# Matrix stubborn_h10_rejudge

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 12345  stop_time: (base)
- cells: 2  failures: 0

| arm | countermeasure | alpha | depth | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| share | sop2_rejudge | a040 | d2 | 0.400 | 0.043 | 0.043 | - | 0.000 | 0.923 | 0.347 | 10.337 | 115 | FAIL (3) | ok | 20261004_111002_stubborn_h10_rejudge__share_sop2_rejudge_a040_d2 |
| share | sop2_rejudge | a045 | d2 | 0.450 | 0.000 | 0.000 | - | 0.000 | 1.000 | 0.393 | -0.573 | 116 | FAIL (3) | no-forks | 20261004_111002_stubborn_h10_rejudge__share_sop2_rejudge_a045_d2 |
