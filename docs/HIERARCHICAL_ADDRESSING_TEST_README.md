# Hierarchical Addressing and Inter-Network Communication Test

This comprehensive test suite validates the hierarchical addressing system and inter-network communication capabilities of the Monerosim agent framework.

## Overview

The hierarchical addressing test suite validates:

1. **AS-aware IP address assignment** - Ensures agents are correctly assigned to appropriate subnets based on autonomous system numbers
2. **Agent discovery across subnets** - Validates that agents can discover and communicate with agents in different network segments
3. **Cross-AS transaction flows** - Tests that transactions can flow between agents in different autonomous systems
4. **Shared state communication** - Validates that the shared state mechanism works across different network boundaries
5. **Network connectivity validation** - Ensures the network topology is properly connected and functional

## Test Architecture

### Test Components

- **`test_hierarchical_addressing.py`** - Main test implementation with 6 comprehensive test cases
- **`run_hierarchical_addressing_test.py`** - Test runner with analysis and reporting capabilities
- **Test reports** - JSON and console output with detailed results and recommendations

### Network Topology

The test is designed to work with the global 20-agent configuration that includes:

- **5 Autonomous Systems (AS)**:
  - AS 65001: North America (10.0.0.0/24)
  - AS 65002: Europe (192.168.0.0/24)
  - AS 65003: Asia (172.16.0.0/24)
  - AS 65004: South America (10.1.0.0/24)
  - AS 65005: Africa (10.2.0.0/24)

- **20 Agents distributed across continents**:
  - 5 miners (1 per continent)
  - 15 regular users with transaction capabilities

## Usage

### Prerequisites

Ensure you have the required files in your project directory:

```bash
# Required configuration files
config_global_20_agents.yaml
global_network_20_nodes_no_comments.gml

# Required directories
/tmp/monerosim_shared/  # Will be created automatically
```

### Running the Test

#### Option 1: Full Test Execution

Run the complete test suite with setup and analysis:

```bash
python3 scripts/run_hierarchical_addressing_test.py
```

#### Option 2: Test Only (Skip Setup)

If you've already verified the environment:

```bash
python3 scripts/run_hierarchical_addressing_test.py --skip-setup
```

#### Option 3: Analysis Only

Analyze existing test results without running new tests:

```bash
python3 scripts/run_hierarchical_addressing_test.py --analyze-only
```

#### Option 4: Direct Test Execution

Run the test directly with custom logging:

```bash
python3 scripts/test_hierarchical_addressing.py --log-level DEBUG
```

### Command Line Options

```bash
python3 scripts/run_hierarchical_addressing_test.py [OPTIONS]

Options:
  --shared-dir PATH     Shared directory for simulation state (default: /tmp/monerosim_shared)
  --log-level LEVEL     Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --skip-setup          Skip environment setup checks
  --analyze-only        Only analyze existing test results, don't run tests
  --help               Show help message
```

## Test Cases

### 1. Network Topology Validation

**Purpose**: Validates the overall network structure and IP address assignment.

**Validates**:
- All expected autonomous systems are present
- IP addresses are correctly assigned to AS subnets
- Agent distribution across AS groups
- Network connectivity and structure

**Expected Results**:
- All 5 AS groups (65001-65005) present
- IP addresses within correct subnet ranges
- At least 20 agents distributed across AS groups

### 2. AS-Aware IP Assignment

**Purpose**: Ensures IP addresses are correctly mapped to autonomous systems.

**Validates**:
- IP to AS mapping accuracy
- Subnet range compliance
- AS boundary integrity

**Expected Results**:
- 100% correct IP to AS mappings
- No IP addresses outside designated subnets

### 3. Agent Discovery Across Subnets

**Purpose**: Tests agent discovery capabilities across different network segments.

**Validates**:
- Cross-subnet agent visibility
- Agent registry functionality
- Network boundary transparency

**Expected Results**:
- All agents can discover agents in other AS groups
- Agent registry contains complete network information

### 4. Shared State Communication

**Purpose**: Validates shared state mechanisms work across network boundaries.

**Validates**:
- Shared file accessibility
- Cross-network data synchronization
- State persistence and integrity

**Expected Results**:
- All critical shared state files exist and are readable
- Data integrity maintained across network segments

### 5. Cross-AS Transaction Flow

**Purpose**: Tests transaction capabilities between different autonomous systems.

**Validates**:
- Transaction routing across AS boundaries
- Wallet functionality in different subnets
- Cross-network payment processing

**Expected Results**:
- Transactions can flow between different AS groups
- Wallet operations work across network boundaries

### 6. Network Connectivity Validation

**Purpose**: Ensures the network topology is properly connected.

**Validates**:
- Graph connectivity
- Network path availability
- Topology integrity

**Expected Results**:
- Network graph is fully connected
- No isolated network segments

## Output and Reporting

### Console Output

The test runner provides real-time console output with:

