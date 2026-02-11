#!/bin/bash
#
# Archive a completed monerosim simulation
#
# Usage: ./scripts/archive_simulation.sh [archive_name] [--keep-wallets]
#
# This script archives:
# - shadow.data/ (simulation logs)
# - /tmp/monerosim_shared/ (shared state including transactions.json)
# - shadow_output/ (generated configs)
# - Input config file
#
# Output is stored in ~/scale_run_logs/

set -e

# Shared directory (single source of truth)
SHARED_DIR="/tmp/monerosim_shared"

# Parse arguments
ARCHIVE_NAME=""
KEEP_WALLETS=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-wallets)
            KEEP_WALLETS=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [archive_name] [--keep-wallets]"
            echo ""
            echo "Archives a completed monerosim simulation to ~/scale_run_logs/"
            echo ""
            echo "Options:"
            echo "  archive_name     Custom name for archive (default: timestamp_config)"
            echo "  --keep-wallets   Include wallet directories in archive (large!)"
            echo ""
            echo "Archived data:"
            echo "  - shadow.data/            Simulation logs"
            echo "  - /tmp/monerosim_shared/  Shared state (agent_registry, transactions, etc.)"
            echo "  - shadow_output/          Generated Shadow configs"
            echo "  - Input config file"
            exit 0
            ;;
        *)
            ARCHIVE_NAME="$1"
            shift
            ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Ensure we're in project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check for required directories
if [[ ! -d "shadow.data" ]]; then
    echo -e "${RED}Error: shadow.data/ not found. Run a simulation first.${NC}"
    exit 1
fi

if [[ ! -d "${SHARED_DIR}" ]]; then
    echo -e "${RED}Error: ${SHARED_DIR}/ not found.${NC}"
    exit 1
fi

# Create archive name from timestamp if not provided
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
if [[ -z "$ARCHIVE_NAME" ]]; then
    # Try to find the config file used
    if [[ -f "shadow_output/shadow_agents.yaml" ]]; then
        # Extract config name from comments if possible
        CONFIG_NAME=$(grep -m1 "^# Generated from:" shadow_output/shadow_agents.yaml 2>/dev/null | sed 's/.*: //' | xargs basename 2>/dev/null | sed 's/\.yaml$//' || echo "sim")
    else
        CONFIG_NAME="sim"
    fi
    ARCHIVE_NAME="${TIMESTAMP}_${CONFIG_NAME}"
fi

# Archive directory
ARCHIVE_BASE="$HOME/scale_run_logs"
ARCHIVE_DIR="$ARCHIVE_BASE/$ARCHIVE_NAME"

if [[ -d "$ARCHIVE_DIR" ]]; then
    echo -e "${YELLOW}Warning: Archive directory exists: $ARCHIVE_DIR${NC}"
    read -p "Overwrite? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
    rm -rf "$ARCHIVE_DIR"
fi

mkdir -p "$ARCHIVE_DIR"

echo -e "${YELLOW}Archiving simulation to: $ARCHIVE_DIR${NC}"
echo ""

# Archive shadow.data
echo "Copying shadow.data/ ..."
cp -r shadow.data "$ARCHIVE_DIR/"

# Archive shared state from /tmp
echo "Copying ${SHARED_DIR}/ ..."
mkdir -p "$ARCHIVE_DIR/shared_data"

# Copy essential files
for file in agent_registry.json transactions.json blocks_with_transactions.json \
            initial_funding_status.json miners.json; do
    if [[ -f "${SHARED_DIR}/$file" ]]; then
        cp "${SHARED_DIR}/$file" "$ARCHIVE_DIR/shared_data/"
        echo "  - $file"
    fi
done

# Copy monitoring data
if [[ -d "${SHARED_DIR}/monitoring" ]]; then
    cp -r "${SHARED_DIR}/monitoring" "$ARCHIVE_DIR/shared_data/"
    echo "  - monitoring/"
fi

# Copy miner info files
for f in "${SHARED_DIR}"/miner-*_miner_info.json; do
    if [[ -f "$f" ]]; then
        cp "$f" "$ARCHIVE_DIR/shared_data/"
    fi
done

# Copy distributor info
if [[ -f "${SHARED_DIR}/miner-distributor_distributor_info.json" ]]; then
    cp "${SHARED_DIR}/miner-distributor_distributor_info.json" "$ARCHIVE_DIR/shared_data/"
fi

