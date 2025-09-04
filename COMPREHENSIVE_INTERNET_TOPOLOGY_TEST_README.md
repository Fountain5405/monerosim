# Comprehensive Internet Topology End-to-End Test

This test suite validates the complete realistic internet topology simulation system in Monerosim, including GML parsing, hierarchical IP assignment, multi-layered network structure, and inter-network communication validation.

## Overview

The comprehensive test system consists of:

1. **Complex GML Topology** (`comprehensive_internet_topology_test.gml`)
   - 15 network nodes across 5 Autonomous Systems (ASes)
   - Realistic network structure with varying bandwidth, latency, and packet loss
   - Multiple network layers (core, edge, international)

2. **Test Configuration** (`config_comprehensive_internet_test.yaml`)
   - 15 agents distributed across different ASes
   - Mix of miners and regular users
   - Realistic transaction patterns and mining distribution

3. **Test Suite** (`scripts/comprehensive_internet_topology_test.py`)
   - 9 comprehensive test cases
   - Validates all aspects of the simulation system
   - Detailed logging and reporting

4. **Test Runner** (`scripts/run_comprehensive_internet_test.py`)
   - Automated test execution
   - Optional binary building
   - Prerequisite checking

## Network Topology

### Autonomous Systems (ASes)

| AS Number | Description | Subnet | Nodes | Characteristics |
|-----------|-------------|--------|-------|------------------|
| 65001 | Large ISP Network | 10.0.0.0/24 | 4 | High-speed backbone, NYC/LAX coverage |
| 65002 | Regional ISP Network | 192.168.0.0/24 | 4 | Regional coverage, Chicago/Seattle |
| 65003 | Data Center Network | 172.16.0.0/24 | 3 | Ultra-high bandwidth, Ashburn |
| 65004 | International Network | 203.0.113.0/24 | 2 | High latency, global coverage |
| 65005 | University Network | 198.51.100.0/24 | 2 | Research network, Cambridge |

### Network Characteristics

- **Intra-AS**: Low latency (1-8ms), high bandwidth (1-10Gbps)
- **Inter-AS**: Variable latency (15-200ms), diverse bandwidth (20Mbps-500Mbps)
- **International**: High latency (75-200ms), lower bandwidth (50Mbps)
- **Research Networks**: Optimized for data transfer (10Gbps)

## Test Cases

### 1. GML Parsing (`test_gml_parsing`)
- Validates GML file structure and content
- Checks for required nodes and edges
- Ensures proper graph declaration

### 2. Network Topology Validation (`test_network_topology_validation`)
- Verifies network connectivity
- Checks AS distribution balance
- Validates topology integrity

### 3. Autonomous System Grouping (`test_autonomous_system_grouping`)
- Confirms all expected ASes are present
- Validates node-to-AS assignments
- Checks AS node count requirements

### 4. Hierarchical IP Assignment (`test_hierarchical_ip_assignment`)
- Validates AS-aware subnet allocation
- Ensures IP uniqueness within ASes
- Checks subnet pattern compliance

### 5. Agent Distribution (`test_agent_distribution`)
- Verifies agent configuration parsing
- Checks miner distribution
- Validates agent count requirements

### 6. Shadow Configuration Generation (`test_shadow_configuration_generation`)
- Tests monerosim binary execution
- Validates Shadow YAML generation
- Checks configuration structure

### 7. Agent Registry Creation (`test_agent_registry_creation`)
- Validates agent registry JSON structure
- Checks agent data completeness
- Verifies IP address assignments

### 8. Miner Registry Creation (`test_miner_registry_creation`)
- Validates miner registry structure
- Checks hashrate distribution
- Ensures IP uniqueness

### 9. Inter-Network Communication Paths (`test_inter_network_communication_paths`)
- Validates network connectivity
- Checks inter-AS communication
- Verifies communication path requirements

## Usage

### Quick Start

```bash
# Run the test with existing binary
python3 scripts/run_comprehensive_internet_test.py

# Build and run the test
python3 scripts/run_comprehensive_internet_test.py --build

# Run with verbose logging
python3 scripts/run_comprehensive_internet_test.py --verbose
```

### Manual Execution

