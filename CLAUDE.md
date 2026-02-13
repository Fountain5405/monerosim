# CLAUDE.md - Coding Guide for Monerosim

## Project Overview

Monerosim is a Rust configuration generator for Monero network simulations running in the [Shadow](https://shadow.github.io/) network simulator. It takes a YAML config and produces Shadow-compatible YAML + wrapper scripts + Python agent scripts.

**Flow:** YAML config → Rust engine → Shadow YAML + wrapper scripts → Shadow simulation with real Monero binaries + Python agents

## Build & Test

```bash
cargo build --release          # Build the binary
cargo test                     # Run unit tests (63 pass, 2 pre-existing IP test failures)
python3 -c "import agents"    # Verify Python agent imports
```

### Simulation Testing

Test directories follow the naming convention `YYYYMMDD_<commit-hash>_tests/`. Each contains:
- `run_all_tests.sh` — Fast config validation (~30s, always run first)
- `run_shadow_sims.sh` — Full Shadow simulations (~70 min per test, 8 tests)

**Never run multiple Shadow sim suites concurrently** — they consume massive resources and produce false failures.

## Architecture

### Rust (`src/`)
- `config_v2.rs` — YAML config parsing, type definitions, validation
- `orchestrator.rs` — High-level config generation coordination
- `shadow/` — Shadow YAML output structures
- `ip/` — IP address allocation, AS management
- `topology/` — Network topology (GML, switch)
- `agent/` — Agent config generation (user agents, miners, scripts)
- `process/` — Process/wrapper script generation
- `analysis/` — Post-simulation log analysis
- `utils/` — Duration parsing, validation, seed extraction

### Python Agents (`agents/`)
- `base_agent.py` — Base class with RPC, retry logic, lifecycle
- `autonomous_miner.py` — Mining agent (hashrate control, block production)
- `regular_user.py` — Transaction-sending user agent
- `miner_distributor.py` — Distributes mining rewards to users
- `simulation_monitor.py` — Health monitoring and status reporting
- `agent_discovery.py` — DNS-based agent registry
- `constants.py` — Shared magic numbers (atomic units, block time, etc.)
- `shared_utils.py` — Shared utilities (address validation, seed generation)
- `monero_rpc.py` — Monero daemon/wallet RPC client

## Coding Conventions

### Rust
- Use `LazyLock<Regex>` for static regex patterns (see `config_v2.rs`, `log_parser.rs`)
- Constants go in `src/lib.rs` (ports, paths, timing values)
- Error handling: `color_eyre` for public APIs, `.unwrap()` only for compile-time-known-valid values (e.g., static regex patterns)
- Tests are inline `#[cfg(test)] mod tests` within source files
- MSRV is 1.80 (for `LazyLock`)

### Python
- Constants go in `agents/constants.py`, shared logic in `agents/shared_utils.py`
- Never use bare `except: pass` — always log the exception
- Use `shared_utils.is_valid_monero_address()` for address validation
- Use `shared_utils.xmr_to_atomic()` / `atomic_to_xmr()` for unit conversion
- Use `shared_utils.make_deterministic_seed()` for reproducible randomness

## Key Domain Concepts

- **Atomic units:** 1 XMR = 10^12 piconero
- **Block time:** 120 seconds target
- **Shadow epoch:** 2000-01-01 00:00:00 UTC (Unix timestamp 946684800)
- **Monero address prefixes:** `4` (standard) or `8` (subaddress), length 4-95 chars
- **Ports:** P2P=18080, RPC=18081, Wallet RPC=18082

## Common Pitfalls

- The 2 failing unit tests (`test_ip_assignment`, `test_subnet_base_calculation`) are pre-existing and unrelated to most changes
- Shadow simulations are resource-intensive — run sequentially, not in parallel
- Config test `03_relay_upgrade` reports "relay has 2 processes" — this is expected for upgrade scenarios with daemon phases
- Python agents run inside Shadow's simulated network — they use `time.time()` relative to Shadow epoch, not real wall clock
