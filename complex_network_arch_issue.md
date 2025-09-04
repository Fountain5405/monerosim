# Complex Network Architecture Issue

## Issue Summary

The GML-based network topology system is not properly utilizing the IP addresses defined in the GML file, resulting in all agents being assigned to the same subnet instead of different subnets across multiple Autonomous Systems (ASes).

## Problem Description

### Expected Behavior
- **AS 65001**: Agents should be assigned to 10.0.0.x subnet
- **AS 65002**: Agents should be assigned to 192.168.0.x subnet  
- **AS 65003**: Agents should be assigned to 172.16.0.x subnet
- Cross-subnet communication should demonstrate realistic network latency and routing

### Actual Behavior
- All agents are assigned to the same subnet: 11.0.0.x (sequential addresses)
- No cross-subnet communication occurs
- The complex GML topology is effectively ignored

## Technical Details

### GML File Structure (`realistic_internet.gml`)
```gml
graph [
  directed 1
  
  # AS 65001
  node [ id 0 AS "65001" bandwidth "1000Mbit" ip "10.0.0.1" ]
  node [ id 1 AS "65001" bandwidth "500Mbit" ip "10.0.0.2" ]
  
  # AS 65002  
  node [ id 2 AS "65002" bandwidth "100Mbit" ip "192.168.0.1" ]
  node [ id 3 AS "65002" bandwidth "100Mbit" ip "192.168.0.2" ]
  
  # AS 65003
  node [ id 4 AS "65003" bandwidth "10Mbit" ip "172.16.0.1" ]
  node [ id 5 AS "65003" bandwidth "10Mbit" ip "172.16.0.2" ]
]
```

### Shadow Configuration Output (`shadow_agents.yaml`)
```yaml
hosts:
  user035:
    network_node_id: 5
    ip_addr: 11.0.0.45  # Should be 172.16.0.x based on GML
  user002:
    network_node_id: 4  
    ip_addr: 11.0.0.12  # Should be 172.16.0.x based on GML
  user006:
    network_node_id: 0
    ip_addr: 11.0.0.16  # Should be 10.0.0.x based on GML
```

### Root Cause
The issue is in [`src/shadow_agents.rs`](src/shadow_agents.rs) where IP addresses are assigned using a sequential pattern (11.0.0.10, 11.0.0.11, etc.) instead of using the actual IP addresses defined in the GML file.

## Impact

1. **Research Validity**: Simulations don't accurately model real internet conditions
2. **Network Effects**: Missing realistic latency, bandwidth constraints, and routing patterns
3. **GML Features**: Complex topology definitions are wasted
4. **Agent Behavior**: Agents don't experience realistic cross-AS communication

## Files Involved

- **Primary**: [`src/shadow_agents.rs`](src/shadow_agents.rs) - IP address assignment logic
- **Configuration**: [`config_realistic_internet.yaml`](config_realistic_internet.yaml) - GML topology definition
- **GML Data**: [`realistic_internet.gml`](realistic_internet.gml) - Network topology specification
- **Output**: [`shadow_realistic_internet_output/shadow_agents.yaml`](shadow_realistic_internet_output/shadow_agents.yaml) - Generated Shadow configuration

## Required Fix

The IP address assignment logic in [`src/shadow_agents.rs`](src/shadow_agents.rs) needs to be modified to:

1. Extract actual IP addresses from GML node definitions
2. Assign agents to these different subnets based on their assigned network_node_id
3. Preserve the AS-aware distribution for realistic network conditions
4. Ensure cross-subnet communication uses proper routing and latency

## Current Workaround

None identified. The issue requires code changes to properly utilize GML IP address information.

## Next Steps

1. Modify [`src/shadow_agents.rs`](src/shadow_agents.rs) to use GML node IP addresses
2. Update IP address assignment logic to respect subnet boundaries
3. Test with cross-subnet communication scenarios
4. Verify realistic network conditions are properly simulated

## Status

- **Issue Identified**: ✅
- **Root Cause Found**: ✅  
- **Fix Required**: ❌ (pending code changes)
- **Testing**: ❌ (pending fix implementation)

## Date Identified

2025-08-26

## Machine Context

Issue identified on development machine. Resolution requires access to the codebase and testing environment.