# Network Split (Partition) Scenario Implementation Plan

## Overview

This document outlines the modifications needed to enable dynamic network partitions in monerosim simulations. Network partitions are essential for testing blockchain consensus behavior, fork scenarios, and network resilience.

**Problem**: Shadow's network topology is currently static - defined at simulation startup and immutable throughout execution.

**Solution**: Modify shadowformonero to support time-based network events that can block/unblock paths between node groups, simulating network partitions.

---

## Current Architecture

### How Shadow Routes Packets

1. **Startup**: GML topology parsed, shortest paths precomputed via Dijkstra
2. **Storage**: `RoutingInfo` struct holds immutable path properties (latency, packet_loss)
3. **Packet delivery** (`src/main/core/worker.rs:356-368`):
   ```rust
   let reliability = worker.shared.reliability(src, dst);  // Returns 1.0 - packet_loss
   let chance = random();
   if chance >= reliability {
       packet.drop();  // Packet lost
   }
   ```

### Key Files in shadowformonero

| File | Purpose |
|------|---------|
| `src/main/network/graph/mod.rs` | `NetworkGraph`, `RoutingInfo`, `PathProperties` |
| `src/main/core/worker.rs` | `WorkerShared`, packet delivery logic |
| `src/main/core/sim_config.rs` | Configuration parsing, `generate_routing_info()` |
| `src/main/core/configuration.rs` | YAML config schema |

### Existing Time-Based Behavior

Shadow already has `bootstrap_end_time` - a time after which normal packet loss applies. This proves time-dependent network behavior is architecturally supported.

```rust
// worker.rs:330
let is_bootstrapping = current_time < Worker::with(|w| w.shared.bootstrap_end_time).unwrap();

// worker.rs:365 - packets not dropped during bootstrap
if !is_bootstrapping && chance >= reliability && payload_size > 0 {
    // drop packet
}
```

---

## Proposed Implementation

### Approach: Blocked Paths with Time-Based Events

Add a mutable set of "blocked paths" that causes 100% packet loss between specified node pairs. Network events scheduled at specific simulation times update this set.

### Phase 1: Core Shadow Modifications

#### 1.1 Add NetworkEvent Types

**File**: `src/main/core/configuration.rs`

```rust
/// A network topology event that occurs at a specific simulation time
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkEvent {
    /// When the event occurs (simulation time)
    pub time: units::Time<units::TimePrefix>,
    /// The type of network event
    pub event_type: NetworkEventType,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum NetworkEventType {
    /// Create a network partition - nodes in different groups cannot communicate
    Partition {
        /// Groups of node IDs. Nodes within a group can communicate;
        /// nodes in different groups cannot.
        groups: Vec<Vec<u32>>,
    },
    /// Heal a partition - restore connectivity between all nodes
    Heal,
    /// Block specific paths (asymmetric partition possible)
    BlockPaths {
        /// List of (source_node, dest_node) pairs to block
        paths: Vec<(u32, u32)>,
    },
    /// Unblock specific paths
    UnblockPaths {
        /// List of (source_node, dest_node) pairs to unblock
        paths: Vec<(u32, u32)>,
    },
}
```

#### 1.2 Add Configuration Schema

**File**: `src/main/core/configuration.rs`

Add to the network configuration section:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkOptions {
    // ... existing fields ...

    /// Network events (partitions, heals) that occur during simulation
    #[serde(default)]
    pub events: Vec<NetworkEvent>,
}
```

#### 1.3 Modify WorkerShared

**File**: `src/main/core/worker.rs`

```rust
use std::sync::RwLock;
use std::collections::HashSet;

#[derive(Debug)]
pub struct WorkerShared {
    // ... existing fields ...

    /// Set of blocked (src_node, dst_node) pairs - packets between these are dropped
    pub blocked_paths: RwLock<HashSet<(u32, u32)>>,

    /// Scheduled network events, sorted by time
    pub network_events: Vec<NetworkEvent>,

