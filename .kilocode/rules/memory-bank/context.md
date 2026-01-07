# Monerosim Current Context

## Project Status
**Production-ready** - Core functionality validated through 1000 agent scaling tests with CAIDA-based network topologies.

## Current Development Focus
- Scaling tests up to 1000 agents
- Documentation synchronization with code
- Performance optimization for large simulations

## Recent Achievements
- **Scaling Test Infrastructure**: Tests for 50-1000 agents with 6h simulation duration, 5s stagger
- **Documentation Overhaul**: All docs updated to match current code state
- **Autonomous Mining**: Poisson-distributed block generation, fully deterministic via simulation_seed
- **CAIDA Topology Support**: Realistic internet topologies with AS relationship semantics
- **Modular Architecture**: Rust codebase organized into specialized modules (orchestrator.rs, config_loader.rs, gml_parser.rs)

## Key Implementation Details
- All components run within Shadow network simulator (shadowformonero)
- Binaries installed to `~/.monerosim/bin/`
- Logs stored in `shadow.data/hosts/[hostname]/`
- Shared state coordination via `/tmp/monerosim_shared/`
- Geographic IP distribution across 6 continents
- Default config: `config_32_agents.yaml`

## Known Issues
- Simulation termination: processes killed by Shadow rather than clean exit (expected behavior)
- Block controller: DEPRECATED - use `agents.autonomous_miner` instead
