#!/bin/bash
#
# Scaling test script for monerosim
# Tests increasing agent counts to find the limit on current hardware
#
# Usage: ./scripts/scaling_test.sh [--fast] [--agents N] [--duration D] [--timeout T]
#

set -e

# Parse arguments
FAST_MODE=""
CUSTOM_AGENTS=""
SIM_DURATION="6h"
TIMEOUT=""
THREADS=""
STAGGER=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            FAST_MODE="--fast"
            shift
            ;;
        --agents)
            CUSTOM_AGENTS="$2"
            shift 2
            ;;
        --duration)
            SIM_DURATION="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --threads)
            THREADS="$2"
            shift 2
            ;;
        --stagger)
            STAGGER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--fast] [--agents N] [--duration D] [--timeout T] [--threads T] [--stagger S]"
            echo "  --fast       Enable performance optimizations"
            echo "  --agents N   Test only N agents (can be comma-separated: 100,200,400)"
            echo "  --duration D Simulation duration (default: 6h, e.g., 2h, 30m, 1h30m)"
            echo "  --timeout T  Test timeout (default: 2x sim duration, e.g., 4h, 90m)"
            echo "  --threads T  Thread count for monerod/wallet (default: 1, use 2 for larger sims)"
            echo "  --stagger S  Seconds between user spawns (default: 5, use 0 for all-at-once)"
            exit 1
            ;;
    esac
done

# Configuration
RESULTS="scaling_results.txt"
if [[ -n "$CUSTOM_AGENTS" ]]; then
    IFS=',' read -ra AGENT_COUNTS <<< "$CUSTOM_AGENTS"
else
    AGENT_COUNTS=(85 100 200 400 800 1000)
fi

# Parse duration and calculate default timeout if not specified
# Convert duration like "6h", "2h30m", "90m" to seconds
parse_duration_to_seconds() {
    local dur="$1"
    local total=0
    # Extract hours if present
    if [[ "$dur" =~ ([0-9]+)h ]]; then
        total=$((total + ${BASH_REMATCH[1]} * 3600))
    fi
    # Extract minutes if present
    if [[ "$dur" =~ ([0-9]+)m ]]; then
        total=$((total + ${BASH_REMATCH[1]} * 60))
    fi
    # If just a number, assume seconds
    if [[ "$dur" =~ ^[0-9]+$ ]]; then
        total=$dur
    fi
    echo "$total"
}

SIM_DURATION_SECS=$(parse_duration_to_seconds "$SIM_DURATION")
if [[ -z "$TIMEOUT" ]]; then
    # Default timeout is 2x simulation duration
    TIMEOUT=$((SIM_DURATION_SECS * 2))
else
    # Parse timeout if given in flexible format
    TIMEOUT=$(parse_duration_to_seconds "$TIMEOUT")
fi
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
    local mode_info=""
    if [[ -n "$FAST_MODE" ]]; then
        mode_info=" (FAST MODE)"
    fi
    local threads_info=""
    if [[ -n "$THREADS" ]]; then
        threads_info=", threads=$THREADS"
    fi
    local stagger_info="5s"  # default
    if [[ -n "$STAGGER" ]]; then
        stagger_info="${STAGGER}s"
    fi
    echo "# Scaling Test Results - $(date '+%Y-%m-%d %H:%M:%S')${mode_info}"
    echo "# Hardware: ${mem_total} RAM, ${cpu_count} CPUs"
    echo "# Timeout: ${TIMEOUT}s ($((TIMEOUT / 60)) minutes), Sim duration: ${SIM_DURATION}${threads_info}"
    echo "# Config: 5 fixed miners + variable users, ${stagger_info} stagger"
    echo ""
}

