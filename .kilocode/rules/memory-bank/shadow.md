# Shadow Network Simulator Architecture

## Overview

Shadow is a discrete-event network simulator that enables the simulation of large-scale networks on a single machine. It's particularly valuable for Monerosim as it allows us to run multiple Monero nodes in a controlled environment without requiring separate physical machines or complex network setups.

## Core Architecture

Shadow's architecture consists of several key components:

```
┌─────────────────────────────────────────────────────────────┐
│                     Shadow Core                             │
├─────────────────────────────────────────────────────────────┤
│  Discrete Event Engine                                      │
│  ├── Event Scheduler                                       │
│  ├── Virtual Clock                                         │
│  └── Simulation Controller                                 │
├─────────────────────────────────────────────────────────────┤
│  Virtual Network Stack                                      │
│  ├── Network Topology                                      │
│  ├── Routing                                               │
│  ├── Transport Protocols (TCP/UDP)                         │
│  └── Bandwidth/Latency Modeling                            │
├─────────────────────────────────────────────────────────────┤
│  Process Management                                         │
│  ├── Virtual Hosts                                         │
│  ├── Process Virtualization                                │
│  ├── System Call Interception                              │
│  └── Resource Management                                   │
└─────────────────────────────────────────────────────────────┘
```

### 1. Discrete Event Engine

- **Event Scheduler**: Manages the sequence of events in the simulation
- **Virtual Clock**: Maintains simulation time, which can be faster or slower than real time
- **Simulation Controller**: Coordinates the overall simulation execution

### 2. Virtual Network Stack

- **Network Topology**: Defines the structure of the simulated network
- **Routing**: Handles packet routing between virtual hosts
- **Transport Protocols**: Implements TCP/UDP for communication
- **Bandwidth/Latency Modeling**: Simulates realistic network conditions

### 3. Process Management

- **Virtual Hosts**: Simulates individual machines with their own IP addresses
- **Process Virtualization**: Runs actual application binaries in a controlled environment
- **System Call Interception**: Intercepts and virtualizes system calls
- **Resource Management**: Controls CPU, memory, and other resources

## Shadow Configuration

Shadow uses YAML configuration files to define the simulation parameters:

### General Configuration

```yaml
general:
  stop_time: 10800s
  model_unblocked_syscall_latency: true
  log_level: trace
```

- **stop_time**: Duration of the simulation
- **model_unblocked_syscall_latency**: Enables more realistic system call timing
- **log_level**: Controls the verbosity of logging

### Network Configuration

```yaml
network:
  graph:
    type: 1_gbit_switch
```

- **graph.type**: Defines the network topology (e.g., switch, internet, custom)

### Experimental Features

```yaml
experimental:
  use_dynamic_runahead: true
```

- **use_dynamic_runahead**: Optimizes simulation performance

### Host Configuration

```yaml
hosts:
  a0:
    network_node_id: 0
    ip_addr: 11.0.0.1
    processes:
    - path: /path/to/binary
      args: --arg1 --arg2
      environment:
        ENV_VAR1: value1
      start_time: 0s
```

- **network_node_id**: Identifies the network node this host is connected to
- **ip_addr**: IP address assigned to the host
- **processes**: List of processes to run on this host
  - **path**: Path to the executable
  - **args**: Command-line arguments
  - **environment**: Environment variables
  - **start_time**: When to start the process in simulation time

## Shadow-Monero Integration

### Compatibility Challenges

Running Monero in Shadow requires several adaptations:

1. **Network Virtualization**: Monero's P2P networking code must work with Shadow's virtualized network stack
2. **Time Handling**: Monero's time-based operations must be compatible with Shadow's virtual clock
3. **Resource Constraints**: Monero must operate efficiently within Shadow's resource allocation
4. **DNS and Seed Nodes**: Monero's DNS-based peer discovery must be disabled in Shadow

### Required Modifications

The following modifications are necessary for Monero to run in Shadow:

1. **Disable Seed Nodes**: Prevent Monero from attempting to connect to external seed nodes
2. **Disable DNS Checkpoints**: Prevent DNS-based checkpoint verification
3. **Fixed Difficulty**: Use a fixed mining difficulty for predictable block generation
4. **Resource Optimization**: Limit thread usage and memory consumption
5. **P2P Configuration**: Configure explicit peer connections instead of discovery

## Monerosim-Shadow Integration

Monerosim generates Shadow configuration files that define:

1. **Network Topology**: How Monero nodes are connected
2. **Node Configuration**: Settings for each Monero daemon
3. **Wallet Configuration**: Settings for wallet processes
4. **Test Scripts**: Configuration for test and monitoring scripts

### Configuration Generation Process

1. Monerosim parses the user's configuration file
2. It generates a Shadow YAML configuration with:
   - Network settings
   - Host definitions for each Monero node
   - Process definitions with appropriate command-line arguments
   - Environment variables for performance optimization
   - Start times to ensure proper initialization sequence

### Performance Optimizations

Shadow simulations with Monero benefit from several optimizations:

1. **Memory Management**:
   ```
   MALLOC_MMAP_THRESHOLD_: '131072'
   MALLOC_TRIM_THRESHOLD_: '131072'
   GLIBC_TUNABLES: glibc.malloc.arena_max=1
   MALLOC_ARENA_MAX: '1'
   ```

2. **Process Scheduling**:
   - Staggered start times prevent resource contention
   - Proper sequencing ensures dependencies are satisfied

3. **Network Optimization**:
   - Bandwidth and connection limits prevent network congestion
   - Explicit peer configuration ensures reliable connectivity

## Shadow Execution Model

When Shadow runs a simulation:

1. It loads the configuration file and initializes the simulation environment
2. It creates virtual hosts with their assigned IP addresses
3. It starts processes according to their specified start times
4. It routes network traffic between processes according to the network topology
5. It advances the simulation clock based on event processing
6. It collects logs and performance data throughout the simulation
7. It terminates when the specified stop_time is reached

## Debugging and Monitoring

Shadow provides several mechanisms for debugging and monitoring:

1. **Logging**: Comprehensive logging of network and process activities
2. **Process Output**: Capture of stdout/stderr from all processes
3. **Network Statistics**: Detailed statistics on network performance
4. **Event Tracing**: Tracing of discrete events for performance analysis

## Current Challenges in Monerosim-Shadow Integration

1. **P2P Connectivity**: Ensuring reliable P2P connections between Monero nodes
2. **Wallet Integration**: Proper initialization and operation of wallet processes
3. **Block Generation**: Consistent and reliable block generation in the mining node
4. **Transaction Processing**: End-to-end verification of transaction processing

## Future Enhancements

1. **Advanced Network Topologies**: Support for more complex network structures
2. **Network Condition Simulation**: Simulation of packet loss, jitter, and other network conditions
3. **Scalability Improvements**: Optimizations for larger simulations with more nodes
4. **Visualization Tools**: Better tools for visualizing simulation results