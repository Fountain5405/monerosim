# Difficulty-Aware Mining Implementation

## Problem Statement

The current synthetic mining system does not properly simulate Monero's dynamic difficulty adjustment (LWMA - Linear Weighted Moving Average). This limits the ability to test:
- Hashrate attacks (51% attacks)
- Selfish mining strategies
- Network response to sudden hashrate changes

## Current State: Difficulty is Ignored

The autonomous miners calculate block timing using only configured hashrate weights:

```python
# In autonomous_miner.py _calculate_next_block_time()
hashrate_fraction = self.hashrate_pct / self.discovered_total_hashrate
expected_block_time = 120.0 / hashrate_fraction  # Fixed, ignores difficulty
```

The daemon's difficulty is queried via `_get_current_difficulty()` but **never used in timing decisions**.

## The Problem

| Real Mining | Current System |
|-------------|----------------|
| Higher difficulty → slower blocks | Difficulty ignored |
| LWMA adjusts difficulty every block | LWMA runs but miners don't react |
| Attack causes difficulty spike → honest miners slow | Miners maintain constant rate |
| Feedback loop stabilizes network | No feedback loop |

### Impact on Attack Simulations

- **51% Attack**: Attacker dominance should trigger difficulty increases that slow honest miners. Currently, honest miners maintain constant rate regardless of difficulty changes.

- **Selfish Mining**: Strategy effectiveness depends on difficulty adjustment dynamics. Currently, the network can't naturally "push back" against attacks.

- **Hashrate Fluctuations**: When miners join/leave, difficulty should adjust over ~60 blocks. Currently, timing adjusts instantly via discovery but ignores LWMA's gradual adjustment.

## How Monero's LWMA Works

1. **Window Size**: Last 60 blocks
2. **Target Block Time**: 120 seconds
3. **Adjustment**: Recalculated every block based on recent block timestamps
4. **Effect**: If blocks arrive faster than 120s average, difficulty increases; if slower, decreases

## Proposed Solution

Incorporate the daemon's difficulty into the timing calculation by scaling the Poisson rate based on difficulty changes from a baseline:

### Implementation Changes in `autonomous_miner.py`

```python
# In __init__():
self.baseline_difficulty = None  # Set during setup

# In _setup_agent(), after daemon is ready:
self.baseline_difficulty = self._get_current_difficulty()
self.logger.info(f"Baseline difficulty: {self.baseline_difficulty}")

# In _calculate_next_block_time():
def _calculate_next_block_time(self) -> float:
    TARGET_BLOCK_TIME = 120.0

    # Periodically rediscover total network hashrate
    current_time = time.time()
    if current_time - self.last_discovery_time > self.discovery_interval:
        self.discovered_total_hashrate = self._discover_total_network_hashrate()
        self.last_discovery_time = current_time

    # Calculate base timing from hashrate fraction
    hashrate_fraction = self.hashrate_pct / self.discovered_total_hashrate
    base_expected_time = TARGET_BLOCK_TIME / hashrate_fraction

    # Query current difficulty and scale timing
    current_difficulty = self._get_current_difficulty()
    if self.baseline_difficulty and self.baseline_difficulty > 0:
        difficulty_factor = current_difficulty / self.baseline_difficulty
    else:
        difficulty_factor = 1.0

    # Higher difficulty = longer expected time (slower mining)
    expected_agent_block_time = base_expected_time * difficulty_factor

    # Poisson timing
    lambda_rate = 1.0 / expected_agent_block_time
    u = random.random()
    if u >= 1.0:
        u = 0.999999
    time_seconds = -math.log(1.0 - u) / lambda_rate

    self.logger.debug(f"Next block in {time_seconds:.1f}s "
                     f"(difficulty factor: {difficulty_factor:.2f})")

    return time_seconds
```

### How This Creates Feedback Loop

1. Blocks arrive too fast → LWMA increases difficulty
2. Miners query increased difficulty → `difficulty_factor > 1.0`
3. `expected_agent_block_time` increases → miners slow down
4. Block times stabilize back toward 120s target

### For Attack Simulations

- **Attacker dominates**: Difficulty rises, honest miners slow proportionally
- **Attacker leaves**: Difficulty drops, honest miners speed up
- **Selfish mining**: Orphan rates and fork resolution interact with difficulty changes

## Alternative Approaches Considered

### Option A: Use Absolute Difficulty in Formula
```python
# More realistic but requires defining "hashrate" in H/s
agent_hashrate_hs = (self.hashrate_pct / 100.0) * NETWORK_HASHRATE_HS
lambda_rate = agent_hashrate_hs / current_difficulty
```
**Drawback**: Requires defining what hashrate weights mean in H/s.

### Option B: Relative Difficulty Scaling (Proposed)
```python
difficulty_factor = current_difficulty / baseline_difficulty
expected_time = base_expected_time * difficulty_factor
```
**Advantage**: Works with abstract hashrate weights, simpler to implement.

## Testing the Implementation

1. Run simulation with stable hashrate distribution
2. Verify difficulty stabilizes and block times average ~120s
3. Add a high-hashrate miner mid-simulation
4. Observe difficulty increase and existing miners slowing down
5. Remove the high-hashrate miner
6. Observe difficulty decrease and remaining miners speeding up

## Status

**IMPLEMENTED (Difficulty-Only Mode)** - Changes made to `agents/autonomous_miner.py`:
- Added `baseline_difficulty` tracking in `__init__` and `_setup_agent`
- Updated `_calculate_next_block_time()` to use difficulty-only mode:
  - Base timing assumes hashrate weights sum to 100 at simulation start
  - Timing scales ONLY with difficulty factor (current / baseline)
  - Removed hashrate discovery from timing to avoid double-counting
- Removed `_discover_total_network_hashrate()` method (no longer needed)
- Updated statistics and logging to show difficulty factor

### Why Difficulty-Only Mode?

Using both hashrate discovery AND difficulty adjustment caused double-counting:
- If a new miner with weight 40 joins (total 100 → 140)
- Hashrate discovery alone: existing miners slow 1.4x (immediate)
- Difficulty adjustment alone: LWMA increases difficulty 1.4x → miners slow 1.4x (gradual)
- Combined: 1.4 × 1.4 = 1.96x slowdown (WRONG!)

Difficulty-only mode:
- Miners use hashrate_pct / 100 as their base fraction
- LWMA naturally increases difficulty when more hashrate joins
- All miners slow down proportionally through the difficulty factor
- Produces realistic ~60 block adjustment period