    /// Index of next unprocessed network event
    pub next_network_event: AtomicUsize,
}
```

#### 1.4 Modify reliability() Method

**File**: `src/main/core/worker.rs`

```rust
impl WorkerShared {
    pub fn reliability(&self, src: std::net::IpAddr, dst: std::net::IpAddr) -> Option<f32> {
        let src_node = self.ip_assignment.get_node(src)?;
        let dst_node = self.ip_assignment.get_node(dst)?;

        // Check if path is blocked (network partition)
        {
            let blocked = self.blocked_paths.read().unwrap();
            if blocked.contains(&(src_node, dst_node)) {
                return Some(0.0);  // 100% packet loss = partition
            }
        }

        // Normal reliability from routing info
        Some(1.0 - self.routing_info.path(src_node, dst_node)?.packet_loss)
    }

    /// Process any network events that should occur at or before the given time
    pub fn process_network_events(&self, current_time: EmulatedTime) {
        let current_idx = self.next_network_event.load(Ordering::SeqCst);

        for (i, event) in self.network_events.iter().enumerate().skip(current_idx) {
            let event_time = EmulatedTime::SIMULATION_START +
                SimulationTime::from_nanos(event.time.convert(units::TimePrefix::Nano).unwrap().value());

            if event_time > current_time {
                break;  // No more events to process yet
            }

            // Process this event
            self.apply_network_event(event);
            self.next_network_event.store(i + 1, Ordering::SeqCst);

            log::info!("Applied network event at {:?}: {:?}", event_time, event.event_type);
        }
    }

    fn apply_network_event(&self, event: &NetworkEvent) {
        let mut blocked = self.blocked_paths.write().unwrap();

        match &event.event_type {
            NetworkEventType::Partition { groups } => {
                // Block all paths between nodes in different groups
                for (i, group_a) in groups.iter().enumerate() {
                    for group_b in groups.iter().skip(i + 1) {
                        for &node_a in group_a {
                            for &node_b in group_b {
                                // Block both directions
                                blocked.insert((node_a, node_b));
                                blocked.insert((node_b, node_a));
                            }
                        }
                    }
                }
            }
            NetworkEventType::Heal => {
                blocked.clear();
            }
            NetworkEventType::BlockPaths { paths } => {
                for &(src, dst) in paths {
                    blocked.insert((src, dst));
                }
            }
            NetworkEventType::UnblockPaths { paths } => {
                for &(src, dst) in paths {
                    blocked.remove(&(src, dst));
                }
            }
        }
    }
}
```

#### 1.5 Hook Event Processing into Simulation Loop

**File**: `src/main/core/worker.rs` or `src/main/core/manager.rs`

Add call to `process_network_events()` at the start of each simulation round:

```rust
// In the main simulation loop, before processing host events:
Worker::with(|w| {
    w.shared.process_network_events(current_time);
}).unwrap();
```

### Phase 2: Configuration Support

#### 2.1 Shadow YAML Schema

```yaml
network:
  graph:
    type: gml
    file:
      path: "topology.gml"

  # NEW: Network events
  events:
    # At 10h, create a 2-way partition
    - time: "10h"
      type: partition
      groups:
        - [0, 1, 2, 3, 4]      # Partition A: nodes 0-4
        - [5, 6, 7, 8, 9]      # Partition B: nodes 5-9

    # At 15h, heal the partition
    - time: "15h"
      type: heal

    # At 20h, create asymmetric partition (A can't reach B, but B can reach A)
    - time: "20h"
      type: block_paths
      paths:
        - [0, 5]
        - [0, 6]
        - [1, 5]
        - [1, 6]
```

### Phase 3: Monerosim Integration

#### 3.1 Update generate_config.py

Add partition scenario support:

```python
def add_network_partition(
    config: dict,
    partition_time: str,
    groups: List[List[str]],  # Agent IDs grouped
    heal_time: Optional[str] = None
):
    """Add network partition events to configuration."""

    if 'network' not in config:
        config['network'] = {}
    if 'events' not in config['network']:
        config['network']['events'] = []

    # Convert agent IDs to node IDs
    # (requires mapping from agent placement to GML node IDs)
    node_groups = convert_agents_to_nodes(groups, config)

    config['network']['events'].append({
        'time': partition_time,
        'type': 'partition',
        'groups': node_groups
    })

    if heal_time:
        config['network']['events'].append({
            'time': heal_time,
            'type': 'heal'
        })
