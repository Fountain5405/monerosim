#!/bin/bash

# network_config.sh - Central configuration file for MoneroSim network settings
# This file defines all IP addresses and ports used across the MoneroSim scripts

# Daemon Nodes
A0_IP="11.0.0.1"          # Mining node IP
A0_RPC_PORT="28090"       # Mining node RPC port
A0_RPC="http://${A0_IP}:${A0_RPC_PORT}/json_rpc"

A1_IP="11.0.0.2"          # Sync node IP
A1_RPC_PORT="28090"       # Sync node RPC port
A1_RPC="http://${A1_IP}:${A1_RPC_PORT}/json_rpc"

# Wallet Nodes - Updated to match current shadow.yaml configuration
WALLET1_IP="11.0.0.3"     # Mining wallet IP
WALLET1_RPC_PORT="28091"  # Mining wallet RPC port
WALLET1_RPC="http://${WALLET1_IP}:${WALLET1_RPC_PORT}/json_rpc"

WALLET2_IP="11.0.0.4"     # Recipient wallet IP
WALLET2_RPC_PORT="28092"  # Recipient wallet RPC port
WALLET2_RPC="http://${WALLET2_IP}:${WALLET2_RPC_PORT}/json_rpc"

# For backward compatibility with scripts using different variable names
DAEMON_IP="${A0_IP}"
DAEMON_RPC_PORT="${A0_RPC_PORT}"

# Common wallet credentials (used in multiple scripts)
WALLET1_NAME="mining_wallet"
WALLET1_PASSWORD="test123"
WALLET2_NAME="recipient_wallet"
WALLET2_PASSWORD="test456"

# Export all variables to make them available to sourced scripts
export A0_IP A0_RPC_PORT A0_RPC
export A1_IP A1_RPC_PORT A1_RPC
export WALLET1_IP WALLET1_RPC_PORT WALLET1_RPC
export WALLET2_IP WALLET2_RPC_PORT WALLET2_RPC
export DAEMON_IP DAEMON_RPC_PORT
export WALLET1_NAME WALLET1_PASSWORD WALLET2_NAME WALLET2_PASSWORD

# Fallback addresses for error recovery (used if wallet RPC fails to provide addresses)
# These are standard testnet addresses that can be used for mining
WALLET1_ADDRESS_FALLBACK="9tUBnwk5FUXVSKnVbXBjQESkLyS5eWjPHzq2KgQEz3Zcbc1G1oUBHx8Qpc9JnQMNDVQiUBNNopa5qKWuHEJQUW9b2xr2X3K"
WALLET2_ADDRESS_FALLBACK="9tUBnwk5FUXVSKnVbXBjQESkLyS5eWjPHzq2KgQEz3Zcbc1G1oUBHx8Qpc9JnQMNDVQiUBNNopa5qKWuHEJQUW9b2xr2X3K"
export WALLET1_ADDRESS_FALLBACK WALLET2_ADDRESS_FALLBACK