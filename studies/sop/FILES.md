# SoP study: file ownership

Generated 2026-11-01 from git: merge-base 5f04b397 (where sop-research left main) .. sop-research.
`* ` marks a file added or changed on sop-research (including the 2026-11-01 status lines).
Everything under studies/sop/ is new on the branch and owned by SoP; it is not listed here.

## Owned by SoP: move into studies/sop/ (455 files; 126 added or changed on sop-research)

Study-specific code, specs, configs, data and dated docs (selfish mining, PoP and SoP). Caveat: setup.sh on main names test_configs/selfish_micro_sop.yaml in a help message (line 54); update that text after the move.

```
  data/campaign7/README.md
  data/campaign7/analysis_out/ban_replay.txt
  data/campaign7/analysis_out/compare_modelb.md
  data/campaign7/analysis_out/depth_mc.txt
  data/campaign7/analysis_out/depth_pooled_d5.txt
  data/campaign7/analysis_out/depth_replication.txt
  data/campaign7/analysis_out/embed_vs_judged.txt
  data/campaign7/analysis_out/flipback_scan_240h_1s.txt
  data/campaign7/analysis_out/flipback_scan_240h_5s.txt
  data/campaign7/analysis_out/pending_shares_banfix.txt
  data/campaign7/analysis_out/race_leads.txt
  data/campaign7/analysis_out/reorg_depths.txt
  data/campaign7/analysis_out/reveal_stats.json
  data/campaign7/analysis_out/reveal_stats_banfix.json
  data/campaign7/analysis_out/reveal_stats_banlog.json
  data/campaign7/analysis_out/shapes_compare.txt
  data/campaign7/analysis_out/share_budget.txt
  data/campaign7/matrix_cells/pop_sop2_h10_fixed/cells/es_r2_sop2.json
  data/campaign7/matrix_cells/pop_sop2_h10_fixed/cells/es_sop2.json
  data/campaign7/matrix_cells/pop_sop2_h10_fixed/table.md
  data/campaign7/matrix_cells/pop_sop2_h10_fixed_rep/cells/es_r2_sop2.json
  data/campaign7/matrix_cells/pop_sop2_h10_fixed_rep/cells/es_sop2.json
  data/campaign7/matrix_cells/pop_sop2_h10_fixed_rep/table.md
  data/campaign7/matrix_cells/sop2_h10_honest/cells/connected_sop2.json
  data/campaign7/matrix_cells/sop2_h10_honest/cells/connected_stock.json
  data/campaign7/matrix_cells/sop2_h10_honest/cells/upgraded_sop2.json
  data/campaign7/matrix_cells/sop2_h10_honest/table.md
  data/campaign7/matrix_cells/sop2_h10_honest_rep/cells/connected_sop2.json
  data/campaign7/matrix_cells/sop2_h10_honest_rep/cells/connected_stock.json
  data/campaign7/matrix_cells/sop2_h10_honest_rep/cells/upgraded_sop2.json
  data/campaign7/matrix_cells/sop2_h10_honest_rep/table.md
  data/campaign7/matrix_cells/stale_id_stress/cells/w64.json
  data/campaign7/matrix_cells/stale_id_stress/table.md
  data/campaign7/matrix_cells/stubborn_h10/cells/block_sop2_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10/cells/block_sop2_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10/cells/block_stock_a030_d2.json
  data/campaign7/matrix_cells/stubborn_h10/cells/block_stock_a040_d1.json
  data/campaign7/matrix_cells/stubborn_h10/cells/block_stock_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10/cells/block_stock_a040_d3.json
  data/campaign7/matrix_cells/stubborn_h10/cells/block_stock_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10/cells/share_sop2_a030_d2.json
  data/campaign7/matrix_cells/stubborn_h10/cells/share_sop2_a040_d1.json
  data/campaign7/matrix_cells/stubborn_h10/cells/share_sop2_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10/cells/share_sop2_a040_d3.json
  data/campaign7/matrix_cells/stubborn_h10/cells/share_sop2_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10/table.md
  data/campaign7/matrix_cells/stubborn_h10_banfix/cells/share_sop2_a033_d5_netcn_debug.json
  data/campaign7/matrix_cells/stubborn_h10_banfix/table.md
  data/campaign7/matrix_cells/stubborn_h10_banfix_rep/cells/share_sop2_a033_d5_netcn_debug.json
  data/campaign7/matrix_cells/stubborn_h10_banfix_rep/table.md
  data/campaign7/matrix_cells/stubborn_h10_banfix_rep2/cells/share_sop2_a033_d5_netcn_debug.json
  data/campaign7/matrix_cells/stubborn_h10_banfix_rep2/table.md
  data/campaign7/matrix_cells/stubborn_h10_banlog/cells/share_sop2_a033_d5_netcn_debug.json
  data/campaign7/matrix_cells/stubborn_h10_banlog/table.md
  data/campaign7/matrix_cells/stubborn_h10_banlog_rep/cells/share_sop2_a033_d5_netcn_debug.json
  data/campaign7/matrix_cells/stubborn_h10_banlog_rep/table.md
  data/campaign7/matrix_cells/stubborn_h10_banlog_rep2/cells/share_sop2_a033_d5_netcn_debug.json
  data/campaign7/matrix_cells/stubborn_h10_banlog_rep2/table.md
  data/campaign7/matrix_cells/stubborn_h10_long/cells/block_stock_a033_d2.json
  data/campaign7/matrix_cells/stubborn_h10_long/cells/share_sop2_a033_d2.json
  data/campaign7/matrix_cells/stubborn_h10_long/table.md
  data/campaign7/matrix_cells/stubborn_h10_long_depth/cells/share_sop2_a033_d3.json
  data/campaign7/matrix_cells/stubborn_h10_long_depth/cells/share_sop2_a033_d5.json
  data/campaign7/matrix_cells/stubborn_h10_long_depth/table.md
  data/campaign7/matrix_cells/stubborn_h10_long_depth_rep/cells/share_sop2_a033_d3.json
  data/campaign7/matrix_cells/stubborn_h10_long_depth_rep/cells/share_sop2_a033_d5.json
  data/campaign7/matrix_cells/stubborn_h10_long_depth_rep/table.md
  data/campaign7/matrix_cells/stubborn_h10_long_rep/cells/block_stock_a033_d2.json
  data/campaign7/matrix_cells/stubborn_h10_long_rep/cells/share_sop2_a033_d2.json
  data/campaign7/matrix_cells/stubborn_h10_long_rep/table.md
  data/campaign7/matrix_cells/stubborn_h10_long_rep2/cells/block_stock_a033_d2.json
  data/campaign7/matrix_cells/stubborn_h10_long_rep2/cells/share_sop2_a033_d2.json
  data/campaign7/matrix_cells/stubborn_h10_long_rep2/table.md
  data/campaign7/matrix_cells/stubborn_h10_rejudge/cells/share_sop2_rejudge_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rejudge/cells/share_sop2_rejudge_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rejudge/table.md
  data/campaign7/matrix_cells/stubborn_h10_rejudge_rep/cells/share_sop2_rejudge_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rejudge_rep/cells/share_sop2_rejudge_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rejudge_rep/table.md
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/block_sop2_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/block_sop2_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/block_stock_a030_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/block_stock_a040_d1.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/block_stock_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/block_stock_a040_d3.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/block_stock_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/share_sop2_a030_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/share_sop2_a040_d1.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/share_sop2_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/share_sop2_a040_d3.json
  data/campaign7/matrix_cells/stubborn_h10_rep/cells/share_sop2_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep/table.md
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/block_sop2_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/block_sop2_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/block_stock_a030_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/block_stock_a040_d1.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/block_stock_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/block_stock_a040_d3.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/block_stock_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/share_sop2_a030_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/share_sop2_a040_d1.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/share_sop2_a040_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/share_sop2_a040_d3.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/cells/share_sop2_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_rep2/table.md
  data/campaign7/matrix_cells/stubborn_h10_smoke/cells/block_stock_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_smoke/cells/share_sop2_a045_d2.json
  data/campaign7/matrix_cells/stubborn_h10_smoke/table.md
  data/campaign7/modelb/alpha_sweep_400d_seed11.md
  data/campaign7/modelb/reveal_variants_a033_d2_20000d.md
  data/campaign7/modelb/run_one.py
  data/campaign7/modelb/shapes_d2.json
  data/campaign7/modelb/shapes_d3.json
  data/campaign7/modelb/shapes_d5.json
  data/campaign7/modelb/sop_d2.json
  data/campaign7/modelb/sop_d3.json
  data/campaign7/modelb/sop_d5.json
  data/campaign7/modelb/stock_d2.json
  data/campaign8/README.md
  data/campaign8/analysis_out/attacker_embedding_check_20261019.txt
  data/campaign8/analysis_out/flipback_20261018.txt
  data/campaign8/analysis_out/flipback_20261019.txt
  data/campaign8/analysis_out/flipback_overnight_20261019.txt
  data/campaign8/analysis_out/flipback_plusN_by_run_20261019.txt
  data/campaign8/analysis_out/late_all_20261018.txt
  data/campaign8/analysis_out/late_all_20261019.txt
  data/campaign8/analysis_out/late_all_offline_20261018.txt
  data/campaign8/analysis_out/late_all_overnight_20261019.txt
  data/campaign8/analysis_out/late_new_20261018.txt
  data/campaign8/analysis_out/late_new_20261019.txt
  data/campaign8/analysis_out/late_new_overnight_20261019.txt
  data/campaign8/analysis_out/modelb_hunt_a033_20000d_seed1_20261019.md
  data/campaign8/analysis_out/modelb_hunt_a040_a045_2000d_seed1_20261019.md
  data/campaign8/analysis_out/modelb_hunt_a040_a045_d2_2000d_seed2_20261019.md
  data/campaign8/analysis_out/modelb_hunt_hs_a033_20000d_seed1_20261019.md
  data/campaign8/analysis_out/modelb_hunt_hs_a040_a045_2000d_seed1_20261019.md
  data/campaign8/analysis_out/modelb_hunt_hs_a040_a045_d2_2000d_seed2_20261019.md
  data/campaign8/analysis_out/modelb_reconcile_40000d_seed1_20261019.md
  data/campaign8/analysis_out/modelb_reconcile_40000d_seed2_20261019.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.30_d12_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.30_d35_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.33_d12_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.33_d35_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.40_d12_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.40_d35_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.45_d12_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_hs_a0.45_d35_2000d_seed1_20261020.md
  data/campaign8/analysis_out/modelb_sweep_rev20261020.md
* data/campaign8/analysis_out/modelb_sweep_rev20261020_noown.md
  data/campaign8/analysis_out/oracle_20261018.txt
  data/campaign8/analysis_out/oracle_20261019.txt
  data/campaign8/analysis_out/oracle_overnight_20261019.txt
  data/campaign8/analysis_out/pending_overnight_20261019.txt
  data/campaign8/analysis_out/pending_shares_rev2.txt
  data/campaign8/analysis_out/probe_20261018.txt
  data/campaign8/analysis_out/probe_20261019.txt
  data/campaign8/analysis_out/probe_overnight_20261019.txt
  data/campaign8/analysis_out/reveals_depths_overnight_20261019.txt
  data/campaign8/analysis_out/reveals_depths_rev2_vs_stock.txt
  data/campaign8/analysis_out/reveals_stats_overnight_20261019.json
  data/campaign8/analysis_out/reveals_stats_overnight_20261019.txt
  data/campaign8/analysis_out/reveals_stats_rev2_vs_stock.json
  data/campaign8/analysis_out/reveals_stats_rev2_vs_stock.txt
  data/campaign8/analysis_out/tevador_script_runs_20261019.md
* data/sop_rl/README.md
* data/sop_rl/logs/.gitkeep
* data/sop_rl/policy_noown_a040.json.gz
* data/sop_rl/policy_noown_a045.json.gz
* data/sop_rl/policy_noown_a048.json.gz
* data/sop_rl/policy_noown_a050_coarse.json.gz
* data/sop_search/baseline.jsonl
* data/sop_search/crossing_fine.jsonl
* data/sop_search/kw_fine.jsonl
* data/sop_search/kw_perish_047.jsonl
* data/sop_search/kw_perish_k2_045.jsonl
* data/sop_search/kw_sweep.jsonl
* data/sop_search/perish_fine.jsonl
* data/sop_search/perish_stage3.jsonl
* data/sop_search/sim_round1/share_sop2_param_a047_s1.json
* data/sop_search/sim_round1/share_sop2_param_a048_s1.json
* data/sop_search/stage1_gz.jsonl
* data/sop_search/stage2_lmr.jsonl
* data/sop_search/stage3_curve.jsonl
* data/sop_search/stock_crossing.jsonl
* data/sop_search/stock_crossing_d5.jsonl
* docs/20260912_selfish_mining_results.md
* docs/20260920_selfish_mining_literature.md
* docs/20260921_selfish_eclipse_results.md
* docs/20260921_selfish_release2_results.md
* docs/20260922_pop_countermeasure_design.md
* docs/20260922_selfish_mining_manuscript.md
* docs/20260923_sop_design.md
* docs/20260925_e4_code_data_review.md
* docs/20260926_dev_branch_handoff.md
* docs/20260926_exact_uncles_and_sop_controls.md
* docs/20260926_sop_h10_rerun.md
* docs/20260930_sop_conformance.md
* docs/20261007_sop_campaign7_results.md
* docs/20261019_sop_campaign8_results.md
* docs/20261021_research_direction_idea_SoP.txt
* docs/20261022_sop_v4_results.md
* docs/20261023_sop_scale_n300_smoke.md
* docs/20261024_sop_o5_grid_results.md
* docs/20261025_sop_mdp_notes.md
* docs/20261026_sop_attacker_search.md
* docs/20261026_sop_learned_attacker.md
* docs/20261028_mrl_status.md
  docs/assets/sop/fork_choice_loop.html
  docs/assets/sop/mrl146_briefing.html
  docs/assets/sop/mrl146_briefing.md
* docs/assets/sop/mrl_meeting_20261021.md
  docs/assets/sop/shares_at_a_fork.html
* docs/msb_calibration_20260921.md
* docs/review/20261008_review_prompt.md
* docs/superpowers/plans/2026-09-12-selfish-mining-apparatus.md
* docs/superpowers/plans/2026-09-12-selfish-mining-phase2.md
* docs/superpowers/plans/2026-09-13-sim-relay-withheld-blocks.md
* docs/superpowers/plans/2026-10-21-sop-rev20261020.md
* docs/superpowers/plans/2026-10-25-sop-rl-attacker.md
* docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md
* docs/superpowers/specs/2026-09-12-selfish-mining-phase2-design.md
* docs/superpowers/specs/2026-09-13-sim-relay-withheld-blocks-design.md
* docs/superpowers/specs/2026-10-21-sop-rev20261020-design.md
* docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md
* gml_processing/1200_nodes_caida_slow_links.gml
* patches/monero-sim-pop.patch
* review_report.md
* scripts/gml_add_slow_nodes.py
  scripts/make_sop_scale_base.py
  scripts/selfish_mining/__init__.py
  scripts/selfish_mining/flipback_scan.py
  scripts/selfish_mining/p2p_ban_replay.py
  scripts/selfish_mining/sop_model_compare.py
  scripts/selfish_mining/sop_pending.py
  scripts/selfish_mining/sop_reveals.py
  scripts/selfish_mining/sop_shares.py
* scripts/selfish_mining/sop_stuck_time.py
  scripts/selfish_mining/test_flipback_scan.py
  scripts/selfish_mining/test_p2p_ban_replay.py
  scripts/selfish_mining/test_sop_model_compare.py
  scripts/selfish_mining/test_sop_pending.py
  scripts/selfish_mining/test_sop_reveals.py
  scripts/selfish_mining/test_sop_shares.py
* scripts/sop_attacker_search.py
* scripts/sop_decision_hist.py
* scripts/sop_fidelity_audit.py
  scripts/sop_health_check.py
* scripts/sop_kw_table.py
  scripts/sop_lateness_probe.py
* scripts/sop_mdp.py
* scripts/sop_mdp_crosscheck.py
  scripts/sop_oracle.py
* scripts/sop_param_readout.py
* scripts/sop_policy.py
* scripts/sop_race_model.py
* scripts/sop_reveal_audit.py
  scripts/sop_reveal_variants.py
* scripts/sop_rl.py
* scripts/sop_stock_crossing.py
  scripts/sop_v4_probes.py
* scripts/test_gml_add_slow_nodes.py
* scripts/test_sop_attacker_search.py
* scripts/test_sop_decision_hist.py
  scripts/test_sop_health_check.py
  scripts/test_sop_lateness_probe.py
* scripts/test_sop_mdp.py
* scripts/test_sop_mdp_crosscheck.py
  scripts/test_sop_oracle.py
* scripts/test_sop_param_readout.py
* scripts/test_sop_race_model.py
* scripts/test_sop_reveal_audit.py
  scripts/test_sop_reveal_variants.py
* scripts/test_sop_rl.py
* scripts/test_sop_stock_crossing.py
  scripts/test_sop_v4_probes.py
  test_configs/dev_snapshot_sop_smoke.yaml
  test_configs/matrix/deep_hunt_smoke.yaml
  test_configs/matrix/deep_hunt_sop_a040.yaml
  test_configs/matrix/deep_hunt_sop_a045.yaml
  test_configs/matrix/deep_hunt_sop_hs_a040.yaml
  test_configs/matrix/deep_hunt_sop_hs_a045.yaml
  test_configs/matrix/deep_hunt_sop_hs_tail_a040.yaml
  test_configs/matrix/deep_hunt_sop_hs_tail_a045.yaml
  test_configs/matrix/deep_hunt_stock.yaml
  test_configs/matrix/pipeline_smoke.yaml
  test_configs/matrix/pop_dettie_mid.yaml
  test_configs/matrix/pop_dettie_mid_rep.yaml
  test_configs/matrix/pop_exact.yaml
  test_configs/matrix/pop_exact_fix_rep.yaml
  test_configs/matrix/pop_exact_h10.yaml
  test_configs/matrix/pop_exact_h10_fbridge.yaml
  test_configs/matrix/pop_exact_h10_fbridge_rep.yaml
  test_configs/matrix/pop_exact_h10_reject.yaml
  test_configs/matrix/pop_exact_h10_reject_rep.yaml
  test_configs/matrix/pop_exact_h10_rep.yaml
  test_configs/matrix/pop_exact_mid.yaml
  test_configs/matrix/pop_exact_mid_fbridge.yaml
  test_configs/matrix/pop_exact_mid_fbridge_rep.yaml
  test_configs/matrix/pop_exact_mid_reject.yaml
  test_configs/matrix/pop_exact_mid_reject_rep.yaml
  test_configs/matrix/pop_exact_mid_rep.yaml
  test_configs/matrix/pop_exact_relay.yaml
  test_configs/matrix/pop_exact_relay_rep.yaml
  test_configs/matrix/pop_exact_rep.yaml
  test_configs/matrix/pop_followup.yaml
  test_configs/matrix/pop_pilot.yaml
  test_configs/matrix/pop_scale.yaml
  test_configs/matrix/pop_scale_r2.yaml
  test_configs/matrix/pop_scale_r2_rep.yaml
  test_configs/matrix/pop_scale_rep.yaml
  test_configs/matrix/pop_sop.yaml
  test_configs/matrix/pop_sop2.yaml
  test_configs/matrix/pop_sop2_h10.yaml
  test_configs/matrix/pop_sop2_h10_fbridge.yaml
  test_configs/matrix/pop_sop2_h10_fbridge_rep.yaml
  test_configs/matrix/pop_sop2_h10_fixed.yaml
  test_configs/matrix/pop_sop2_h10_fixed_rep.yaml
  test_configs/matrix/pop_sop2_h10_reject.yaml
  test_configs/matrix/pop_sop2_h10_reject_rep.yaml
  test_configs/matrix/pop_sop2_h10_rep.yaml
  test_configs/matrix/pop_uncles_pilot.yaml
  test_configs/matrix/pop_wave2.yaml
  test_configs/matrix/sop2_h10_ctl.yaml
  test_configs/matrix/sop2_h10_ctl_rep.yaml
  test_configs/matrix/sop2_h10_honest.yaml
  test_configs/matrix/sop2_h10_honest_rep.yaml
  test_configs/matrix/sop_either_h10.yaml
  test_configs/matrix/sop_either_h10_long.yaml
  test_configs/matrix/sop_either_h10_long_depth.yaml
  test_configs/matrix/sop_either_h10_long_depth_rep.yaml
  test_configs/matrix/sop_either_h10_long_rep.yaml
  test_configs/matrix/sop_either_h10_rep.yaml
  test_configs/matrix/sop_either_h10_rep2.yaml
  test_configs/matrix/sop_either_n40.yaml
  test_configs/matrix/sop_either_n40_depth.yaml
  test_configs/matrix/sop_either_n40_speed.yaml
* test_configs/matrix/sop_knob_smoke.yaml
  test_configs/matrix/sop_rev2_h10.yaml
  test_configs/matrix/sop_rev2_h10_a045_72h.yaml
  test_configs/matrix/sop_rev2_h10_long.yaml
  test_configs/matrix/sop_rev2_h10_long_depth.yaml
  test_configs/matrix/sop_rev2_h10_long_depth_rep.yaml
  test_configs/matrix/sop_rev2_h10_long_rep.yaml
  test_configs/matrix/sop_rev2_h10_rep.yaml
  test_configs/matrix/sop_rev2_h10_rep2.yaml
  test_configs/matrix/sop_rev2_n40.yaml
  test_configs/matrix/sop_rev2_n40_depth.yaml
  test_configs/matrix/sop_rev2_n40_rep.yaml
  test_configs/matrix/sop_rev2_smoke.yaml
* test_configs/matrix/sop_scale_n1000_hs_a045_d5_72h.yaml
* test_configs/matrix/sop_scale_n300_hs_a045_d5_8h.yaml
  test_configs/matrix/sop_v3_h10_a045_72h.yaml
  test_configs/matrix/sop_v3_hs_h10_72h.yaml
  test_configs/matrix/sop_v3_hs_tail_h10_72h.yaml
  test_configs/matrix/sop_v3_hs_tail_smoke.yaml
  test_configs/matrix/sop_v3_n40_depth_rep.yaml
  test_configs/matrix/sop_v3_n40_rep2.yaml
* test_configs/matrix/sop_v4_adopt_72h.yaml
* test_configs/matrix/sop_v4_adopt_lowalpha_72h.yaml
* test_configs/matrix/sop_v4_adopt_nodrop_72h.yaml
* test_configs/matrix/sop_v4_control_72h.yaml
* test_configs/matrix/sop_v4_control_tail_72h.yaml
* test_configs/matrix/sop_v4_dsweep_gamma_72h.yaml
* test_configs/matrix/sop_v4_dsweep_param_72h.yaml
* test_configs/matrix/sop_v4_dsweep_slow_72h.yaml
* test_configs/matrix/sop_v4_gamma_72h.yaml
  test_configs/matrix/sop_v4_h10_72h.yaml
  test_configs/matrix/sop_v4_h10_72h_s2.yaml
* test_configs/matrix/sop_v4_learned_6h.yaml
* test_configs/matrix/sop_v4_learned_72h.yaml
  test_configs/matrix/sop_v4_noown_72h.yaml
  test_configs/matrix/sop_v4_noown_72h_s2.yaml
* test_configs/matrix/sop_v4_o5_72h.yaml
* test_configs/matrix/sop_v4_o5_alpha_72h.yaml
* test_configs/matrix/sop_v4_o5_noown_72h.yaml
* test_configs/matrix/sop_v4_o5_stock_72h.yaml
* test_configs/matrix/sop_v4_param_1h_72h.yaml
* test_configs/matrix/sop_v4_param_1h_tail_72h.yaml
* test_configs/matrix/sop_v4_param_6h.yaml
* test_configs/matrix/sop_v4_param_72h.yaml
* test_configs/matrix/sop_v4_param_h4_72h.yaml
* test_configs/matrix/sop_v4_param_h4_tail_72h.yaml
* test_configs/matrix/sop_v4_param_tail_72h.yaml
* test_configs/matrix/sop_v4_seed2_adopt_72h.yaml
* test_configs/matrix/sop_v4_seed2_gamma_72h.yaml
* test_configs/matrix/sop_v4_seed2_slow_72h.yaml
* test_configs/matrix/sop_v4_slow_72h.yaml
  test_configs/matrix/sop_v4_smoke.yaml
* test_configs/matrix/sop_v4_stock_d2_72h.yaml
* test_configs/matrix/sop_v4_stock_d2_tail_72h.yaml
* test_configs/matrix/sop_v4_window_72h.yaml
* test_configs/matrix/sop_v4_window_k2_a045_72h.yaml
* test_configs/matrix/sop_v4_window_k6_1h_72h.yaml
* test_configs/matrix/sop_v4_window_k6_a048_72h.yaml
* test_configs/matrix/sop_v4_window_k6_h4_72h.yaml
  test_configs/matrix/stale_id_stress.yaml
  test_configs/matrix/stubborn_h10.yaml
  test_configs/matrix/stubborn_h10_banfix.yaml
  test_configs/matrix/stubborn_h10_banfix_rep.yaml
  test_configs/matrix/stubborn_h10_banfix_rep2.yaml
  test_configs/matrix/stubborn_h10_banlog.yaml
  test_configs/matrix/stubborn_h10_banlog_rep.yaml
  test_configs/matrix/stubborn_h10_banlog_rep2.yaml
  test_configs/matrix/stubborn_h10_long.yaml
  test_configs/matrix/stubborn_h10_long_depth.yaml
  test_configs/matrix/stubborn_h10_long_depth_rep.yaml
  test_configs/matrix/stubborn_h10_long_rep.yaml
  test_configs/matrix/stubborn_h10_long_rep2.yaml
  test_configs/matrix/stubborn_h10_rejudge.yaml
  test_configs/matrix/stubborn_h10_rejudge_rep.yaml
  test_configs/matrix/stubborn_h10_rep.yaml
  test_configs/matrix/stubborn_h10_rep2.yaml
  test_configs/matrix/stubborn_h10_smoke.yaml
  test_configs/pop_exact_fork_smoke.yaml
  test_configs/pop_exact_fork_smoke_fast.yaml
  test_configs/selfish_eclipse/gamma_eclipse.yaml
  test_configs/selfish_eclipse/gamma_eclipse_majority.yaml
  test_configs/selfish_eclipse/honest_baseline.yaml
  test_configs/selfish_eclipse_sweep/omega_0000.yaml
  test_configs/selfish_eclipse_sweep/omega_0200.yaml
  test_configs/selfish_eclipse_sweep/omega_0300_3v.yaml
  test_configs/selfish_long.yaml
  test_configs/selfish_micro.yaml
  test_configs/selfish_micro_honest.yaml
* test_configs/selfish_micro_sop.yaml
* test_configs/selfish_micro_sop_gamma.yaml
* test_configs/selfish_micro_sop_h4.yaml
* test_configs/selfish_micro_sop_scale1000.yaml
* test_configs/selfish_micro_sop_scale300.yaml
* test_configs/selfish_micro_sop_slow.yaml
  test_configs/selfish_micro_sop_tail.yaml
  test_configs/selfish_n40_sop.yaml
  test_configs/selfish_phase2/fanout_1.yaml
  test_configs/selfish_phase2/fanout_3.yaml
  test_configs/selfish_phase2/fanout_6.yaml
  test_configs/selfish_phase2/stub_equalfork.yaml
  test_configs/selfish_phase2/stub_lead.yaml
  test_configs/selfish_phase2/stub_trail.yaml
  test_configs/selfish_phase3/gamma_lift.yaml
  test_configs/selfish_phase4/gamma_relay.yaml
  test_configs/selfish_release2.yaml
  test_configs/selfish_scaled.yaml
  test_configs/selfish_scaled_mid.yaml
  test_configs/selfish_sweep/alpha_0300.yaml
  test_configs/selfish_sweep/alpha_0400.yaml
  test_configs/selfish_sweep/alpha_0450.yaml
  test_configs/selfish_sweep_release2/alpha_0300.yaml
  test_configs/selfish_sweep_release2/alpha_0400.yaml
  test_configs/selfish_sweep_release2/alpha_0450.yaml
  test_configs/sop_fork_smoke.yaml
  test_configs/sop_relay_smoke.yaml
  test_configs/sop_relay_smoke_verbose.yaml
  test_configs/sop_stock_observer_smoke.yaml
  test_configs/sop_weight_smoke.yaml
  test_configs/sop_weight_smoke_fixed.yaml
```

