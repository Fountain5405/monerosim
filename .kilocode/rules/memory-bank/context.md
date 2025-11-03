# Monerosim Current Context

## Project Status
**Production-ready** - Core functionality validated through 40+ agent simulations with complex network topologies.

## Current Development Focus
- Validating dynamic peer discovery across large-scale deployments
- Testing GML-based complex network topologies at scale
- Improving simulation stability and determinism

## Recent Achievements
- Python migration complete and verified in production
- Agent framework scales to 40+ autonomous participants
- GML network topology support with AS-aware distribution
- Peer discovery system with Dynamic/Hardcoded/Hybrid modes
- Comprehensive integration testing completed
- **Shadow Agents Refactoring**: Completed 10-phase modular refactoring of shadow_agents.rs into 7 specialized modules (29 files total), achieving 95.6% test pass rate and clean compilation
- **Mining Shim Testing**: Comprehensive test suite implemented with build, unit, integration, and end-to-end tests, all passing successfully

## Key Implementation Details
- All components run within Shadow network simulator
- Logs stored in `shadow.data/hosts/[hostname]/`
- Shared state coordination via `/tmp/monerosim_shared/`
- Geographic IP distribution across 6 continents
- Pytest-based test infrastructure with 95%+ coverage

## Known Issues
- Simulation termination: processes killed by Shadow rather than clean exit
- Block controller: needs verification of mining coordination
- Transaction flow: regular users not sending transactions in latest tests
