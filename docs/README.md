# Documentation index

Every document in `docs/`, sorted into three kinds. Reference docs describe how
the simulator works now. Design records are dated (or are plans); they are
history, may be out of date, and use the paths of their time. Docs moved to a
study are listed with their new paths; `studies/MOVES.tsv` has the full map.

Current research findings are not here: each study's `STATUS.md` states them.

## Reference (current)

- [`AI_CONFIG_GENERATOR.md`](AI_CONFIG_GENERATOR.md): AI Config Generator
- [`ANALYSIS_TOOLS.md`](ANALYSIS_TOOLS.md): Transaction Routing Analysis Tools
- [`ARCHITECTURE.md`](ARCHITECTURE.md): Monerosim Architecture
- [`CHAIN_SNAPSHOT.md`](CHAIN_SNAPSHOT.md): Chain Snapshots (difficulty preload for native mining)
- [`CHAIN_SNAPSHOT_REGEN.md`](CHAIN_SNAPSHOT_REGEN.md): Regenerating the `h50` chain snapshot (after the timestamp-offset fix)
- [`CONFIGURATION.md`](CONFIGURATION.md): Monerosim Configuration Guide
- [`CONFIG_TIMING.md`](CONFIG_TIMING.md): Config Generator Timing Reference
- [`CUPRATE_INTEGRATION.md`](CUPRATE_INTEGRATION.md): Cuprate Integration
- [`FLOW.md`](FLOW.md): How Monerosim Works
- [`HARDFORK_TESTING.md`](HARDFORK_TESTING.md): Hard Fork / Network Upgrade Testing
- [`NATIVE_MINING.md`](NATIVE_MINING.md): Native Mining under Shadow
- [`NETWORK_SCALING_GUIDE.md`](NETWORK_SCALING_GUIDE.md): Network Scaling Guide
- [`PEERLIST_DUMP_PATCH.md`](PEERLIST_DUMP_PATCH.md): Why the target node needs a monerod peer-list-dump patch
- [`PERFORMANCE_AND_SCALE.md`](PERFORMANCE_AND_SCALE.md): Performance and Scale Limits
- [`RUNNING_SIMULATIONS.md`](RUNNING_SIMULATIONS.md): Running Simulations
- [`SCENARIO_FORMAT.md`](SCENARIO_FORMAT.md): Scenario File Format
- [`SELFISH_MINING.md`](SELFISH_MINING.md): Selfish Mining
- [`TAIL_EMISSION.md`](TAIL_EMISSION.md): Tail emission
- [`UPGRADE_WALLET_SIGKILL.md`](UPGRADE_WALLET_SIGKILL.md): Upgrade-Phase Wallet Shutdown: Why SIGKILL, and What We Lose
- [`explain_clock_mods.md`](explain_clock_mods.md): How `--bootfast` and `--allfast` work
- [`shadow-tx-stagger.md`](shadow-tx-stagger.md): Transaction Activity Stagger in Shadow Simulations

## Design records (dated, may be out of date)

