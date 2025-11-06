#!/bin/bash
# Ultra-simplified miner initialization script for Monerosim
# Just launches monerod with mining shim - no external dependencies
#
# Usage: miner_init.sh AGENT_ID AGENT_IP WALLET_PORT DAEMON_PORT MINER_ADDRESS_VAR

set -euo pipefail

# Script parameters
AGENT_ID="${1:-agent}"
AGENT_IP="${2:-127.0.0.1}"
WALLET_PORT="${3:-28082}"
DAEMON_PORT="${4:-28080}"
MINER_ADDRESS_VAR="${5:-MINER_WALLET_ADDRESS}"

# Logging
LOG_DIR="/tmp/monerosim_shared"
LOG_FILE="${LOG_DIR}/${AGENT_ID}_miner_init.log"
mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

error_exit() {
    log "ERROR: $*"
    exit 1
}

#!/bin/bash
# Ultra-simplified miner initialization script for Monerosim
# Just sets up environment variables for mining shim - no external dependencies
#
# Usage: miner_init.sh AGENT_ID AGENT_IP WALLET_PORT DAEMON_PORT MINER_ADDRESS_VAR

set -euo pipefail

# Script parameters
AGENT_ID="${1:-agent}"
AGENT_IP="${2:-127.0.0.1}"
WALLET_PORT="${3:-28082}"
DAEMON_PORT="${4:-28080}"
MINER_ADDRESS_VAR="${5:-MINER_WALLET_ADDRESS}"

# Logging
LOG_DIR="/tmp/monerosim_shared"
LOG_FILE="${LOG_DIR}/${AGENT_ID}_miner_init.log"
mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

error_exit() {
    log "ERROR: $*"
    exit 1
}

log "Starting ultra-simplified miner initialization for ${AGENT_ID}"

# Check mining shim exists
SHIM_PATH="/home/lever65/monerosim_dev/monerosim/./mining_shim/libminingshim.so"
if [[ ! -f "${SHIM_PATH}" ]]; then
    error_exit "Mining shim not found: ${SHIM_PATH}"
fi

# Set environment variables for mining shim
export LD_PRELOAD="${SHIM_PATH}"
export MINER_HASHRATE="${MINER_HASHRATE:-100}"
export AGENT_ID="${AGENT_ID}"
export SIMULATION_SEED="${SIMULATION_SEED:-42}"
export MININGSHIM_LOG_LEVEL="${MININGSHIM_LOG_LEVEL:-info}"

# Use a hardcoded mining address for simulation
MINING_ADDRESS="44AFFq5kSiGBoZ4NMDwYtN18obc8AemS33DBLWs3H7otXft3XjrpDtQGv7SqSsaBYBb98uNbr2VBBEt7f2wfn3RVGQBEP3A"
export MINING_ADDRESS="${MINING_ADDRESS}"

log "Environment set up:"
log "  LD_PRELOAD=${LD_PRELOAD}"
log "  MINER_HASHRATE=${MINER_HASHRATE}"
log "  AGENT_ID=${AGENT_ID}"
log "  MINING_ADDRESS=${MINING_ADDRESS}"

log "Miner initialization complete - monerod will be launched separately by Shadow"

# Exit cleanly - Shadow will launch monerod with mining shim preloaded
exit 0