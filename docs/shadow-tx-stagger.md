# Transaction Activity Stagger in Shadow Simulations

## The Problem

When multiple user agents start transacting in a Shadow simulation, one user
can monopolize daemon CPU time and starve the others, causing a "winner take
all" pattern where only one user successfully sends transactions.

## Root Cause

Shadow is a discrete-event network simulator. All processes across all
simulated hosts share the same real CPU thread(s). Processes on the same
simulated host are always serialized — they take turns, switching only at
system call boundaries (e.g., `usleep`, `read`, `write`).

Each user agent runs two processes on the same host:

- **monerod** (daemon) — handles P2P networking, block/tx verification
- **monero-wallet-rpc** — constructs transactions (heavy crypto: Bulletproofs+, CLSAG)

When user-001 broadcasts a transaction, it propagates to all other daemons.
Each daemon must verify the transaction (Bulletproofs+ verification, CLSAG
ring signature verification), which is CPU-intensive (~650ms per tx). While a
daemon is verifying, the wallet-rpc on the same host cannot run.

With a large activity start time gap (e.g., 2 minutes between users):

1. user-001 starts first and sends transactions unopposed
2. Those transactions propagate to user-002's daemon for verification
3. user-002's daemon is busy verifying user-001's backlog when user-002's
   wallet tries to construct its own transaction
4. user-002's wallet-rpc can't get CPU time, the Python agent times out (180s)
5. user-001 keeps sending more transactions, deepening the starvation

This creates a positive feedback loop: the first user to transact generates
verification work that prevents other users from ever catching up.

## The Fix

Stagger `activity_start_time` values so that transaction generation is evenly
distributed across simulated time:

```
stagger = transaction_interval / num_users
```

For example, with `transaction_interval: 60` and 3 users:

```
stagger = 60 / 3 = 20 seconds

user-001: activity_start_time = 32400  (09:00:00)
user-002: activity_start_time = 32420  (09:00:20)
user-003: activity_start_time = 32440  (09:00:40)
```

This produces an even cadence of one transaction every 20 seconds across the
network, preventing any single daemon from being overwhelmed.

## Calibration

The minimum safe `transaction_interval` depends on how fast your hardware
can run tx verification under Shadow. Run calibration to measure this:

```bash
python scripts/calibrate.py              # Run calibration sim (~5 min)
python scripts/calibrate.py --show       # Show current calibration data
```

This measures the PERF `add_tx` time from daemon logs and saves results to
`~/.monerosim/calibration.json`. The config generators (`generate_config.py`,
`scenario_parser.py`) automatically use this data when computing stagger values.

You can also extract calibration from any existing run:

```bash
python scripts/calibrate.py --from-run archived_runs/20260406_103204_quickstart3
```

### The Formula

```
min_interval = num_users * verify_time_p95 * safety_factor
stagger = interval / num_users
```

Where:
- `verify_time_p95` — 95th percentile tx verification time (from calibration)
- `safety_factor` — default 3x (accounts for multi-input txs and variance)
- `interval` — the larger of `transaction_interval` and `min_interval`

### Without Calibration

If no calibration data exists, the stagger defaults to `transaction_interval / num_users`.
This is safe for most configurations. Calibration is mainly useful when pushing
high user counts or low transaction intervals.

## Important Notes

- This is a **Shadow simulation artifact**, not a real Monero issue. On real
  hardware, each node has its own CPU and daemon verification doesn't starve
  the wallet.
- No Monero source code modifications are needed. The fix is purely in
  simulation configuration.
- The `simulation_seed` makes Shadow deterministic — same config always
  produces the same result, making it easy to verify fixes.
