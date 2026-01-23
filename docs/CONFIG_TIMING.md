# Config Generator Timing Reference

This document explains the timing parameters in `generate_config.py` and `scenario_parser.py`, their dependencies, and how they interact.

## Timing Parameters & Defaults

| CLI Flag | Default | Description |
|----------|---------|-------------|
| `--user-spawn-start` | 20m (batched) or 3h (non-batched) | When user processes start spawning |
| `--bootstrap-end-time` | auto-calculated | When bootstrap period ends |
| `--md-start-time` | = bootstrap_end_time | When miner distributor starts funding |
| `--regular-user-start` | = md_start_time + 1h | When users start sending transactions |
| `--duration` | (required) | Total simulation duration |

## Dependency Chain

The timing parameters form a dependency chain where each step depends on the previous:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: User Spawn Start                                                    │
│  ───────────────────────                                                     │
│  user_spawn_start_s = --user-spawn-start                                     │
│                    OR 1200s (20m) if batched                                 │
│                    OR 10800s (3h) if non-batched                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Last User Spawn                                                     │
│  ───────────────────────                                                     │
│  Batched:     last_user_spawn_s = batch_schedule[-1]                         │
│               (depends on user_spawn_start_s + batch intervals)              │
│                                                                              │
│  Non-batched: last_user_spawn_s = user_spawn_start_s + (users-1) * stagger   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Bootstrap End Time                                                  │
│  ──────────────────────────                                                  │
│  bootstrap_end_time_s = --bootstrap-end-time                                 │
│                      OR max(14400, last_user_spawn_s * 1.20)                 │
│                         ─────  ──────────────────────────                    │
│                         4h min    last spawn + 20% buffer                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Miner Distributor Start (wait_time)                                 │
│  ───────────────────────────────────────────                                 │
│  md_start_time_s = --md-start-time                                           │
│                 OR bootstrap_end_time_s                                      │
│                                                                              │
│  ⚠️  Warning if md_start < bootstrap_end (miners may not have enough funds)  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: Activity Start Time (when users start transacting)                  │
│  ──────────────────────────────────────────────────────────                  │
│  activity_start_time_s = --regular-user-start                                │
│                       OR md_start_time_s + 3600 (1h funding period)          │
│                                                                              │
│  ⚠️  Warning if activity_start < md_start (users may not have funds yet)     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: Duration                                                            │
│  ────────────────                                                            │
│  duration_s = max(--duration, activity_start_time_s + 7200)                  │
│                              ─────────────────────────────                   │
│                              ensure 2h minimum activity period               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Constants Reference

| Constant | Value | Purpose |
|----------|-------|---------|
| `USER_START_TIME_S` | 10800 (3h) | Default user spawn for non-batched |
| `DEFAULT_INITIAL_DELAY_S` | 1200 (20m) | Default user spawn for batched |
| `MIN_BOOTSTRAP_END_TIME_S` | 14400 (4h) | Minimum bootstrap period |
| `BOOTSTRAP_BUFFER_PERCENT` | 0.20 (20%) | Buffer after last user spawn |
| `FUNDING_PERIOD_S` | 3600 (1h) | Gap between md_start and activity_start |
| `MIN_ACTIVITY_PERIOD_S` | 7200 (2h) | Minimum simulation activity time |
| `DEFAULT_AUTO_THRESHOLD` | 50 | User count that triggers batched spawning |

## Visual Timeline

```
t=0                                                                    t=duration
│                                                                            │
├──────────┬─────────────┬──────────────┬─────────────┬──────────────────────┤
│          │             │              │             │                      │
│  Miners  │   Users     │  Bootstrap   │  MD starts  │  Users transact      │
│  start   │   spawn     │  ends        │  funding    │  (activity_start)    │
│          │             │              │             │                      │
▼          ▼             ▼              ▼             ▼                      │
0       user_spawn    last_spawn   bootstrap_end  md_start  activity_start   │
           start      + 20% buffer                                           │
```

## Example Scenarios

### Scenario A: All Defaults (100 users, batched)

```bash
python3 scripts/generate_config.py --agents 100 --duration 12h -o config.yaml
```

Timeline:
```
user_spawn_start    = 20m (default batched)
last_user_spawn     = ~2h (depends on batch schedule)
bootstrap_end       = max(4h, 2h * 1.2) = 4h
md_start            = 4h (= bootstrap_end)
activity_start      = 5h (= md_start + 1h)
```

### Scenario B: Large Scale with Delayed Spawning

```bash
python3 scripts/generate_config.py \
  --agents 1000 \
  --duration 36h \
  --user-spawn-start 14h \
  --bootstrap-end-time 20h \
  --md-start-time 18h \
  --regular-user-start 20h \
  -o config.yaml
```

Timeline:
```
user_spawn_start    = 14h (explicit)
last_user_spawn     = ~17h (batch schedule)
bootstrap_end       = 20h (explicit override)
md_start            = 18h (explicit, 2h BEFORE bootstrap ends)
activity_start      = 20h (explicit, same as bootstrap_end)
```

This configuration:
- Lets miners run alone for 14h (fast wall time, no user processes)
- Starts funding 2h early to give transactions time to confirm
- Removes the 1h funding gap so users transact immediately when bootstrap ends

## Scenario Parser (scenario.yaml) Format

The `scenario_parser.py` supports the same timing overrides via a `timing:` section:

```yaml
timing:
  user_spawn_start: 14h       # When users start spawning
  bootstrap_end_time: 20h     # When bootstrap ends
  md_start_time: 18h          # When miner distributor starts
  activity_start_time: 20h    # When users start transacting
```

All fields are optional. If omitted, they follow the same default/auto-calculation logic as `generate_config.py`.

## Key Concepts

### user_spawn_start vs activity_start

These are different timing concepts:

- **user_spawn_start**: When user *processes* start (daemon and wallet spawn)
  - Users need time to sync the blockchain before transacting
  - Spawning many users slows down wall time significantly

- **activity_start**: When users start *sending transactions*
  - Should be after users have synced and received funds
  - This is when the "steady state" simulation begins

### Why Allow md_start < bootstrap_end?

Setting `--md-start-time` before `--bootstrap-end-time` lets the miner distributor start funding users early. This gives funding transactions time to:
1. Be mined into blocks
2. Propagate through the network
3. Reach user wallets before they start transacting

This is useful for large simulations where funding 1000 users takes significant time.

### Batched vs Non-Batched Spawning

- **Batched** (≥50 users): Users spawn in exponentially growing batches
  - Default start: 20m after miners
  - Reduces initial load on the simulation

- **Non-batched** (<50 users): Users spawn linearly with stagger interval
  - Default start: 3h after miners
  - Simpler scheduling for small simulations

## Warnings

The config generator emits warnings for potentially problematic configurations:

1. **md_start < bootstrap_end**: "Miners may not have accumulated enough funds"
2. **activity_start < md_start**: "Users may start before receiving funds"

These are warnings, not errors. The configuration is still valid and may be intentional for specific testing scenarios.