- [`20260506_1011node_validation.md`](20260506_1011node_validation.md): 1011-node end-to-end validation (2026-05-06)
- [`20260512_how_pow_works.md`](20260512_how_pow_works.md): How block production works in monerosim
- [`20260605_max_connections_per_ip_bug.md`](20260605_max_connections_per_ip_bug.md): `max-connections-per-ip=1` breaks small, dense simulations
- [`20260610_rucknium_issue3_reply_draft_v2.md`](20260610_rucknium_issue3_reply_draft_v2.md): 20260610_rucknium_issue3_reply_draft_v2
- [`20260610_rucknium_review_response_v2.md`](20260610_rucknium_review_response_v2.md): Response to Rucknium's v0.1.0 Review (issue #3) — v2: Mechanisms, Not Narratives
- [`20260618_mainnet_topology_targets.md`](20260618_mainnet_topology_targets.md): Mainnet network topology: targets + monerosim config approach
- [`20260620_network_topology_study.md`](20260620_network_topology_study.md): Matching Mainnet: Simulator Fidelity Across Rucknium's Four Metrics
- [`20260711_code_quality_review.md`](20260711_code_quality_review.md): Code Quality Review: Full-Codebase Assessment
- [`20260714_shadowformonero_v3.3.0_sync.md`](20260714_shadowformonero_v3.3.0_sync.md): shadowformonero: Rebase onto Upstream Shadow v3.3.0
- [`20260715_dns_shim_audit_and_fixes.md`](20260715_dns_shim_audit_and_fixes.md): DNS-Shim Forensic Audit + Fixes (fork v0.2.2)
- [`20260717_wallet_crash_root_cause.md`](20260717_wallet_crash_root_cause.md): The Intermittent wallet-rpc Crash: Root Cause
- [`20260721_per_run_tmp_namespacing.md`](20260721_per_run_tmp_namespacing.md): Per-Run /tmp Namespacing
- [`20260722_node_reachability_firewall.md`](20260722_node_reachability_firewall.md): Node Reachability: Synthetic Firewall vs. Hidden (breaking change)
- [`20260723_multi_node_type_architecture.md`](20260723_multi_node_type_architecture.md): Multi-node-type architecture: cuprate + generalizable node implementations
- [`20260724_cuprate_scale_experiment.md`](20260724_cuprate_scale_experiment.md): Cuprate at scale: a monerod vs monerod+cuprate network experiment
- [`20260724_cuprate_wallet_rpc.md`](20260724_cuprate_wallet_rpc.md): Cuprate wallet-RPC interop: a real `monero-wallet-rpc` syncs and sends through `cuprated`
- [`20260725_cuprate_connection_matrix.md`](20260725_cuprate_connection_matrix.md): Cross-implementation P2P connection characteristics: monerod ↔ cuprate
- [`20260802_cuprate_upstream_merge.md`](20260802_cuprate_upstream_merge.md): Cuprate 0.1.0-preview: upstream merge, and a 300-node validation of canonical cuprate
- [`20260904_per_run_directories.md`](20260904_per_run_directories.md): Per-run directories: parallel simulations from one checkout
- [`20260923_mainnet_topology_literature.md`](20260923_mainnet_topology_literature.md): Monero mainnet P2P topology: literature and replica targets
- [`20261003_startup_cost.md`](20261003_startup_cost.md): Why a monero process start costs ~17 wall-seconds under Shadow
- [`20261003_startup_ssl_runbook.md`](20261003_startup_ssl_runbook.md): Runbook: why simulation startup takes hours (RPC SSL hypothesis)
- [`20261009_rpc_ssl_off_wallet_stall.md`](20261009_rpc_ssl_off_wallet_stall.md): RPC SSL off → wallets stop syncing after the first transaction burst
- [`20261011_peak_log_phase_design_notes.md`](20261011_peak_log_phase_design_notes.md): Peak-log phase: costs and design options (not implemented)
- [`20261012_3k_slowdown_decomposition.md`](20261012_3k_slowdown_decomposition.md): 3k slowdown: workload, not engine (2026-10-12)
- [`20261012_tail_emission_plan.md`](20261012_tail_emission_plan.md): Plan: simulate mainnet tail emission (2026-10-12)
- [`20261020_storage_dedup_zfs.md`](20261020_storage_dedup_zfs.md): Per-node chain and log storage: share the blobs; dedup doesn't pay
- [`20261101_repo_reorganization.md`](20261101_repo_reorganization.md): Repository reorganization: research branches merged, studies moved to `studies/`, one patch list
- [`20261103_sim_patch_inertness_audit.md`](20261103_sim_patch_inertness_audit.md): Are the monerod-sim patches inert without their flags? Audit of the 15 patches and the stock-equivalence test

Undated plans and investigations, also history:

- [`DETERMINISM_FIXES.md`](DETERMINISM_FIXES.md): Monerosim Determinism Investigation - Findings and Remediation Plan
- [`netsplit_scenario_mods.md`](netsplit_scenario_mods.md): Network Split (Partition) Scenario Implementation Plan
- [`v0.2.0_dns_blocklist_plan.md`](v0.2.0_dns_blocklist_plan.md): v0.2.0 plan: Dandelion++ adversarial experiment suite

Design specs and implementation plans for core features (20 files) are in
[`superpowers/specs/`](superpowers/specs/) and [`superpowers/plans/`](superpowers/plans/).
Figures for the Rucknium review and the topology study are in [`assets/`](assets/).

## Moved to a study

### `studies/sop/`