# Memory monitor - runs in background, samples every 5 seconds
# Writes peak RSS (in KB) to the specified file
# Args: $1 = PID to monitor, $2 = output file for peak, $3 = log file for samples
monitor_memory() {
    local pid=$1
    local peak_file=$2
    local sample_log=$3
    local peak_kb=0
    local sample_count=0
    local low_mem_warned=false

    echo "# Memory samples (time, shadow_rss_mb, system_free_mb, system_used_pct)" > "$sample_log"

    while kill -0 "$pid" 2>/dev/null; do
        # Get total RSS of Shadow and all children (in KB)
        # Use ps to get all processes in the process group
        local rss_kb=0
        while read -r child_rss; do
            rss_kb=$((rss_kb + child_rss))
        done < <(pgrep -P "$pid" 2>/dev/null | xargs -I{} ps -o rss= -p {} 2>/dev/null | tr -d ' ' || echo 0)

        # Also add the parent process RSS
        local parent_rss=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ')
        if [[ -n "$parent_rss" ]]; then
            rss_kb=$((rss_kb + parent_rss))
        fi

        # Track peak
        if [[ "$rss_kb" -gt "$peak_kb" ]]; then
            peak_kb=$rss_kb
        fi

        # Get system memory info
        local mem_info=$(free -m | awk '/^Mem:/{print $3, $2, $7}')
        local used_mb=$(echo "$mem_info" | awk '{print $1}')
        local total_mb=$(echo "$mem_info" | awk '{print $2}')
        local avail_mb=$(echo "$mem_info" | awk '{print $3}')
        local used_pct=$((used_mb * 100 / total_mb))

        # Log sample
        local rss_mb=$((rss_kb / 1024))
        echo "$(date '+%H:%M:%S'), ${rss_mb}, ${avail_mb}, ${used_pct}%" >> "$sample_log"

        # Warn if system memory is getting low (less than 10% available)
        if [[ "$used_pct" -gt 90 ]] && [[ "$low_mem_warned" == "false" ]]; then
            echo -e "  ${YELLOW}WARNING: System memory at ${used_pct}% (${avail_mb}MB free)${NC}" >&2
            low_mem_warned=true
        fi

        ((sample_count++))
        sleep 5
    done

    # Write peak to file
    echo "$peak_kb" > "$peak_file"
    echo "# Samples: $sample_count, Peak RSS: $((peak_kb / 1024))MB" >> "$sample_log"
}

