# Monerosim Product Overview

## What It Is
Rust-based configuration generator for Shadow network simulator to run realistic Monero cryptocurrency network simulations with autonomous agent behaviors.

## Core Value Proposition
Enables controlled, reproducible Monero network research and testing without deploying real infrastructure.

## Key Capabilities
- **Scalable Simulations**: 2-1000+ agents on single machine (tested up to 1000)
- **Agent Framework**: Autonomous miners (Poisson-based), users, distributors, monitors
- **Network Topologies**: Switch-based (simple) or CAIDA GML-based (realistic internet)
- **Geographic Distribution**: Automatic IP allocation across 6 continents
- **Peer Discovery**: Dynamic, Hardcoded, or Hybrid connection modes
- **Reproducible**: Deterministic simulations via `simulation_seed`

## Primary Use Cases
1. Protocol modification testing in safe environment
2. Network attack/defense simulation and research
3. Performance analysis under various conditions
4. P2P networking behavior studies
5. Academic cryptocurrency research
6. Large-scale network topology analysis

## Target Users
- Monero protocol researchers
- Cryptocurrency network developers
- Security researchers
- Academic distributed systems researchers

## Maturity Status
**Production-ready** - Validated with configurations up to 1000 agents. CAIDA-based realistic internet topologies supported. Autonomous mining with full determinism.