- `docs/20260912_selfish_mining_results.md` → [`studies/sop/docs/20260912_selfish_mining_results.md`](../studies/sop/docs/20260912_selfish_mining_results.md)
- `docs/20260920_selfish_mining_literature.md` → [`studies/sop/docs/20260920_selfish_mining_literature.md`](../studies/sop/docs/20260920_selfish_mining_literature.md)
- `docs/20260921_selfish_eclipse_results.md` → [`studies/sop/docs/20260921_selfish_eclipse_results.md`](../studies/sop/docs/20260921_selfish_eclipse_results.md)
- `docs/20260921_selfish_release2_results.md` → [`studies/sop/docs/20260921_selfish_release2_results.md`](../studies/sop/docs/20260921_selfish_release2_results.md)
- `docs/20260922_pop_countermeasure_design.md` → [`studies/sop/docs/20260922_pop_countermeasure_design.md`](../studies/sop/docs/20260922_pop_countermeasure_design.md)
- `docs/20260922_selfish_mining_manuscript.md` → [`studies/sop/docs/20260922_selfish_mining_manuscript.md`](../studies/sop/docs/20260922_selfish_mining_manuscript.md)
- `docs/20260923_sop_design.md` → [`studies/sop/docs/20260923_sop_design.md`](../studies/sop/docs/20260923_sop_design.md)
- `docs/20260925_e4_code_data_review.md` → [`studies/sop/docs/20260925_e4_code_data_review.md`](../studies/sop/docs/20260925_e4_code_data_review.md)
- `docs/20260926_dev_branch_handoff.md` → [`studies/sop/docs/20260926_dev_branch_handoff.md`](../studies/sop/docs/20260926_dev_branch_handoff.md)
- `docs/20260926_exact_uncles_and_sop_controls.md` → [`studies/sop/docs/20260926_exact_uncles_and_sop_controls.md`](../studies/sop/docs/20260926_exact_uncles_and_sop_controls.md)
- `docs/20260926_sop_h10_rerun.md` → [`studies/sop/docs/20260926_sop_h10_rerun.md`](../studies/sop/docs/20260926_sop_h10_rerun.md)
- `docs/20260930_sop_conformance.md` → [`studies/sop/docs/20260930_sop_conformance.md`](../studies/sop/docs/20260930_sop_conformance.md)
- `docs/20261007_sop_campaign7_results.md` → [`studies/sop/docs/20261007_sop_campaign7_results.md`](../studies/sop/docs/20261007_sop_campaign7_results.md)
- `docs/20261019_sop_campaign8_results.md` → [`studies/sop/docs/20261019_sop_campaign8_results.md`](../studies/sop/docs/20261019_sop_campaign8_results.md)
- `docs/20261021_research_direction_idea_SoP.txt` → [`studies/sop/docs/20261021_research_direction_idea_SoP.txt`](../studies/sop/docs/20261021_research_direction_idea_SoP.txt)
- `docs/20261022_sop_v4_results.md` → [`studies/sop/docs/20261022_sop_v4_results.md`](../studies/sop/docs/20261022_sop_v4_results.md)
- `docs/20261023_sop_scale_n300_smoke.md` → [`studies/sop/docs/20261023_sop_scale_n300_smoke.md`](../studies/sop/docs/20261023_sop_scale_n300_smoke.md)
- `docs/20261024_sop_o5_grid_results.md` → [`studies/sop/docs/20261024_sop_o5_grid_results.md`](../studies/sop/docs/20261024_sop_o5_grid_results.md)
- `docs/20261025_sop_mdp_notes.md` → [`studies/sop/docs/20261025_sop_mdp_notes.md`](../studies/sop/docs/20261025_sop_mdp_notes.md)
- `docs/20261026_sop_attacker_search.md` → [`studies/sop/docs/20261026_sop_attacker_search.md`](../studies/sop/docs/20261026_sop_attacker_search.md)
- `docs/20261026_sop_learned_attacker.md` → [`studies/sop/docs/20261026_sop_learned_attacker.md`](../studies/sop/docs/20261026_sop_learned_attacker.md)
- `docs/20261028_mrl_status.md` → [`studies/sop/docs/20261028_mrl_status.md`](../studies/sop/docs/20261028_mrl_status.md)
- `docs/msb_calibration_20260921.md` → [`studies/sop/docs/msb_calibration_20260921.md`](../studies/sop/docs/msb_calibration_20260921.md)
- `docs/review/20261008_review_prompt.md` → [`studies/sop/docs/review/20261008_review_prompt.md`](../studies/sop/docs/review/20261008_review_prompt.md)
- `docs/superpowers/plans/2026-10-21-sop-rev20261020.md` → [`studies/sop/docs/superpowers/plans/2026-10-21-sop-rev20261020.md`](../studies/sop/docs/superpowers/plans/2026-10-21-sop-rev20261020.md)
- `docs/superpowers/plans/2026-10-25-sop-rl-attacker.md` → [`studies/sop/docs/superpowers/plans/2026-10-25-sop-rl-attacker.md`](../studies/sop/docs/superpowers/plans/2026-10-25-sop-rl-attacker.md)
- `docs/superpowers/specs/2026-10-21-sop-rev20261020-design.md` → [`studies/sop/docs/superpowers/specs/2026-10-21-sop-rev20261020-design.md`](../studies/sop/docs/superpowers/specs/2026-10-21-sop-rev20261020-design.md)
- `docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md` → [`studies/sop/docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md`](../studies/sop/docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md)
- `review_report.md` → [`studies/sop/docs/review/20261008_review_report.md`](../studies/sop/docs/review/20261008_review_report.md)
- `docs/assets/sop/` (5 files) → [`studies/sop/docs/assets/sop/`](../studies/sop/docs/assets/sop/)