# Run a single test
# Status messages go to stderr (console), result line goes to stdout (captured)
run_test() {
    local agent_count=$1
    local user_count=$((agent_count - 5))
    local config_file="$TEMP_DIR/config_${agent_count}.yaml"
    local shadow_dir="$TEMP_DIR/shadow_${agent_count}"
    local log_file="$TEMP_DIR/run_${agent_count}.log"
    local time_file="$TEMP_DIR/time_${agent_count}.txt"

    echo -e "${YELLOW}Testing $agent_count agents (5 miners + $user_count users)...${NC}" >&2

    # Build config generation args
    local config_args="--agents $agent_count --duration $SIM_DURATION -o $config_file $FAST_MODE"
    if [[ -n "$THREADS" ]]; then
        config_args="$config_args --threads $THREADS"
    fi
    if [[ -n "$STAGGER" ]]; then
        config_args="$config_args --stagger-interval $STAGGER"
    fi

    # Generate monerosim config
    echo "  Generating config..." >&2
    python3 scripts/generate_config.py $config_args 2>&2 || {
        echo "  FAIL: Config generation failed" >&2
        printf "%-7s | %-6s | %-7s | %-8s | %-8s | %s\n" "$agent_count" "$user_count" "FAIL" "-" "-" "Config generation failed"
        return 1
    }

    # Generate shadow config
    echo "  Generating shadow config..." >&2
    rm -rf "$shadow_dir"
    mkdir -p "$shadow_dir"
    # Clean monerosim shared state from previous runs
    rm -rf /tmp/monerosim_shared
    if ! "$MONEROSIM_BIN" --config "$config_file" --output "$shadow_dir" > "$TEMP_DIR/monerosim_${agent_count}.log" 2>&1; then
        echo "  FAIL: Shadow config generation failed" >&2
        printf "%-7s | %-6s | %-7s | %-8s | %-8s | %s\n" "$agent_count" "$user_count" "FAIL" "-" "-" "Shadow config generation failed"
        return 1
    fi

    # Verify shadow config was created
    if [[ ! -f "$shadow_dir/shadow_agents.yaml" ]]; then
        echo "  FAIL: shadow_agents.yaml not created" >&2
        printf "%-7s | %-6s | %-7s | %-8s | %-8s | %s\n" "$agent_count" "$user_count" "FAIL" "-" "-" "shadow_agents.yaml not created"
        return 1
    fi

    # Clean previous shadow run artifacts (matching run_sim.sh)
    rm -rf shadow.data/
    rm -rf shadow.log

    # Files for memory monitoring
    local peak_file="$TEMP_DIR/peak_${agent_count}.txt"
    local sample_log="$TEMP_DIR/memory_samples_${agent_count}.csv"

    # Run shadow with timeout and capture stats
    echo "  Running shadow (timeout: ${TIMEOUT}s)..." >&2
    local start_time=$(date +%s)

    # Start Shadow in background
    timeout "$TIMEOUT" "$SHADOW_BIN" "$shadow_dir/shadow_agents.yaml" \
        > "$log_file" 2>&1 &
    local shadow_pid=$!

    # Start memory monitor in background
    monitor_memory "$shadow_pid" "$peak_file" "$sample_log" &
    local monitor_pid=$!

    # Wait for Shadow to finish
    wait "$shadow_pid" 2>/dev/null
    local exit_code=$?

    # Give monitor a moment to finish, then kill if still running
    sleep 1
    kill "$monitor_pid" 2>/dev/null
    wait "$monitor_pid" 2>/dev/null

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local duration_fmt=$(printf "%d:%02d" $((duration / 60)) $((duration % 60)))

    # Read peak memory from monitor
    local mem_kb=0
    if [[ -f "$peak_file" ]]; then
        mem_kb=$(cat "$peak_file")
    fi

    local mem_readable=""
    if [[ -n "$mem_kb" && "$mem_kb" -gt 0 ]]; then
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
        echo -e "  ${GREEN}SUCCESS${NC} - Completed in $duration_fmt, peak RAM: $mem_readable" >&2
    elif [[ $exit_code -eq 124 ]]; then
        status="TIMEOUT"
        notes="Exceeded ${TIMEOUT}s timeout"
        echo -e "  ${YELLOW}TIMEOUT${NC} - Exceeded timeout after $duration_fmt" >&2
    elif [[ $exit_code -eq 137 ]]; then
        status="OOM"
        notes="Killed by OOM killer (SIGKILL)"
        echo -e "  ${RED}OOM${NC} - Killed after $duration_fmt, peak RAM: $mem_readable" >&2
    elif [[ -n "$sim_finished" ]]; then
        # Shadow completed but exited with error due to process states
        status="SUCCESS"
        notes="Sim completed (processes still running at end)"
        echo -e "  ${GREEN}SUCCESS${NC} - Completed in $duration_fmt, peak RAM: $mem_readable" >&2
    else
        status="FAIL"
        notes="Exit code: $exit_code"
        echo -e "  ${RED}FAIL${NC} - Exit code $exit_code after $duration_fmt" >&2
    fi

    # Output result line
    printf "%-7s | %-6s | %-7s | %-8s | %-8s | %s\n" \
        "$agent_count" "$user_count" "$status" "$mem_readable" "$duration_fmt" "$notes"

    # Always return success so the script continues to the next test
    # The main loop checks status via the result string and handles consecutive failures
    return 0
}

# Main
main() {
    # Rebuild monerosim to ensure latest changes are included
    echo -e "${YELLOW}Rebuilding monerosim...${NC}"
    cargo build --release || {
        echo -e "${RED}Error: cargo build failed${NC}"
        exit 1
    }
    echo -e "${GREEN}Build complete${NC}"
    echo ""

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
        echo "$result"  # Also print to console

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

    # Info about output files
    echo ""
    echo "Results saved to: $RESULTS"
    echo "Memory samples in: $TEMP_DIR/memory_samples_*.csv"
    echo "All temp files in: $TEMP_DIR"
}

main "$@"