## Shared with the simulator: keep in place, SoP depends on them (25 files; 8 added or changed on sop-research)

Main's Rust code and tests load the selfish-mining agents (src/config/agent_config.rs, src/utils/mining.rs, tests/fixtures/selfish*.yaml, tests/orchestrator_selfish.rs), every patch is built into the one monerod-sim, and the h10 snapshot and the loops GML are simulator assets. HANDOFF.md says why the branch changed each starred file.

```
* .gitignore
  agents/selfish_bridge.py
* agents/selfish_miner.py
* agents/selfish_strategy.py
  agents/test_selfish_bridge.py
* agents/test_selfish_miner.py
* agents/test_selfish_strategy.py
  chain_snapshots/h10/blocks.jsonl.gz
  chain_snapshots/h10/manifest.json
  docs/20261012_tail_emission_plan.md
  docs/SELFISH_MINING.md
  docs/TAIL_EMISSION.md
  gml_processing/1200_nodes_caida_with_loops.gml
  monero.pin
  patches/monero-fakechain-hardforks.patch
  patches/monero-sim-mining.patch
  patches/monero-sim-peerlist-dump.patch
  patches/monero-sim-selfish-relay.patch
  patches/monero-sim-tail-emission.patch
* pyproject.toml
  scripts/honest_chain_from_log.py
* scripts/selfish_matrix.py
  scripts/selfish_mining_analysis.py
* scripts/test_selfish_matrix.py
  scripts/test_selfish_mining_analysis.py
```

## Changed on sop-research outside both lists (0 files; 0 added or changed on sop-research)

Empty means every branch change is classified above.

```
```
