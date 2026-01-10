# Plan: Add Realtime Throttle Mode to Shadow for Bootstrap Sync

## Problem Statement

With 1000 nodes, Shadow takes 4+ hours of wall-clock time to spawn all processes. During this time:
- Sim time advances rapidly (miners keep mining)
- Nodes don't have enough wall-clock time to actually sync with each other
- Result: 3-4h sim time passes before nodes are even running

**Key insight**: A "true pause" won't help because nodes need network events to sync. What we need is **throttling** - force sim time to advance at most 1:1 with wall-clock time during bootstrap.

## Solution: Realtime Throttle Mode

Add a `realtime_ratio` config option that throttles simulation to a specified ratio of sim:wall time during bootstrap period.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                Shadow Scheduling Loop                        │
│                                                              │
│  for each round:                                             │
│    wall_start = Instant::now()                              │
│    execute_events(window_start, window_end)                 │
│    wall_elapsed = wall_start.elapsed()                      │
│    sim_advanced = window_end - window_start                 │
│                                                              │
│    if in_bootstrap && realtime_ratio > 0:                   │
│      target_wall = sim_advanced / realtime_ratio            │
│      if wall_elapsed < target_wall:                         │
│        sleep(target_wall - wall_elapsed)  // THROTTLE HERE  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Example with `realtime_ratio: 1.0`**:
- If a round advances 100ms of sim time
- And wall-clock took only 10ms to execute
- We sleep for 90ms to enforce 1:1 pacing
- Nodes now have real time to process network events

## Implementation

### Phase 1: Shadow Modifications (shadowformonero)

#### 1.1 Add Configuration Option

**File**: `~/monerosim_dev/shadowformonero/src/main/core/configuration.rs`

Add to `GeneralOptions` (around line 408):
```rust
/// Throttle simulation to this ratio of sim:wall time during bootstrap
/// 1.0 = realtime (1 sec sim = 1 sec wall), 0.0 = disabled (default)
/// Only active when bootstrap_end_time is set
#[clap(long, value_name = "ratio")]
#[serde(default)]
pub bootstrap_realtime_ratio: Option<f64>,
```

#### 1.2 Add Throttle Logic to Scheduling Loop

**File**: `~/monerosim_dev/shadowformonero/src/main/core/manager.rs`

In the scheduling loop (around line 415), add throttling:
```rust
use std::time::{Duration, Instant};

// Before the loop, get config
let realtime_ratio = self.config.general.bootstrap_realtime_ratio.unwrap_or(0.0);
let bootstrap_end = self.config.general.bootstrap_end_time
    .map(|t| EmulatedTime::SIMULATION_START + t)
    .unwrap_or(EmulatedTime::SIMULATION_START);

// Inside the scheduling loop:
while let Some((window_start, window_end)) = window {
    let is_in_bootstrap = window_start < bootstrap_end;
    let should_throttle = is_in_bootstrap && realtime_ratio > 0.0;

    // Record wall-clock time before execution
    let wall_start = if should_throttle { Some(Instant::now()) } else { None };

    // === EXISTING EVENT EXECUTION CODE ===
    scheduler.scope(|s| {
        // ... existing parallel host execution ...
    });
    // === END EXISTING CODE ===

    // Throttle if in bootstrap mode
    if let Some(start) = wall_start {
        let wall_elapsed = start.elapsed();
        let sim_advanced = window_end - window_start;
        let target_wall = Duration::from_secs_f64(
            sim_advanced.as_secs_f64() / realtime_ratio
        );

        if wall_elapsed < target_wall {
            let sleep_duration = target_wall - wall_elapsed;
            log::trace!(
                "Throttling: sim={}ms, wall={}ms, sleeping {}ms",
                sim_advanced.as_millis(),
                wall_elapsed.as_millis(),
                sleep_duration.as_millis()
            );
            std::thread::sleep(sleep_duration);
        }
    }

    // ... rest of existing code ...
}
```

#### 1.3 Update WorkerShared (if needed)

**File**: `~/monerosim_dev/shadowformonero/src/main/core/worker.rs`

May need to store bootstrap_end_time for access in worker threads:
```rust
pub struct WorkerShared {
    // ... existing fields ...
    pub bootstrap_end_time: EmulatedTime,
    pub realtime_ratio: f64,
}
```

### Phase 2: Monerosim Integration

#### 2.1 Update Config Types

**File**: `src/config_v2.rs`
```rust
/// Throttle simulation to realtime during bootstrap (1.0 = 1:1 ratio)
#[serde(skip_serializing_if = "Option::is_none")]
pub bootstrap_realtime_ratio: Option<f64>,
```

**File**: `src/shadow/types.rs`
```rust
#[serde(skip_serializing_if = "Option::is_none")]
pub bootstrap_realtime_ratio: Option<f64>,
```

#### 2.2 Update generate_config.py

**File**: `scripts/generate_config.py`
```python
# Add to general_config:
"bootstrap_realtime_ratio": 1.0,  # 1:1 sim:wall during bootstrap
```

### Phase 3: Usage

#### Config Example
```yaml
general:
  stop_time: 4h
  bootstrap_end_time: 2h           # First 2h is bootstrap period
  bootstrap_realtime_ratio: 1.0    # Run at 1:1 during bootstrap
  # After bootstrap_end_time, full speed resumes
```

#### Timeline with 1000 nodes
```
Wall time 0min:     Sim time 0min     - Miners start
Wall time 30min:    Sim time 30min    - 1000 users spawn (throttled, enough time)
Wall time 2h:       Sim time 2h       - Bootstrap ends, throttle disabled
Wall time 2h+10min: Sim time 4h       - Simulation ends (fast mode)
```

