# Where the agent `hashrate` value flows (scout map, 2026-09-30) — for the fractional-hashrate change

## Rust (integer today)
- src/config/agent_config.rs:123, :368 — `pub hashrate: Option<u32>`; :32 deserialization `map(|v| Some(v as u32))`.
- src/utils/validation.rs:185-213 — native 1..=1000, percentage 1..=100 (==0 checks at 194-210); :213 `total_hashrate += hashrate as u64`. Test helper :806 `fn miner(hashrate: u32)`; tests :602-836 use integer literals (0, 100, 150, 1000, 1001).
- src/utils/mining.rs:19 — `hash_interval_ms(hashrate_hs: u32) -> u64` (as f64, round, floor 1 ms); :36 `equilibrium_difficulty(u64)`.
- src/agent/user_agents.rs:665-674 — sums `h as u64` for the D_eq log; :939-942 `hash_interval_ms(user_agent_config.hashrate.unwrap_or(1))` → `sim-hash-interval-ms`; :1635-1636 `hashrate.to_string()` into agent attributes.
- src/orchestrator.rs:444-445 — `hashrate.to_string()` into attributes; **:558 `h.parse::<u32>()` — fails on "4.5"**.
- src/utils/chain_snapshot.rs:27 `total_hashrate: u64`; :112 exact match `manifest.total_hashrate == total_hashrate` (fractional totals like 3+3.5+3.5 must still match h10's 10).

## Python (mostly float-ready already)
- agents/autonomous_miner.py:252 — `float(hashrate_str)` (test agents/test_autonomous_miner.py:32-35 already covers "33.5").
- scripts/native_daa_analysis.py:118 `float(...)`; :318-369 sums.
- scripts/selfish_mining_analysis.py:246-249, :292-295 — alpha / eclipsed sums (float-safe).
- scripts/scenario_parser.py:626-629 — list expansion passes values through (no int()).
- scripts/chain_snapshot.py:550 — `--total-hashrate type=int` (manifest field).
- Type hints only (runtime-safe): scripts/ai_config/validator.py:95,164,165,376-378,514-517,592; scripts/config_generation/agent_emit.py:14,27.
- Tests with integer equality (fine as-is): scripts/test_scenario_parser.py:188-190, test_selfish_matrix.py:60-62, test_selfish_configs.py:206-208; float-ratio checks test_selfish_phase2_configs.py:50-52, test_selfish_configs.py:88-90.
