"""Shared timing constants for config generation.

Single source of truth for values previously duplicated across
generate_config.py and scenario_parser.py (and imported by
configure_upgrade.py). All values are in seconds unless noted.
"""

# Bootstrap timing (verified for Monero regtest with ring size 16).
# Ensures sufficient blocks for coinbase unlock (60 blocks) and outputs
# for ring signatures. At ~2 min/block, 4h gives ~120 blocks.
MIN_BOOTSTRAP_END_TIME_S = 14400  # 4h

# Buffer added after last user spawn to absorb hardware variance.
BOOTSTRAP_BUFFER_PERCENT = 0.20

# Time after bootstrap ends for miner-distributor to fund users
# before activity starts.
FUNDING_PERIOD_S = 3600  # 1h


# Batched bootstrap defaults
DEFAULT_AUTO_THRESHOLD = 50              # enable batching when > N users
DEFAULT_INITIAL_DELAY_S = 1200           # 20m after miners
DEFAULT_BATCH_INTERVAL_S = 1200          # 20m between batches
DEFAULT_INITIAL_BATCH_SIZE = 5
DEFAULT_GROWTH_FACTOR = 2.0
DEFAULT_MAX_BATCH_SIZE = 200
DEFAULT_INTRA_BATCH_STAGGER_S = 5        # 5s between users in same batch


# Upgrade scenario defaults
DEFAULT_UPGRADE_STAGGER_S = 30           # 30s between node upgrades

# Within-node gap between an old binary's stop time and the next phase's
# start. Defaulted to 5 min: monero-wallet-rpc occasionally hangs in a
# CPU-bound section (ring signature construction during a transfer)
# under cooperative Shadow scheduling, and a tight gap risks the v1
# wallet still holding port 18082 when v2 tries to bind. 5 min gives
# Shadow enough wall time to deliver SIGTERM, then SIGKILL if needed,
# before the next phase fires. (See run 20260501_165857_upgrade_smoke
# for an instance of the hang.)
DEFAULT_DAEMON_RESTART_GAP_S = 300
DEFAULT_WALLET_RESTART_GAP_S = 300


# Threshold (total agent count) above which config generators auto-enable
# `native_preemption: true` in the Shadow general section. Without it,
# Shadow uses cooperative scheduling, which can deadlock when a single
# monerod process enters a busy CPU section (notably LMDB blockchain
# resize). See run 20260504_104925_large_upgrade_short for the failure
# this guards against: one v2 daemon hit "DB resize needed", entered a
# futex spin, and froze the entire 1011-node sim because Shadow couldn't
# advance simulation time while waiting for it to yield.
LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD = 100