### Advanced Mode: Block-Synchronized Clock

An even more elegant approach - synchronize Shadow's clock to the blockchain's block height:

**Concept**:
1. An agent (e.g., simulation_monitor) writes current block height to a "sync file"
2. Shadow reads this file and only advances sim time when block height advances
3. Sim time = block_height * block_time (e.g., 1 block = 2 minutes)

**Implementation**:
```rust
// In manager.rs scheduling loop:
let sync_file = Path::new("/tmp/monerosim_shared/block_sync.txt");

while let Some((window_start, window_end)) = window {
    if is_in_bootstrap && block_sync_enabled {
        // Read current block height from sync file
        let current_block = fs::read_to_string(&sync_file)
            .ok()
            .and_then(|s| s.trim().parse::<u64>().ok())
            .unwrap_or(0);

        // Calculate max sim time allowed based on block height
        let max_sim_time = current_block * BLOCK_TIME_SECONDS;

        // If we're ahead of blockchain, wait
        while window_end.as_secs() > max_sim_time {
            std::thread::sleep(Duration::from_millis(100));
            // Re-read sync file
            current_block = fs::read_to_string(&sync_file)...;
            max_sim_time = current_block * BLOCK_TIME_SECONDS;
        }
    }
    // ... execute events ...
}
```

**Sync Agent** (writes to sync file):
```python
# In simulation_monitor.py or dedicated block_sync_agent.py:
def update_block_sync(self):
    heights = [self.get_node_height(node) for node in self.nodes]
    consensus_height = min(heights)  # Or mode/median
    sync_file = self.shared_dir / "block_sync.txt"
    sync_file.write_text(str(consensus_height))
```

**Benefits**:
- Sim time perfectly tracks blockchain progress
- Nodes always have time to sync each block
- Deterministic (same blocks = same sim time)
- Self-regulating (fast hardware syncs faster, slow hardware still works)

**Config**:
```yaml
general:
  bootstrap_end_time: 2h
  block_sync_enabled: true
  block_sync_file: /tmp/monerosim_shared/block_sync.txt
  block_time: 120  # 2 minutes per block
```

## Key Files to Modify

### For Realtime Throttle (Phase 1)
| File | Changes |
|------|---------|
| `shadowformonero/src/main/core/configuration.rs` | Add `bootstrap_realtime_ratio` option |
| `shadowformonero/src/main/core/manager.rs` | Add throttle logic in scheduling loop (~30 LOC) |
| `monerosim/src/config_v2.rs` | Add `bootstrap_realtime_ratio` config |
| `monerosim/src/shadow/types.rs` | Add to Shadow config types |

### For Block-Sync Mode (Phase 2, Advanced)
| File | Changes |
|------|---------|
| `shadowformonero/src/main/core/configuration.rs` | Add `block_sync_enabled`, `block_sync_file`, `block_time` |
| `shadowformonero/src/main/core/manager.rs` | Add block-sync wait logic (~40 LOC) |
| `monerosim/agents/simulation_monitor.py` | Add block height sync file writing |
| `monerosim/scripts/generate_config.py` | Add block-sync options |

## Determinism

**Realtime throttle does NOT affect determinism** because:
- Only wall-clock pacing changes, not event order
- Same events execute in same order with same timestamps
- Random seeds unchanged
- Sleep only adds delays, doesn't change simulation logic

## Verification

1. **Build Shadow with changes**:
   ```bash
   cd ~/monerosim_dev/shadowformonero
   cargo build --release
   cp target/release/shadow ~/.monerosim/bin/
   ```

2. **Test throttle mode**:
   ```bash
   # Generate config with throttle enabled
   python scripts/generate_config.py --agents 100 -o test.yaml
   # Add to test.yaml:
   #   bootstrap_realtime_ratio: 1.0

   # Run and observe wall-clock pacing
   time shadow test.yaml
   # Should take ~2h wall time for 2h bootstrap (1:1 ratio)
   ```

3. **Compare with non-throttled**:
   ```bash
   # Run without throttle (or ratio: 0.0)
   # Should complete much faster but nodes may not sync properly
   ```

4. **Verify determinism**:
   ```bash
   # Run twice with same seed and throttle
   # Compare final blockchain heights - should be identical
   ```

## Estimated Effort

### Phase 1: Realtime Throttle
- **Shadow changes**: ~2-4 hours (small, localized changes)
- **Monerosim integration**: ~1 hour
- **Testing**: ~2-4 hours
- **Total**: ~1 day

### Phase 2: Block-Sync Mode (after Phase 1 proven)
- **Shadow changes**: ~2-3 hours
- **Sync agent**: ~2-3 hours
- **Testing**: ~3-4 hours
- **Total**: ~1 day

## Implementation Recommendation

**Start with Phase 1 (realtime throttle)** - simpler, proves the concept.
If needed, **add Phase 2 (block-sync)** for more precise control.

## Future Enhancements

- **Dynamic throttle**: Adjust ratio based on sync progress
- **External throttle control**: Signal-based pause/resume on top of throttle
- **Block-sync with consensus**: Use median height across nodes instead of min
- **Upstream contribution**: Propose to shadow-simulator/shadow

## Repositories Involved

This feature requires changes to **2 repositories**:

1. **shadowformonero** (`~/monerosim_dev/shadowformonero/`)
   - Core throttle/block-sync logic in scheduling loop
   - New configuration options

2. **monerosim** (`~/monerosim_dev/monerosim/`)
   - Config types to pass options to Shadow
   - Block sync agent (for Phase 2)
   - Config generation updates
