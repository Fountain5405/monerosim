#!/bin/bash
# Miner initialization script for Monerosim
# Retrieves wallet address and starts mining
# 
# This script is part of the decentralized mining initialization system
# that replaces the centralized block controller approach.
#
# Usage: miner_init.sh AGENT_ID AGENT_IP WALLET_PORT DAEMON_PORT MINER_ADDRESS_VAR

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Script parameters
AGENT_ID="${1:-agent}"
AGENT_IP="${2:-127.0.0.1}"
WALLET_PORT="${3:-28082}"
DAEMON_PORT="${4:-28080}"
MINER_ADDRESS_VAR="${5:-MINER_WALLET_ADDRESS}"

# Logging configuration
LOG_DIR="/tmp/monerosim_shared"
LOG_FILE="${LOG_DIR}/${AGENT_ID}_miner_init.log"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

# Error handling function
error_exit() {
    log "ERROR: $*"
    exit 1
}

# Validate required parameters
if [[ $# -lt 5 ]]; then
    error_exit "Usage: $0 AGENT_ID AGENT_IP WALLET_PORT DAEMON_PORT MINER_ADDRESS_VAR"
fi

log "Starting miner initialization for agent ${AGENT_ID}"
log "Parameters: IP=${AGENT_IP}, Wallet Port=${WALLET_PORT}, Daemon Port=${DAEMON_PORT}"

# Function to check if wallet RPC is available
check_wallet_rpc() {
    local wallet_url="http://${AGENT_IP}:${WALLET_PORT}/json_rpc"
    local response
    
    log "Testing wallet RPC at: ${wallet_url}"
    
    # Try multiple curl approaches
    if command -v curl >/dev/null 2>&1; then
        log "Using curl for wallet RPC check"
        response=$(curl -s --connect-timeout 5 --max-time 10 "${wallet_url}" 2>/dev/null || echo "")
    else
        log "curl not found, trying wget"
        response=$(wget -q --timeout=10 -O - "${wallet_url}" 2>/dev/null || echo "")
    fi
    
    log "Wallet RPC response length: ${#response}"
    [[ -n "${response}" ]] && return 0 || return 1
}

# Function to make RPC call with retry logic
make_rpc_call() {
    local method="$1"
    local params="$2"
    local wallet_url="http://${AGENT_IP}:${WALLET_PORT}/json_rpc"
    local max_attempts=3
    local attempt=1

    while [[ ${attempt} -le ${max_attempts} ]]; do
        log "RPC attempt ${attempt}/${max_attempts}: ${method}"

        local response
        response=$(/usr/bin/curl -s --connect-timeout 10 --max-time 30 \
            -X POST "${wallet_url}" \
            -H 'Content-Type: application/json' \
            -d "{\"jsonrpc\":\"2.0\",\"id\":\"${AGENT_ID}\",\"method\":\"${method}\",\"params\":${params}}" \
            2>/dev/null || echo "")

        if [[ -n "${response}" ]]; then
            # Check for RPC error using grep instead of jq
            if echo "${response}" | grep -q '"error"'; then
                local error
                error=$(echo "${response}" | grep -o '"error"[^}]*' | head -1)
                if [[ -n "${error}" ]]; then
                    log "RPC error: ${error}"
                    if [[ ${attempt} -eq ${max_attempts} ]]; then
                        error_exit "RPC call failed after ${max_attempts} attempts: ${error}"
                    fi
                fi
            else
                echo "${response}"
                return 0
            fi
        else
            log "Empty response from RPC call"
        fi

        ((attempt++))
        sleep 2
    done

    error_exit "RPC call failed after ${max_attempts} attempts"
}

# Function to ensure wallet exists (create if needed)
ensure_wallet() {
    local wallet_name="${AGENT_ID}_wallet"
    log "Ensuring wallet exists: ${wallet_name}"
    
    # First try to open the wallet
    local params="{\"filename\":\"${wallet_name}\",\"password\":\"\"}"
    local response
    
    log "Attempting to open wallet '${wallet_name}'..."
    response=$(make_rpc_call "open_wallet" "${params}")
    
    # Check if wallet was opened successfully
    local result
    result=$(echo "${response}" | jq -r '.result // empty' 2>/dev/null || echo "")
    if [[ -n "${result}" ]]; then
        log "Wallet opened successfully"
        return 0
    fi
    
    # If opening failed, try to create the wallet
    log "Wallet not found, attempting to create it..."
    params="{\"filename\":\"${wallet_name}\",\"password\":\"\",\"language\":\"English\"}"
    response=$(make_rpc_call "create_wallet" "${params}")
    
    # Check if wallet was created successfully
    result=$(echo "${response}" | jq -r '.result // empty' 2>/dev/null || echo "")
    if [[ -n "${result}" ]]; then
        log "Wallet created successfully"
        return 0
    else
        error_exit "Failed to create wallet: ${response}"
    fi
}

# Function to get wallet address with retries
get_wallet_address() {
    log "Retrieving wallet address"
    local max_retries=10
    local retry_delay=5
    local attempt=1
    
    while [[ ${attempt} -le ${max_retries} ]]; do
        local params="{\"account_index\":0,\"address_index\":[0]}"
        local response
        response=$(make_rpc_call "get_address" "${params}")

        # Extract address from response
        local address
        address=$(echo "${response}" | jq -r '.result.addresses[0].address // empty' 2>/dev/null || echo "")
        
        # Fallback to grep if jq fails
        if [[ -z "${address}" ]]; then
            address=$(echo "${response}" | grep -o '"address":"[^"]*"' | head -1 | cut -d'"' -f4 2>/dev/null || echo "")
        fi

        if [[ -n "${address}" && "${address}" != "null" ]]; then
            log "Retrieved wallet address: ${address}"
            echo "${address}"
            return 0
        else
            log "Failed to retrieve wallet address (attempt ${attempt}/${max_retries}): ${response}"
            if [[ ${attempt} -lt ${max_retries} ]]; then
                log "Retrying in ${retry_delay} seconds..."
                sleep ${retry_delay}
                
                # Try to reopen the wallet if it's not loaded
                local wallet_name="${AGENT_ID}_wallet"
                log "Attempting to reopen wallet '${wallet_name}'..."
                local reopen_params="{\"filename\":\"${wallet_name}\",\"password\":\"\"}"
                make_rpc_call "open_wallet" "${reopen_params}" >/dev/null 2>&1 || true
            fi
        fi
        
        ((attempt++))
    done
    
    error_exit "Failed to retrieve wallet address after ${max_retries} attempts"
}

# Function to launch monerod with mining
launch_monerod() {
    local address="$1"
    log "Launching monerod with mining shim and address: ${address}"
    
    # Verify mining shim library exists
    if [[ ! -f "${LD_PRELOAD}" ]]; then
        error_exit "Mining shim library not found at: ${LD_PRELOAD}"
    fi
    
    log "Mining shim library verified: ${LD_PRELOAD}"
    log "Mining environment variables:"
    log "  LD_PRELOAD=${LD_PRELOAD}"
    log "  MINER_HASHRATE=${MINER_HASHRATE}"
    log "  AGENT_ID=${AGENT_ID}"
    log "  SIMULATION_SEED=${SIMULATION_SEED}"
    log "  MINING_ADDRESS=${address}"
    
    # Build monerod command with mining enabled
    local monerod_cmd="/usr/local/bin/monerod"
    local monerod_args=(
        "--rpc-bind-ip=${AGENT_IP}"
        "--rpc-bind-port=${DAEMON_PORT}"
        "--confirm-external-bind"
        "--log-level=1"
        "--data-dir=/tmp/monerosim_shared/${AGENT_ID}_data"
        "--simulation"
        "--start-mining=${address}"
        "--mining-threads=1"
    )
    
    log "Launching monerod: ${monerod_cmd} ${monerod_args[*]}"
    
    # Export mining address for mining shim
    export MINING_ADDRESS="${address}"
    
    # Launch monerod with mining shim preloaded (LD_PRELOAD already set in environment)
    exec "${monerod_cmd}" "${monerod_args[@]}"
}

# Main execution flow
main() {
    log "=== Miner Initialization Started ==="
    
    # Wait for wallet RPC to become available (max 120s, 5s intervals)
    log "Waiting for wallet RPC to become available..."
    local max_attempts=24
    local attempt=1
    local wallet_available=false
    
    while [[ ${attempt} -le ${max_attempts} ]]; do
        log "Checking wallet RPC availability (attempt ${attempt}/${max_attempts})"
        
        if check_wallet_rpc; then
            log "Wallet RPC is available"
            wallet_available=true
            break
        fi
        
        if [[ ${attempt} -eq ${max_attempts} ]]; then
            error_exit "Wallet RPC not available after ${max_attempts} attempts (120 seconds)"
        fi
        
        ((attempt++))
        sleep 5
    done
    
    if [[ "${wallet_available}" != true ]]; then
        error_exit "Failed to connect to wallet RPC"
    fi
    
    # Ensure wallet exists (create if needed)
    ensure_wallet
    
    # Get wallet address
    local address
    address=$(get_wallet_address)
    
    # Launch monerod with mining
    launch_monerod "${address}"
}

# Check if required tools are available
check_dependencies() {
    local missing_deps=()
    
    command -v curl >/dev/null 2>&1 || missing_deps+=("curl")
    command -v jq >/dev/null 2>&1 || missing_deps+=("jq")
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        error_exit "Missing required dependencies: ${missing_deps[*]}"
    fi
}

# Run dependency check
check_dependencies

# Execute main function
main "$@"