### `studies/antiproxy/`

- `docs/SPY_EXPERIMENT_JOURNAL.md` → [`studies/antiproxy/docs/SPY_EXPERIMENT_JOURNAL.md`](../studies/antiproxy/docs/SPY_EXPERIMENT_JOURNAL.md)
- `docs/20261018_spy_node_defenses.md` → [`studies/antiproxy/docs/20261018_spy_node_defenses.md`](../studies/antiproxy/docs/20261018_spy_node_defenses.md)
- `docs/20261027_findings_summary.md` → [`studies/antiproxy/docs/20261027_findings_summary.md`](../studies/antiproxy/docs/20261027_findings_summary.md)
- `docs/20261028_hashrate_gating_arithmetic.md` → [`studies/antiproxy/docs/20261028_hashrate_gating_arithmetic.md`](../studies/antiproxy/docs/20261028_hashrate_gating_arithmetic.md)
- `docs/20261030_monero_p2p_code_map.md` → [`studies/antiproxy/docs/20261030_monero_p2p_code_map.md`](../studies/antiproxy/docs/20261030_monero_p2p_code_map.md)
- `docs/X0_CALIBRATION.md` → [`studies/antiproxy/docs/X0_CALIBRATION.md`](../studies/antiproxy/docs/X0_CALIBRATION.md)
- `docs/20261028_progress_brief.md` → [`studies/antiproxy/docs/20261028_progress_brief.md`](../studies/antiproxy/docs/20261028_progress_brief.md)
- `docs/SPY_ESTIMATORS.md` → [`studies/antiproxy/docs/SPY_ESTIMATORS.md`](../studies/antiproxy/docs/SPY_ESTIMATORS.md)
- `docs/TXRELAY_LOG.md` → [`studies/antiproxy/docs/TXRELAY_LOG.md`](../studies/antiproxy/docs/TXRELAY_LOG.md)
- `docs/spy_journal/BOX_HANDOVER_phantom.md` → [`studies/antiproxy/docs/spy_journal/BOX_HANDOVER_phantom.md`](../studies/antiproxy/docs/spy_journal/BOX_HANDOVER_phantom.md)
- `docs/spy_journal/BOX_HANDOVER_simbox2.md` → [`studies/antiproxy/docs/spy_journal/BOX_HANDOVER_simbox2.md`](../studies/antiproxy/docs/spy_journal/BOX_HANDOVER_simbox2.md)
- `docs/superpowers/plans/2026-10-30-per-host-peerlist-accounting.md` → [`studies/antiproxy/docs/superpowers/plans/2026-10-30-per-host-peerlist-accounting.md`](../studies/antiproxy/docs/superpowers/plans/2026-10-30-per-host-peerlist-accounting.md)
- `docs/superpowers/plans/2026-10-31-id-consistency-enforcement.md` → [`studies/antiproxy/docs/superpowers/plans/2026-10-31-id-consistency-enforcement.md`](../studies/antiproxy/docs/superpowers/plans/2026-10-31-id-consistency-enforcement.md)
- `docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md` → [`studies/antiproxy/docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md`](../studies/antiproxy/docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md)
- `docs/superpowers/specs/20261031-id-consistency-enforcement-design.md` → [`studies/antiproxy/docs/superpowers/specs/20261031-id-consistency-enforcement-design.md`](../studies/antiproxy/docs/superpowers/specs/20261031-id-consistency-enforcement-design.md)
- `docs/spy_journal/` (922 files: runs, drivers, adhoc scripts, logs) → [`studies/antiproxy/docs/spy_journal/`](../studies/antiproxy/docs/spy_journal/)

### `studies/eclipse/`

- `docs/eclipse_reproduction.md` → [`studies/eclipse/docs/eclipse_reproduction.md`](../studies/eclipse/docs/eclipse_reproduction.md)
- `docs/20261006_bootfast_eclipse_reproduction.md` → [`studies/eclipse/docs/20261006_bootfast_eclipse_reproduction.md`](../studies/eclipse/docs/20261006_bootfast_eclipse_reproduction.md)
