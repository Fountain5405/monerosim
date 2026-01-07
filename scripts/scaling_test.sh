#!/bin/bash
#
# Scaling test script for monerosim
# Tests increasing agent counts to find the limit on current hardware
#
# Usage: ./scripts/scaling_test.sh
#

set -e

# Configuration
TIMEOUT=3600  # 1 hour - script detects early completion via "Finished simulation" in logs
RESULTS="scaling_results.txt"
AGENT_COUNTS=(50 100 200 400 800 1000)
MONEROSIM_BIN="./target/release/monerosim"
SHADOW_BIN="$HOME/.monerosim/bin/shadow"
TEMP_DIR="/tmp/monerosim_scaling_test"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure we're in the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    if [[ ! -x "$MONEROSIM_BIN" ]]; then
        echo -e "${RED}Error: monerosim binary not found at $MONEROSIM_BIN${NC}"
        echo "Run: cargo build --release"
        exit 1
    fi

    if [[ ! -x "$SHADOW_BIN" ]]; then
        echo -e "${RED}Error: shadow binary not found at $SHADOW_BIN${NC}"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 not found${NC}"
        exit 1
    fi

    if ! command -v /usr/bin/time &> /dev/null; then
        echo -e "${RED}Error: /usr/bin/time not found (needed for memory stats)${NC}"
        exit 1
    fi

    echo -e "${GREEN}All prerequisites met${NC}"
}

# Get system info
get_system_info() {
    local mem_total=$(free -h | grep Mem | awk '{print $2}')
    local cpu_count=$(nproc)
    echo "# Scaling Test Results - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "# Hardware: ${mem_total} RAM, ${cpu_count} CPUs"
    echo "# Timeout: ${TIMEOUT}s ($((TIMEOUT / 60)) minutes)"
    echo "# Config: 5 fixed miners + variable users, 6h sim duration, 5s stagger"
    echo ""
}