```

#### 3.2 New Scenario Type

Add `--scenario partition` to generate_config.py:

```bash
python generate_config.py \
    --scenario partition \
    --agents 100 \
    --partition-time "10h" \
    --partition-groups "0-49,50-99" \
    --heal-time "20h" \
    --duration "30h"
```

#### 3.3 Example Partition Scenario Config

```yaml
# partition_scenario.yaml
metadata:
  scenario: partition
  description: "50/50 network split at 10h, healed at 20h"

general:
  stop_time: 30h
  bootstrap_end_time: 5h

network:
  path: topology.gml
  events:
    - time: "10h"
      type: partition
      groups:
        - [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]      # 10 nodes
        - [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]  # 10 nodes
    - time: "20h"
      type: heal

agents:
  # ... miner and user definitions ...
```

---

## Testing Plan

### Unit Tests (shadowformonero)

1. **Test blocked path detection**:
   - Add paths to `blocked_paths`
   - Verify `reliability()` returns 0.0

2. **Test partition event processing**:
   - Create partition with 2 groups
   - Verify correct paths are blocked

3. **Test heal event**:
   - After heal, verify `blocked_paths` is empty

### Integration Tests (monerosim)

1. **Simple partition test** (2 miners, 10 users):
   - Partition at t=5h
   - Verify blockchain forks (different heights on each side)
   - Heal at t=10h
   - Verify chain reorganization occurs

2. **Asymmetric partition test**:
   - One-way block
   - Verify expected consensus behavior

---

## Analysis Additions

### New Metrics for Partition Scenarios

Add to tx_analyzer:

```rust
struct PartitionAnalysis {
    /// Block heights on each side of partition over time
    chain_heights_by_partition: HashMap<String, Vec<(f64, u64)>>,

    /// Time for chains to reconverge after heal
    reconvergence_time_seconds: Option<f64>,

    /// Number of orphaned blocks after reconvergence
    orphaned_blocks: u64,

    /// Transaction confirmation delays during partition
    tx_confirmation_delays: Vec<f64>,
}
```

---

## Implementation Order

1. **Phase 1.1-1.2**: Configuration types (1-2 hours)
2. **Phase 1.3-1.4**: WorkerShared modifications (2-3 hours)
3. **Phase 1.5**: Hook into simulation loop (1 hour)
4. **Phase 2**: YAML config support (1-2 hours)
5. **Testing**: Unit + integration tests (2-3 hours)
6. **Phase 3**: Monerosim integration (2-3 hours)

**Total estimated effort**: 10-15 hours

---

## Alternative Approaches Considered

### A: Modify RoutingInfo with path overrides

Add `path_overrides: RwLock<HashMap<(T,T), PathProperties>>` to `RoutingInfo`.

**Pros**: Can also modify latency, not just packet loss
**Cons**: More invasive change to existing struct

### B: Full dynamic graph recomputation

Replace petgraph with mutable structure, recompute Dijkstra on topology change.

**Pros**: Supports arbitrary topology changes (not just partitions)
**Cons**: Expensive for large graphs, complex implementation

### C: Application-level simulation

Use Monero's `set_bans` RPC to simulate partitions.

**Pros**: No Shadow modifications needed
**Cons**: Less realistic (relies on application behavior), may not fully prevent connections

---

## Open Questions

1. **Should partitions affect new connections or only packet delivery?**
   - Current proposal: Only packet delivery (connections time out naturally)
   - Alternative: Also modify `is_routable()` to prevent new connections

2. **How to handle in-flight packets when partition occurs?**
   - Current proposal: Already-scheduled packets still deliver
   - Alternative: Cancel pending packets to blocked destinations

3. **Should we support gradual partition (increasing packet loss over time)?**
   - Could add `PacketLossRamp { start_loss: f32, end_loss: f32, duration: String }`

---

## References

- Shadow source: `/home/lever65/monerosim_scale/shadowformonero/`
- Key file: `src/main/core/worker.rs` (packet delivery at line 356)
- Bootstrap time example: `src/main/core/worker.rs:330`
- RoutingInfo: `src/main/network/graph/mod.rs:434`