```bash
# 1. Build the monerosim binary (if needed)
cargo build --release

# 2. Run the comprehensive test
python3 scripts/comprehensive_internet_topology_test.py
```

## Prerequisites

- **Rust Toolchain**: For building monerosim
- **Python 3.6+**: For running tests
- **Required Files**:
  - `comprehensive_internet_topology_test.gml`
  - `config_comprehensive_internet_test.yaml`
  - `scripts/comprehensive_internet_topology_test.py`

## Output Files

The test generates several output files:

- `comprehensive_internet_topology_test.log`: Detailed execution log
- `comprehensive_internet_topology_test_report.json`: Structured test results
- `comprehensive_internet_test_output/shadow_agents.yaml`: Generated Shadow configuration
- `/tmp/monerosim_shared/agent_registry.json`: Agent registry
- `/tmp/monerosim_shared/miners.json`: Miner registry

## Test Results

### Success Criteria

The test suite passes when:
- All 9 test cases complete successfully
- Network topology is fully connected
- All ASes have proper IP assignments
- Shadow configuration generates without errors
- Agent and miner registries are properly created

### Expected Results

```
COMPREHENSIVE INTERNET TOPOLOGY TEST REPORT
============================================================
Total Tests: 9
Passed: 9
Failed: 0
Success Rate: 100.0%

ALL TESTS PASSED! 🎉
============================================================
```

## Troubleshooting

### Common Issues

1. **Missing Binary**
   ```
   Error: Monerosim binary not found
   Solution: Run with --build flag or build manually with `cargo build --release`
   ```

2. **Missing Files**
   ```
   Error: Missing required files
   Solution: Ensure all test files are present in the project root
   ```

3. **Build Failures**
   ```
   Error: Build failed
   Solution: Check Rust toolchain installation and dependencies
   ```

4. **Test Timeouts**
   ```
   Error: Test execution timed out
   Solution: Check system resources and Shadow installation
   ```

### Debug Mode

Enable verbose logging for detailed troubleshooting:

```bash
python3 scripts/run_comprehensive_internet_test.py --verbose
```

## Architecture Validation

This test validates the following architectural components:

### 1. GML Parser (`src/gml_parser.rs`)
- Custom GML parsing implementation
- Node and edge extraction
- Attribute parsing and validation

### 2. Shadow Configuration (`src/shadow_agents.rs`)
- Agent-based configuration generation
- AS-aware IP assignment
- Network topology integration

### 3. Hierarchical Addressing
- AS-based subnet allocation
- IP address uniqueness
- Network segmentation

### 4. Multi-layered Network Structure
- Core network nodes
- Edge distribution points
- International connectivity
- Research network integration

### 5. Inter-network Communication
- Cross-AS connectivity validation
- Communication path analysis
- Network reachability testing

## Performance Characteristics

### Test Execution Time
- **Typical**: 30-60 seconds
- **With Build**: 5-8 minutes
- **Verbose Mode**: 10-15% slower

### Resource Requirements
- **CPU**: Minimal (single-threaded parsing)
- **Memory**: ~50MB for test execution
- **Disk**: ~10MB for generated files

## Integration with CI/CD

The test can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Comprehensive Internet Test
  run: |
    python3 scripts/run_comprehensive_internet_test.py --build
```

## Future Enhancements

### Planned Improvements
- **Performance Testing**: Network throughput validation
- **Scalability Testing**: Large-scale network simulation
- **Fault Injection**: Network failure scenario testing
- **Real-time Monitoring**: Live network state validation

### Extension Points
- **Custom Topologies**: Support for user-defined GML files
- **Dynamic Configuration**: Runtime topology modification
- **Advanced Metrics**: Detailed performance analytics
- **Visualization**: Network topology rendering

## Contributing

When adding new test cases:

1. Follow the existing test structure
2. Add comprehensive logging
3. Include detailed error messages
4. Update this documentation
5. Test with multiple network topologies

## Related Documentation

- [Monerosim Architecture](../docs/ARCHITECTURE.md)
- [GML Network Topology](../docs/GML_IP_ASSIGNMENT_AS_DISTRIBUTION.md)
- [Agent Framework](../docs/AGENT_FRAMEWORK.md)
- [Configuration Guide](../docs/CONFIGURATION.md)