# Run a single test
run_test() {
    local agent_count=$1
    local user_count=$((agent_count - 5))
    local config_file="$TEMP_DIR/config_${agent_count}.yaml"
    local shadow_dir="$TEMP_DIR/shadow_${agent_count}"
    local log_file="$TEMP_DIR/run_${agent_count}.log"
    local time_file="$TEMP_DIR/time_${agent_count}.txt"

    echo -e "${YELLOW}Testing $agent_count agents (5 miners + $user_count users)...${NC}"

    # Generate monerosim config (6h duration, 5s stagger)
    echo "  Generating config..."
    python3 scripts/generate_config.py --agents "$agent_count" -o "$config_file" || {
        echo "  FAIL: Config generation failed"
        echo "$agent_count | $user_count | FAIL | - | - | Config generation failed"
        return 1
    }

    # Generate shadow config
    echo "  Generating shadow config..."
    rm -rf "$shadow_dir"
    mkdir -p "$shadow_dir"
    # Clean monerosim shared state from previous runs
    rm -rf /tmp/monerosim_shared
    if ! "$MONEROSIM_BIN" --config "$config_file" --output "$shadow_dir" 2>&1 | tee "$TEMP_DIR/monerosim_${agent_count}.log" | tail -5; then
        echo "  FAIL: Shadow config generation failed"
        echo "$agent_count | $user_count | FAIL | - | - | Shadow config generation failed"
        return 1
    fi

    # Verify shadow config was created
    if [[ ! -f "$shadow_dir/shadow_agents.yaml" ]]; then
        echo "  FAIL: shadow_agents.yaml not created"
        echo "$agent_count | $user_count | FAIL | - | - | shadow_agents.yaml not created"
        return 1
    fi

    # Clean previous shadow run artifacts (matching run_sim.sh)
    rm -rf shadow.data/
    rm -rf shadow.log

    # Run shadow with timeout and capture stats
    echo "  Running shadow (timeout: ${TIMEOUT}s)..."
    local start_time=$(date +%s)

    # Run with /usr/bin/time to capture memory stats
    /usr/bin/time -v timeout "$TIMEOUT" "$SHADOW_BIN" "$shadow_dir/shadow_agents.yaml" \
        > "$log_file" 2>&1
    local exit_code=$?

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local duration_fmt=$(printf "%d:%02d" $((duration / 60)) $((duration % 60)))

    # Extract memory from time output (in KB, convert to readable)
    # Use -a to treat binary files as text (shadow logs may contain binary data)
    local mem_kb=$(grep -a "Maximum resident set size" "$log_file" | awk '{print $NF}')
    local mem_readable=""
    if [[ -n "$mem_kb" ]]; then
        local mem_mb=$((mem_kb / 1024))
        if [[ $mem_mb -gt 1024 ]]; then
            mem_readable="$(echo "scale=1; $mem_mb / 1024" | bc)GB"
        else
            mem_readable="${mem_mb}MB"
        fi
    else
        mem_readable="N/A"
    fi

    # Determine result
    # Note: Shadow returns exit code 1 when processes are still running at simulation end
    # This is expected for long-running daemons, so we check if simulation completed
    local status=""
    local notes=""

    # Check if simulation completed (look for "Finished simulation" in log)
    local sim_finished=$(grep -a "Finished simulation" "$log_file" 2>/dev/null)

    if [[ $exit_code -eq 0 ]]; then
        status="SUCCESS"
        echo -e "  ${GREEN}SUCCESS${NC} - Completed in $duration_fmt, peak RAM: $mem_readable"
    elif [[ $exit_code -eq 124 ]]; then
        status="TIMEOUT"
        notes="Exceeded ${TIMEOUT}s timeout"
        echo -e "  ${YELLOW}TIMEOUT${NC} - Exceeded timeout after $duration_fmt"
    elif [[ $exit_code -eq 137 ]]; then
        status="OOM"
        notes="Killed by OOM killer (SIGKILL)"
        echo -e "  ${RED}OOM${NC} - Killed after $duration_fmt, peak RAM: $mem_readable"
    elif [[ -n "$sim_finished" ]]; then
        # Shadow completed but exited with error due to process states
        status="SUCCESS"
        notes="Sim completed (processes still running at end)"
        echo -e "  ${GREEN}SUCCESS${NC} - Completed in $duration_fmt, peak RAM: $mem_readable"
    else
        status="FAIL"
        notes="Exit code: $exit_code"
        echo -e "  ${RED}FAIL${NC} - Exit code $exit_code after $duration_fmt"
    fi

    # Output result line
    printf "%-7s | %-6s | %-7s | %-8s | %-8s | %s\n" \
        "$agent_count" "$user_count" "$status" "$mem_readable" "$duration_fmt" "$notes"

    # Return non-zero only if actually failed (not just Shadow's process-still-running exit)
    [[ "$status" == "SUCCESS" ]]
}

# Main
main() {
    check_prerequisites

    # Create temp directory
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"

    # Write results header
    get_system_info > "$RESULTS"
    echo "Agents  | Users  | Status  | Peak RAM | Duration | Notes" >> "$RESULTS"
    echo "--------|--------|---------|----------|----------|------" >> "$RESULTS"

    # Also print header to console
    echo ""
    get_system_info
    echo "Agents  | Users  | Status  | Peak RAM | Duration | Notes"
    echo "--------|--------|---------|----------|----------|------"

    local failed=0

    for count in "${AGENT_COUNTS[@]}"; do
        result=$(run_test "$count")
        echo "$result" >> "$RESULTS"

        # Check if we should stop (consecutive failures might indicate we hit the limit)
        if [[ "$result" == *"OOM"* ]] || [[ "$result" == *"TIMEOUT"* ]]; then
            ((failed++))
            if [[ $failed -ge 2 ]]; then
                echo ""
                echo -e "${YELLOW}Stopping after 2 consecutive failures${NC}"
                break
            fi
        else
            failed=0
        fi
    done

    echo ""
    echo "Results saved to: $RESULTS"
    echo ""
    cat "$RESULTS"

    # Cleanup
    echo ""
    echo "Temporary files in: $TEMP_DIR"
}

main "$@"
