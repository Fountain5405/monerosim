commit: `8b8a93b6`
# Matrix stale_id_stress

- base: `/scratch/monerosim_dev/monerosim/test_configs/selfish_micro_sop.yaml`  seed: 12345  stop_time: 2h
- cells: 1  failures: 0

| network | alpha | share | share_h | ctrl | gamma | att_orph | net_orph | msb_z | blocks | verdicts | health | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| w64 | 0.800 | 0.486 | 0.486 | - | 0.000 | 0.622 | 0.475 | 1.961 | 35 | FAIL (3) | STALE-ID 6; INVALID-CHAIN 27850; no-forks | 20261003_115208_stale_id_stress__w64 |