```
🚀 Starting Hierarchical Addressing and Inter-Network Communication Test
================================================================================
✅ Test environment setup complete
⏱️  Execution Time: 2.34 seconds

================================================================================
HIERARCHICAL ADDRESSING TEST ANALYSIS REPORT
================================================================================

📊 SUMMARY:
  Overall Result: PASSED
  Success Rate: 100.0%
  Tests Passed: 6/6

🏥 NETWORK HEALTH:
  Status: Excellent
  Health Score: 6/6
  AS Coverage: 5/5

⚡ PERFORMANCE METRICS:
  AS Groups: 5
  Test Coverage: 6 tests
  AS Distribution:
    AS 65001: 5 agents (25.0%)
    AS 65002: 4 agents (20.0%)
    AS 65003: 6 agents (30.0%)
    AS 65004: 3 agents (15.0%)
    AS 65005: 2 agents (10.0%)

💡 RECOMMENDATIONS:
  1. Network topology and addressing system are functioning correctly
  2. Consider adding more comprehensive cross-AS transaction testing
================================================================================
```

### JSON Report

Detailed results are saved to:
```
/tmp/monerosim_shared/hierarchical_addressing_test_report.json
```

Contains:
- Complete test results with details
- Network topology information
- Performance metrics
- Recommendations for improvement

## Troubleshooting

### Common Issues

#### Missing Required Files

**Error**: `❌ Missing required files: ['global_network_20_nodes_no_comments.gml', 'config_global_20_agents.yaml']`

**Solution**:
```bash
# Ensure you have the required files
ls -la global_network_20_nodes_no_comments.gml config_global_20_agents.yaml
```

#### Shared Directory Issues

**Error**: `Failed to create shared directory`

**Solution**:
```bash
# Create shared directory manually
mkdir -p /tmp/monerosim_shared
chmod 755 /tmp/monerosim_shared
```

#### Permission Issues

**Error**: `Permission denied` when accessing shared files

**Solution**:
```bash
# Fix permissions
chmod -R 755 /tmp/monerosim_shared
```

#### Test Execution Fails

**Error**: Tests fail with various errors

**Solution**:
1. Check that the simulation has been run and generated the required shared state files
2. Verify agent registry and miner registry exist
3. Check log files for detailed error information

### Debug Mode

Run tests with debug logging for detailed information:

```bash
python3 scripts/run_hierarchical_addressing_test.py --log-level DEBUG
```

## Integration with Simulation Workflow

### Complete Testing Workflow

1. **Setup Environment**:
   ```bash
   # Ensure all required files are present
   ls config_global_20_agents.yaml global_network_20_nodes_no_comments.gml
   ```

2. **Generate Shadow Configuration**:
   ```bash
   cargo run -- --config config_global_20_agents.yaml --output shadow_agents_output
   ```

3. **Run Simulation**:
   ```bash
   rm -rf shadow.data && shadow shadow_agents_output/shadow_agents.yaml
   ```

4. **Run Hierarchical Addressing Tests**:
   ```bash
   python3 scripts/run_hierarchical_addressing_test.py
   ```

5. **Analyze Results**:
   ```bash
   # View detailed report
   cat /tmp/monerosim_shared/hierarchical_addressing_test_report.json | jq .
   ```

## Performance Considerations

### Test Execution Time

- **Typical execution**: 2-5 seconds
- **With debug logging**: 5-10 seconds
- **Large networks**: May take longer depending on agent count

### Resource Requirements

- **Memory**: Minimal additional memory beyond simulation
- **Disk**: ~1MB for test reports and logs
- **CPU**: Light processing for analysis

## Extending the Test Suite

### Adding New Test Cases

1. Add test method to `HierarchicalAddressingTest` class
2. Follow the pattern of existing tests
3. Return `TestResult` with appropriate details
4. Update test runner analysis if needed

### Custom Network Topologies

1. Create new GML topology file
2. Update configuration file
3. Modify subnet mappings in test if needed
4. Run tests with new configuration

## API Reference

### HierarchicalAddressingTest Class

```python
class HierarchicalAddressingTest:
    def __init__(self, shared_dir: Path, log_level: str = "INFO")
    def run_all_tests(self) -> bool
    def load_network_topology(self) -> NetworkTopology
    # ... additional methods
```

### TestResult Class

```python
@dataclass
class TestResult:
    test_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None
```

## Contributing

When contributing to the test suite:

1. Follow existing code patterns and naming conventions
2. Add comprehensive error handling
3. Include detailed logging for debugging
4. Update documentation for new features
5. Test with multiple network configurations

## Related Documentation

- [Agent Framework Documentation](AGENT_FRAMEWORK.md)
- [Network Configuration Guide](CONFIGURATION.md)
- [GML Topology Guide](GML_IP_ASSIGNMENT_AS_DISTRIBUTION.md)
- [Transaction User Agent Design](TRANSACTION_USER_AGENT_DESIGN.md)