# Optionally copy wallets (can be large)
if [[ "$KEEP_WALLETS" == "true" ]]; then
    echo "Copying wallet directories..."
    mkdir -p "$ARCHIVE_DIR/shared_data/wallets"
    for wallet in "${SHARED_DIR}"/*_wallet; do
        if [[ -d "$wallet" ]]; then
            cp -r "$wallet" "$ARCHIVE_DIR/shared_data/wallets/"
        fi
    done
fi

# Copy shadow output configs
if [[ -d "shadow_output" ]]; then
    echo "Copying shadow_output/ ..."
    cp -r shadow_output "$ARCHIVE_DIR/"
fi

# Copy input config if identifiable
if [[ -f "shadow_output/shadow_agents.yaml" ]]; then
    CONFIG_FILE=$(grep -m1 "^# Generated from:" shadow_output/shadow_agents.yaml 2>/dev/null | sed 's/.*: //' || echo "")
    if [[ -n "$CONFIG_FILE" && -f "$CONFIG_FILE" ]]; then
        cp "$CONFIG_FILE" "$ARCHIVE_DIR/input_config.yaml"
        echo "Copied input config: $CONFIG_FILE"
    fi
fi

# Copy memory samples if present
if [[ -f "memory_samples.csv" ]]; then
    cp memory_samples.csv "$ARCHIVE_DIR/"
fi

# Copy shadow log
if [[ -f "shadow.log" ]]; then
    cp shadow.log "$ARCHIVE_DIR/shadow_run.log"
fi

# Generate README
echo "Generating README.md ..."
AGENT_COUNT=$(jq '.agents | length' "$ARCHIVE_DIR/shared_data/agent_registry.json" 2>/dev/null || echo "unknown")
MINER_COUNT=$(jq '[.agents[] | select(.role == "Miner")] | length' "$ARCHIVE_DIR/shared_data/agent_registry.json" 2>/dev/null || echo "unknown")
USER_COUNT=$(jq '[.agents[] | select(.role == "User")] | length' "$ARCHIVE_DIR/shared_data/agent_registry.json" 2>/dev/null || echo "unknown")
TX_COUNT=$(jq 'length' "$ARCHIVE_DIR/shared_data/transactions.json" 2>/dev/null || echo "0")
BLOCK_COUNT=$(jq 'length' "$ARCHIVE_DIR/shared_data/blocks_with_transactions.json" 2>/dev/null || echo "0")

cat > "$ARCHIVE_DIR/README.md" << EOF
# Monerosim Simulation Archive

**Date:** $(date '+%Y-%m-%d %H:%M')
**Archive:** $ARCHIVE_NAME

## Summary

| Metric | Value |
|--------|-------|
| Total Agents | $AGENT_COUNT |
| Miners | $MINER_COUNT |
| Users | $USER_COUNT |
| Transactions | $TX_COUNT |
| Blocks | $BLOCK_COUNT |

## Contents

- \`shadow.data/\` - Shadow simulation logs and outputs
- \`shared_data/\` - Monerosim shared state:
  - \`agent_registry.json\` - All registered agents with IPs and roles
  - \`transactions.json\` - Transaction records with sender info
  - \`blocks_with_transactions.json\` - Block/TX mapping
  - \`initial_funding_status.json\` - Funding results
  - \`miners.json\` - Miner configuration
  - \`monitoring/\` - Periodic monitoring snapshots
- \`shadow_output/\` - Generated Shadow configuration
- \`input_config.yaml\` - Original monerosim config

## Running Analysis

\`\`\`bash
cd /path/to/monerosim
./target/release/tx-analyzer \\
    -d "$ARCHIVE_DIR/shadow.data" \\
    -s "$ARCHIVE_DIR/shared_data" \\
    -o "$ARCHIVE_DIR/analysis_output" \\
    full
\`\`\`
EOF

# Calculate archive size
ARCHIVE_SIZE=$(du -sh "$ARCHIVE_DIR" | cut -f1)
SHADOW_SIZE=$(du -sh "$ARCHIVE_DIR/shadow.data" | cut -f1)

echo ""
echo -e "${GREEN}Archive complete!${NC}"
echo ""
echo "Location: $ARCHIVE_DIR"
echo "Total size: $ARCHIVE_SIZE (shadow.data: $SHADOW_SIZE)"
echo ""
echo "Contents:"
ls -la "$ARCHIVE_DIR"
echo ""
echo "To run analysis:"
echo "  ./target/release/tx-analyzer -d \"$ARCHIVE_DIR/shadow.data\" -s \"$ARCHIVE_DIR/shared_data\" -o \"$ARCHIVE_DIR/analysis_output\" full"
