#!/bin/bash
#
# run_sim.sh - Run a MoneroSim simulation end-to-end and archive results
#
# Usage: ./run_sim.sh --config <path.yaml> [options]
#
# Options:
#   --config <path>        Monerosim config file (required)
#   --name <name>          Run name (default: derived from config filename)
#   --archive-dir <dir>    Archive location (default: ../archived_monerosims)
#   --no-monitor           Skip live progress display
#   --analyze              Run post-simulation analysis (off by default)
#   --no-build             Skip cargo build (use existing binary)
#   --help                 Show help

set -euo pipefail

# ============================================================
# Constants
# ============================================================
SIM_EPOCH=946684800  # 2000-01-01 00:00:00 UTC (Shadow epoch)
MONITOR_INTERVAL=30  # seconds between progress refreshes
MEMORY_SAMPLE_INTERVAL=30

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ============================================================
# CLI Parsing
# ============================================================
CONFIG=""
RUN_NAME=""
ARCHIVE_BASE=""
SHOW_MONITOR=true
RUN_ANALYZE=false
DO_BUILD=true

usage() {
    cat <<'EOF'
Usage: ./run_sim.sh --config <path.yaml> [options]

Run a MoneroSim simulation end-to-end and archive all results.

Options:
  --config <path>        Monerosim config file (required)
  --name <name>          Run name (default: derived from config filename)
  --archive-dir <dir>    Archive location (default: ../archived_monerosims)
  --no-monitor           Skip live progress display
  --analyze              Run post-simulation analysis (off by default)
  --no-build             Skip cargo build (use existing binary)
  --help                 Show help

Examples:
  ./run_sim.sh --config test_configs/20260305.yaml
  ./run_sim.sh --config test_configs/20260305.yaml --name scaling_1000 --analyze
  ./run_sim.sh --config test_configs/ultra_minimal_test.yaml --no-build
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --name)
            RUN_NAME="$2"
            shift 2
            ;;
        --archive-dir)
            ARCHIVE_BASE="$2"
            shift 2
            ;;
        --no-monitor)
            SHOW_MONITOR=false
            shift
            ;;
        --analyze)
            RUN_ANALYZE=true
            shift
            ;;
        --no-build)
            DO_BUILD=false
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            echo "Run './run_sim.sh --help' for usage."
            exit 1
            ;;
    esac
done

if [[ -z "$CONFIG" ]]; then
    echo -e "${YELLOW}Error: --config is required${NC}"
    echo "Run './run_sim.sh --help' for usage."
    exit 1
fi

# Defaults
[[ -z "$ARCHIVE_BASE" ]] && ARCHIVE_BASE="$SCRIPT_DIR/../archived_monerosims"
if [[ -z "$RUN_NAME" ]]; then
    # Derive from config filename: test_configs/20260305.yaml -> 20260305
    RUN_NAME=$(basename "$CONFIG" .yaml)
fi

SHADOW_BIN="$HOME/.monerosim/bin/shadow"
MONEROSIM_BIN="$SCRIPT_DIR/target/release/monerosim"
SHADOW_OUTPUT="$SCRIPT_DIR/shadow_output"
SHARED_DIR="/tmp/monerosim_shared"

# ============================================================
# Utility functions
# ============================================================
log_step() {
    echo ""
    echo -e "${BOLD}${CYAN}==> $1${NC}"
}

log_ok() {
    echo -e "  ${GREEN}$1${NC}"
}

log_warn() {
    echo -e "  ${YELLOW}WARNING: $1${NC}"
}

log_err() {
    echo -e "  ${YELLOW}ERROR: $1${NC}"
}

log_info() {
    echo -e "  $1"
}

# Convert duration strings like "2.5h", "90m", "6h30m", or raw seconds to seconds
parse_duration_to_seconds() {
    local dur="$1"
    local total=0

    # Handle pure integer (seconds)
    if [[ "$dur" =~ ^[0-9]+$ ]]; then
        echo "$dur"
        return
    fi

    # Handle decimal hours like "2.5h"
    if [[ "$dur" =~ ^([0-9]+\.?[0-9]*)h$ ]]; then
        total=$(python3 -c "print(int(float('${BASH_REMATCH[1]}') * 3600))")
        echo "$total"
        return
    fi

    # Handle compound like "6h30m"
    if [[ "$dur" =~ ([0-9]+)h ]]; then
        total=$((total + ${BASH_REMATCH[1]} * 3600))
    fi
    if [[ "$dur" =~ ([0-9]+)m ]]; then
        total=$((total + ${BASH_REMATCH[1]} * 60))
    fi
    if [[ "$dur" =~ ([0-9]+)s$ ]]; then
        total=$((total + ${BASH_REMATCH[1]}))
    fi

    echo "$total"
}

# Format seconds as human-readable "Xh Ym"
format_duration() {
    local secs=$1
    local hours=$((secs / 3600))
    local mins=$(( (secs % 3600) / 60 ))
    if [[ $hours -gt 0 ]]; then
        printf "%dh %dm" "$hours" "$mins"
    else
        printf "%dm %ds" "$mins" $((secs % 60))
    fi
}

# Format bytes as human-readable
format_bytes() {
    local bytes=$1
    if [[ $bytes -ge 1073741824 ]]; then
        python3 -c "print(f'{$bytes / 1073741824:.1f} GB')"
    elif [[ $bytes -ge 1048576 ]]; then
        python3 -c "print(f'{$bytes / 1048576:.1f} MB')"
    elif [[ $bytes -ge 1024 ]]; then
        echo "$((bytes / 1024)) KB"
    else
        echo "${bytes} B"
    fi
}

# Format KB as human-readable
format_kb() {
    local kb=$1
    if [[ $kb -ge 1048576 ]]; then
        python3 -c "print(f'{$kb / 1048576:.1f} GB')"
    elif [[ $kb -ge 1024 ]]; then
        python3 -c "print(f'{$kb / 1024:.1f} MB')"
    else
        echo "${kb} KB"
    fi
}

# ============================================================
# Phase 1: Pre-flight Checks
# ============================================================
preflight_checks() {
    log_step "Phase 1: Pre-flight Checks"

    # Check shadow binary
    if [[ ! -x "$SHADOW_BIN" ]]; then
        log_err "Shadow binary not found at $SHADOW_BIN"
        log_info "Run ./setup.sh to install Shadow"
        exit 1
    fi
    log_ok "Shadow binary: $SHADOW_BIN"

    # Check config file
    if [[ ! -f "$CONFIG" ]]; then
        log_err "Config file not found: $CONFIG"
        exit 1
    fi
    log_ok "Config file: $CONFIG"

    # Parse stop_time from config
    STOP_TIME_RAW=$(python3 -c "
import yaml, sys
with open('$CONFIG') as f:
    cfg = yaml.safe_load(f)
st = cfg.get('general', {}).get('stop_time', '')
print(st)
" 2>/dev/null)

    if [[ -z "$STOP_TIME_RAW" ]]; then
        log_err "Could not parse stop_time from config"
        exit 1
    fi

    STOP_TIME_SECS=$(parse_duration_to_seconds "$STOP_TIME_RAW")
    log_ok "Simulation duration: $STOP_TIME_RAW ($STOP_TIME_SECS seconds)"

    # Parse agent counts from config metadata or agent list
    CONFIG_SUMMARY=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    cfg = yaml.safe_load(f)
meta = cfg.get('metadata', {})
agents_meta = meta.get('agents', {})
agents = cfg.get('agents', {})
miners = agents_meta.get('miners', sum(1 for a in agents if a.startswith('miner-0') or a.startswith('miner-1')))
users = agents_meta.get('users', sum(1 for a in agents if a.startswith('user-')))
total = agents_meta.get('total', len(agents))
relays = sum(1 for a in agents if a.startswith('relay-'))
print(f'{total} {miners} {users} {relays}')
" 2>/dev/null)

    read -r CFG_TOTAL CFG_MINERS CFG_USERS CFG_RELAYS <<< "$CONFIG_SUMMARY"
    log_ok "Agents: ${CFG_TOTAL} total (${CFG_MINERS} miners, ${CFG_USERS} users, ${CFG_RELAYS} relays)"

    # Disk space check
    check_disk_space "$ARCHIVE_BASE"
}

check_disk_space() {
    local archive_dir="$1"

    # Create archive dir if it doesn't exist (needed for df check)
    mkdir -p "$archive_dir"

    # Find largest existing archived run
    local max_size_kb=0
    local largest_run=""
    for dir in "$archive_dir"/*/; do
        [[ -d "$dir" ]] || continue
        local size_kb
        size_kb=$(du -sk "$dir" 2>/dev/null | cut -f1)
        if [[ "$size_kb" -gt "$max_size_kb" ]]; then
            max_size_kb=$size_kb
            largest_run=$(basename "$dir")
        fi
    done

    if [[ "$max_size_kb" -eq 0 ]]; then
        log_ok "Disk space: first run, skipping size estimate"
        return 0
    fi

    # Get free space on archive filesystem
    local free_kb
    free_kb=$(df -k "$archive_dir" | tail -1 | awk '{print $4}')

    log_info "Largest archived run: $largest_run ($(format_kb "$max_size_kb"))"
    log_info "Free disk space: $(format_kb "$free_kb")"

    if [[ "$free_kb" -lt "$max_size_kb" ]]; then
        echo ""
        log_warn "Free space may be insufficient for another run!"
        log_info "  Needed (estimate): $(format_kb "$max_size_kb")"
        log_info "  Available: $(format_kb "$free_kb")"
        echo ""
        echo "  Archived runs (by size):"
        du -sh "$archive_dir"/*/ 2>/dev/null | sort -rh | while read -r line; do
            echo "    $line"
        done
        echo ""
        read -rp "  Continue anyway? (yes/no): " CONFIRM
        if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
            echo "Aborted."
            exit 1
        fi
    else
        log_ok "Disk space: $(format_kb "$free_kb") free (estimate needed: $(format_kb "$max_size_kb"))"
    fi
}

# ============================================================
# Phase 2: Build & Generate
# ============================================================
build_and_generate() {
    log_step "Phase 2: Build & Generate"

    # Create archive directory with timestamp
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    ARCHIVE_DIR="$ARCHIVE_BASE/${TIMESTAMP}_${RUN_NAME}"
    mkdir -p "$ARCHIVE_DIR"
    log_ok "Archive directory: $ARCHIVE_DIR"

    # Build
    if [[ "$DO_BUILD" == true ]]; then
        log_info "Building monerosim (cargo build --release)..."
        if cargo build --release > "$ARCHIVE_DIR/build.log" 2>&1; then
            log_ok "Build successful"
        else
            log_err "Build failed! See $ARCHIVE_DIR/build.log"
            tail -20 "$ARCHIVE_DIR/build.log"
            exit 1
        fi
    else
        log_info "Skipping build (--no-build)"
        if [[ ! -x "$MONEROSIM_BIN" ]]; then
            log_err "monerosim binary not found at $MONEROSIM_BIN"
            log_info "Run without --no-build to compile first"
            exit 1
        fi
    fi

    # Copy input config to archive
    cp "$CONFIG" "$ARCHIVE_DIR/input_config.yaml"
    log_ok "Input config archived"

    # Generate Shadow config
    log_info "Generating Shadow configuration..."
    if "$MONEROSIM_BIN" --config "$CONFIG" --output "$SHADOW_OUTPUT" > "$ARCHIVE_DIR/monerosim.log" 2>&1; then
        log_ok "Shadow config generated"
    else
        log_err "Config generation failed! See $ARCHIVE_DIR/monerosim.log"
        tail -20 "$ARCHIVE_DIR/monerosim.log"
        exit 1
    fi

    # Copy shadow_agents.yaml to archive
    if [[ -f "$SHADOW_OUTPUT/shadow_agents.yaml" ]]; then
        cp "$SHADOW_OUTPUT/shadow_agents.yaml" "$ARCHIVE_DIR/shadow_agents.yaml"
        log_ok "shadow_agents.yaml archived"
    else
        log_err "shadow_agents.yaml not generated!"
        exit 1
    fi
}

# ============================================================
# Phase 3: Run Simulation
# ============================================================
run_simulation() {
    log_step "Phase 3: Starting Simulation"

    # Clean old simulation data
    log_info "Cleaning previous simulation data..."
    rm -rf shadow.data/ shadow.log

    # Start Shadow in its own process group (via setsid) so Ctrl+C won't reach it
    SHADOW_LOG="$ARCHIVE_DIR/shadow_run.log"
    log_info "Starting Shadow..."
    setsid "$SHADOW_BIN" "$SHADOW_OUTPUT/shadow_agents.yaml" > "$SHADOW_LOG" 2>&1 &
    SHADOW_PID=$!
    START_TIME=$(date +%s)
    START_TIME_FMT=$(date '+%Y-%m-%d %H:%M:%S')

    log_ok "Shadow started (PID: $SHADOW_PID)"
    log_ok "Log: $SHADOW_LOG"

    # Start memory monitor in background
    start_memory_monitor "$SHADOW_PID" "$ARCHIVE_DIR/memory_samples.csv" &
    MONITOR_PID=$!

    # Wait for Shadow with or without live monitor
    if [[ "$SHOW_MONITOR" == true ]]; then
        live_progress_monitor "$SHADOW_PID" "$SHADOW_LOG"
    else
        log_info "Waiting for simulation to complete (--no-monitor)..."
        log_info "Monitor manually with: tail -f $SHADOW_LOG"
    fi

    # Wait for Shadow and capture exit code
    # Shadow often exits with code 1 when processes are still running at stop time,
    # which is expected behavior, so we don't let set -e kill us here.
    SHADOW_EXIT=0
    wait "$SHADOW_PID" 2>/dev/null || SHADOW_EXIT=$?

    # Stop memory monitor
    sleep 1
    kill "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" 2>/dev/null || true

    END_TIME=$(date +%s)
    WALL_DURATION=$((END_TIME - START_TIME))

    echo ""
    # Check if simulation completed successfully
    local sim_finished=false
    if grep -q "Finished simulation" "$SHADOW_LOG" 2>/dev/null; then
        sim_finished=true
    elif grep -q "managed processes in unexpected final state" "$SHADOW_LOG" 2>/dev/null; then
        sim_finished=true
    fi

    if [[ $SHADOW_EXIT -eq 0 ]] || [[ "$sim_finished" == true ]]; then
        log_ok "Simulation completed in $(format_duration $WALL_DURATION)"
    elif [[ $SHADOW_EXIT -eq 137 ]]; then
        log_err "Simulation killed (OOM?) after $(format_duration $WALL_DURATION)"
    else
        log_warn "Simulation exited with code $SHADOW_EXIT after $(format_duration $WALL_DURATION)"
    fi
}

# ============================================================
# Memory Monitor (background process)
# ============================================================
start_memory_monitor() {
    local shadow_pid=$1
    local csv_file=$2

    echo "timestamp,shadow_rss_mb,monerod_rss_mb,wallet_rss_mb,total_rss_mb,system_free_mb,system_used_pct" > "$csv_file"

    while kill -0 "$shadow_pid" 2>/dev/null; do
        # Aggregate RSS by process type from all user processes
        local shadow_kb=0 monerod_kb=0 wallet_kb=0 other_kb=0

        while read -r rss comm; do
            [[ -z "$rss" ]] && continue
            case "$comm" in
                shadow)    shadow_kb=$((shadow_kb + rss)) ;;
                monerod)   monerod_kb=$((monerod_kb + rss)) ;;
                monero-wa*) wallet_kb=$((wallet_kb + rss)) ;;
                *)         other_kb=$((other_kb + rss)) ;;
            esac
        done < <(ps -u "$USER" -o rss=,comm= 2>/dev/null)

        local total_kb=$((shadow_kb + monerod_kb + wallet_kb + other_kb))

        # System memory
        local mem_info
        mem_info=$(free -m | awk '/^Mem:/{print $3, $2, $7}')
        local used_mb total_mb avail_mb used_pct
        used_mb=$(echo "$mem_info" | awk '{print $1}')
        total_mb=$(echo "$mem_info" | awk '{print $2}')
        avail_mb=$(echo "$mem_info" | awk '{print $3}')
        used_pct=$((used_mb * 100 / total_mb))

        printf "%s,%d,%d,%d,%d,%d,%d%%\n" \
            "$(date '+%H:%M:%S')" \
            "$((shadow_kb / 1024))" \
            "$((monerod_kb / 1024))" \
            "$((wallet_kb / 1024))" \
            "$((total_kb / 1024))" \
            "$avail_mb" \
            "$used_pct" >> "$csv_file"

        sleep "$MEMORY_SAMPLE_INTERVAL"
    done
}

# ============================================================
# Phase 4: Live Progress Monitor
# ============================================================
live_progress_monitor() {
    local shadow_pid=$1
    local shadow_log=$2
    local prev_sizes_file="/tmp/monerosim_monitor_sizes.tmp"
    local display_lines=0

    # Clean previous sizes file
    rm -f "$prev_sizes_file"

    echo ""
    echo -e "${BOLD}Starting live progress monitor (refresh every ${MONITOR_INTERVAL}s)${NC}"
    echo -e "${DIM}Press Ctrl+C to stop monitor (simulation continues in background)${NC}"
    echo ""

    # Trap SIGINT: stop the monitor and exit, leaving Shadow running
    trap 'echo ""
echo -e "${YELLOW}Monitor stopped. Simulation still running (PID: $shadow_pid).${NC}"
echo "Resume monitoring: tail -f $shadow_log"
echo "Check status:      ./scripts/check_sim.sh"
echo "Kill simulation:   kill $shadow_pid"
kill "$MONITOR_PID" 2>/dev/null || true
rm -f "$prev_sizes_file"
exit 0' INT

    while kill -0 "$shadow_pid" 2>/dev/null; do
        # Clear previous display
        if [[ $display_lines -gt 0 ]]; then
            # Move cursor up and clear lines
            printf '\033[%dA' "$display_lines"
            for ((i = 0; i < display_lines; i++)); do
                printf '\033[2K\n'
            done
            printf '\033[%dA' "$display_lines"
        fi

        # Build display
        local output=""
        local lines=0

        output+="${BOLD}${CYAN}=== MoneroSim Simulation Monitor ===${NC}\n"; lines=$((lines + 1))
        output+="Run:        ${RUN_NAME}\n"; lines=$((lines + 1))
        output+="Config:     ${CFG_TOTAL} nodes (${CFG_MINERS} miners, ${CFG_USERS} users, ${CFG_RELAYS} relays)\n"; lines=$((lines + 1))
        output+="Started:    ${START_TIME_FMT}\n"; lines=$((lines + 1))
        output+="\n"; lines=$((lines + 1))

        # Progress calculation
        local sim_timestamp=""
        local sim_elapsed_secs=0
        local progress_pct=0

        # Extract latest timestamp from shadow log
        sim_timestamp=$(tail -100 "$shadow_log" 2>/dev/null | grep -oP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}' | tail -1 || true)

        if [[ -n "$sim_timestamp" ]]; then
            sim_elapsed_secs=$(python3 -c "
from datetime import datetime
dt = datetime.strptime('$sim_timestamp', '%Y-%m-%d %H:%M:%S')
epoch = datetime(2000, 1, 1)
print(int((dt - epoch).total_seconds()))
" 2>/dev/null || echo 0)

            if [[ $STOP_TIME_SECS -gt 0 ]]; then
                progress_pct=$(python3 -c "print(f'{min($sim_elapsed_secs / $STOP_TIME_SECS * 100, 100):.1f}')" 2>/dev/null || echo "0.0")
            fi
        fi

        # Progress bar
        local bar_width=30
        local filled=0
        if [[ -n "$progress_pct" && "$progress_pct" != "0.0" ]]; then
            filled=$(python3 -c "print(int(float('$progress_pct') / 100 * $bar_width))" 2>/dev/null || echo 0)
        fi
        local empty=$((bar_width - filled))
        local bar=""
        for ((i = 0; i < filled; i++)); do bar+="█"; done
        for ((i = 0; i < empty; i++)); do bar+="░"; done

        local sim_dur_fmt
        sim_dur_fmt=$(format_duration "$sim_elapsed_secs")
        local stop_dur_fmt
        stop_dur_fmt=$(format_duration "$STOP_TIME_SECS")

        output+="Progress:   [${bar}] ${progress_pct}%  (${sim_dur_fmt} / ${stop_dur_fmt})\n"; lines=$((lines + 1))

        if [[ -n "$sim_timestamp" ]]; then
            output+="Sim time:   ${sim_timestamp}\n"; lines=$((lines + 1))
        fi

        local now
        now=$(date +%s)
        local wall_elapsed=$((now - START_TIME))
        local wall_fmt
        wall_fmt=$(format_duration "$wall_elapsed")
        output+="Wall time:  ${wall_fmt} elapsed\n"; lines=$((lines + 1))
        output+="\n"; lines=$((lines + 1))

        # Process counts and memory
        local shadow_cnt=0 monerod_cnt=0 wallet_cnt=0
        local shadow_kb=0 monerod_kb=0 wallet_kb=0

        while read -r rss comm; do
            [[ -z "$rss" ]] && continue
            case "$comm" in
                shadow)
                    shadow_kb=$((shadow_kb + rss))
                    shadow_cnt=$((shadow_cnt + 1))
                    ;;
                monerod)
                    monerod_kb=$((monerod_kb + rss))
                    monerod_cnt=$((monerod_cnt + 1))
                    ;;
                monero-wa*)
                    wallet_kb=$((wallet_kb + rss))
                    wallet_cnt=$((wallet_cnt + 1))
                    ;;
            esac
        done < <(ps -u "$USER" -o rss=,comm= 2>/dev/null)

        local total_kb=$((shadow_kb + monerod_kb + wallet_kb))
        local shadow_mb=$((shadow_kb / 1024))
        local monerod_mb=$((monerod_kb / 1024))
        local wallet_mb=$((wallet_kb / 1024))
        local total_mb=$((total_kb / 1024))

        # Use GB for display if > 1024 MB
        local shadow_disp monerod_disp wallet_disp total_disp
        shadow_disp=$(format_kb "$shadow_kb")
        monerod_disp=$(format_kb "$monerod_kb")
        wallet_disp=$(format_kb "$wallet_kb")
        total_disp=$(format_kb "$total_kb")

        output+="Processes:  ${monerod_cnt} monerod  |  ${wallet_cnt} wallet-rpc  |  ${shadow_cnt} shadow\n"; lines=$((lines + 1))
        output+="Memory:     Shadow ${shadow_disp}  |  Monerod ${monerod_disp}  |  Wallets ${wallet_disp}  |  Total ${total_disp}\n"; lines=$((lines + 1))

        # Free disk space
        local free_kb
        free_kb=$(df -k . | tail -1 | awk '{print $4}')
        output+="Free disk:  $(format_kb "$free_kb")\n"; lines=$((lines + 1))
        output+="\n"; lines=$((lines + 1))

        # Node health via blockchain growth
        local nodes_online=0
        local nodes_syncing=0
        local -a deltas=()

        # Scan all data.mdb files
        local current_sizes=""
        while IFS= read -r -d '' mdb_file; do
            local node_name
            node_name=$(echo "$mdb_file" | grep -oP 'monero-\K[^/]+')
            local file_size
            file_size=$(stat -c%b "$mdb_file" 2>/dev/null || echo 0)  # blocks allocated (not apparent size)
            [[ "$file_size" -eq 0 ]] && continue

            nodes_online=$((nodes_online + 1))
            current_sizes+="${node_name}:${file_size}\n"

            # Compare with previous sizes
            if [[ -f "$prev_sizes_file" ]]; then
                local prev_size
                prev_size=$(grep "^${node_name}:" "$prev_sizes_file" 2>/dev/null | cut -d: -f2 || true)
                if [[ -n "$prev_size" ]]; then
                    local delta=$((file_size - prev_size))
                    deltas+=("$delta")
                    if [[ $delta -gt 0 ]]; then
                        nodes_syncing=$((nodes_syncing + 1))
                    fi
                fi
            fi
        done < <(find /tmp -maxdepth 4 -path '*/monero-*/fake/lmdb/data.mdb' -print0 2>/dev/null)

        # Save current sizes for next cycle
        echo -e "$current_sizes" > "$prev_sizes_file"

        local total_expected=$((CFG_MINERS + CFG_USERS + CFG_RELAYS))
        output+="Nodes:      ${nodes_online}/${total_expected} online"; lines=$((lines + 1))

        if [[ ${#deltas[@]} -gt 0 ]]; then
            output+="  |  ${nodes_syncing} actively syncing\n"

            # Compute stats on deltas
            local stats
            stats=$(python3 -c "
import sys
deltas = [${deltas[*]}]
deltas.sort()
n = len(deltas)
mx = max(deltas)
mn = min(deltas)
mean = sum(deltas) / n
median = deltas[n // 2] if n % 2 else (deltas[n // 2 - 1] + deltas[n // 2]) / 2

def fmt(b):
    if b >= 1048576: return f'{b / 1048576:.1f}M'
    if b >= 1024: return f'{b / 1024:.0f}K'
    return f'{b}B'

print(f'max {fmt(mx)}  mean {fmt(mean)}  median {fmt(median)}  min {fmt(mn)}')
" 2>/dev/null || echo "")

            if [[ -n "$stats" ]]; then
                output+="Chain growth (${MONITOR_INTERVAL}s): ${stats}\n"; lines=$((lines + 1))
            fi
        else
            output+="\n"
        fi

        output+="\n"; lines=$((lines + 1))
        output+="${DIM}Last update: $(date '+%Y-%m-%d %H:%M:%S')${NC}\n"; lines=$((lines + 1))

        # Print the display
        echo -ne "$output"
        display_lines=$lines

        sleep "$MONITOR_INTERVAL"
    done

    # Reset trap
    trap - INT

    # Clean up temp file
    rm -f "$prev_sizes_file"
}

# ============================================================
# Phase 5: Post-Simulation Archiving
# ============================================================
archive_results() {
    log_step "Phase 5: Archiving Results"

    # 5a. Shadow data
    if [[ -d "shadow.data" ]]; then
        log_info "Moving shadow.data/ to archive..."
        mv shadow.data/ "$ARCHIVE_DIR/shadow.data/"
        log_ok "shadow.data archived"
    else
        log_warn "shadow.data/ not found"
    fi

    # Copy monerosim_monitor.log if it exists (generated by simulation-monitor agent)
    local monitor_log
    monitor_log=$(find /tmp/monerosim_shared -name 'monerosim_monitor.log' 2>/dev/null | head -1)
    if [[ -n "$monitor_log" && -f "$monitor_log" ]]; then
        cp "$monitor_log" "$ARCHIVE_DIR/monerosim_monitor.log"
        log_ok "monerosim_monitor.log archived"
    fi

    # 5b. Blockchain snapshots (3 copies: 1 miner, 1 user, 1 relay)
    archive_blockchain_snapshots

    # 5c. Transaction registry
    archive_transaction_registry

    # 5d. Analysis (opt-in)
    if [[ "$RUN_ANALYZE" == true ]]; then
        run_analysis
    fi
}

archive_blockchain_snapshots() {
    log_info "Archiving blockchain snapshots..."

    local shadow_agents="$ARCHIVE_DIR/shadow_agents.yaml"
    if [[ ! -f "$shadow_agents" ]]; then
        log_warn "shadow_agents.yaml not found, skipping blockchain snapshots"
        return
    fi

    # Extract data-dir paths for each node type
    local miner_dirs user_dirs relay_dirs
    miner_dirs=$(grep -oP 'data-dir=\K/tmp/monero-miner-[^ "]+' "$shadow_agents" 2>/dev/null | sort -u || true)
    user_dirs=$(grep -oP 'data-dir=\K/tmp/monero-user-[^ "]+' "$shadow_agents" 2>/dev/null | sort -u || true)
    relay_dirs=$(grep -oP 'data-dir=\K/tmp/monero-relay-[^ "]+' "$shadow_agents" 2>/dev/null | sort -u || true)

    # Pick one from each type
    local selected_miner selected_user selected_relay
    selected_miner=$(echo "$miner_dirs" | head -1)
    selected_user=$(echo "$user_dirs" | shuf 2>/dev/null | head -1)
    selected_relay=$(echo "$relay_dirs" | shuf 2>/dev/null | head -1)

    copy_blockchain_snapshot "$selected_miner" "miner"
    copy_blockchain_snapshot "$selected_user" "user"
    copy_blockchain_snapshot "$selected_relay" "relay"
}

copy_blockchain_snapshot() {
    local data_dir="$1"
    local node_type="$2"

    [[ -z "$data_dir" ]] && return

    local node_name
    node_name=$(basename "$data_dir")
    local lmdb_dir="$data_dir/fake/lmdb"

    if [[ -f "$lmdb_dir/data.mdb" ]]; then
        local dest="$ARCHIVE_DIR/blockchain/${node_name}"
        mkdir -p "$dest"
        cp "$lmdb_dir/data.mdb" "$dest/"
        [[ -f "$lmdb_dir/lock.mdb" ]] && cp "$lmdb_dir/lock.mdb" "$dest/"

        local size
        size=$(du -sh "$dest/data.mdb" 2>/dev/null | cut -f1)
        log_ok "Blockchain snapshot: $node_name (${size})"
    else
        log_warn "No blockchain data for $node_type at $lmdb_dir"
    fi
}

archive_transaction_registry() {
    log_info "Archiving transaction registry..."

    local tx_dir="$ARCHIVE_DIR/transaction_registry"
    mkdir -p "$tx_dir"

    local count=0
    for json_file in "$SHARED_DIR"/*.json; do
        [[ -f "$json_file" ]] || continue
        cp "$json_file" "$tx_dir/"
        count=$((count + 1))
    done

    if [[ $count -gt 0 ]]; then
        log_ok "Transaction registry: $count JSON files archived"
    else
        log_warn "No JSON files found in $SHARED_DIR"
    fi
}

run_analysis() {
    log_info "Running post-simulation analysis..."

    local analysis_script=""
    if [[ -f "$SCRIPT_DIR/analyze_scaling_test.sh" ]]; then
        analysis_script="$SCRIPT_DIR/analyze_scaling_test.sh"
    elif [[ -f "$SCRIPT_DIR/../scale_run_logs/analyze_scaling_test.sh" ]]; then
        analysis_script="$SCRIPT_DIR/../scale_run_logs/analyze_scaling_test.sh"
    elif [[ -f "$SCRIPT_DIR/scripts/post_run_analysis.sh" ]]; then
        analysis_script="$SCRIPT_DIR/scripts/post_run_analysis.sh"
    fi

    if [[ -n "$analysis_script" ]]; then
        log_info "Running: $analysis_script"
        bash "$analysis_script" > "$ARCHIVE_DIR/analysis.log" 2>&1 || true
        log_ok "Analysis complete (see $ARCHIVE_DIR/analysis.log)"
    else
        log_warn "No analysis script found (analyze_scaling_test.sh or scripts/post_run_analysis.sh)"
        log_info "Run analysis manually later with: ./scripts/post_run_analysis.sh"
    fi
}

# ============================================================
# Phase 6: Summary
# ============================================================
print_summary() {
    log_step "Phase 6: Summary"

    echo ""
    echo -e "${BOLD}${GREEN}Simulation run complete!${NC}"
    echo ""

    # Archive size
    local archive_size
    archive_size=$(du -sh "$ARCHIVE_DIR" 2>/dev/null | cut -f1)
    echo "  Archive:      $ARCHIVE_DIR"
    echo "  Archive size: $archive_size"
    echo ""

    # Wall time
    echo "  Wall time:    $(format_duration $WALL_DURATION)"
    echo "  Exit code:    $SHADOW_EXIT"
    echo ""

    # Blockchain snapshots
    if [[ -d "$ARCHIVE_DIR/blockchain" ]]; then
        echo "  Blockchain snapshots:"
        for snap_dir in "$ARCHIVE_DIR"/blockchain/*/; do
            [[ -d "$snap_dir" ]] || continue
            local snap_name
            snap_name=$(basename "$snap_dir")
            local snap_size
            snap_size=$(du -sh "$snap_dir" 2>/dev/null | cut -f1)
            echo "    - $snap_name ($snap_size)"
        done
        echo ""
    fi

    # Transaction registry
    if [[ -d "$ARCHIVE_DIR/transaction_registry" ]]; then
        local tx_count
        tx_count=$(ls -1 "$ARCHIVE_DIR/transaction_registry/"*.json 2>/dev/null | wc -l)
        echo "  Transaction registry: $tx_count files"
        echo ""
    fi

    # Archive contents listing
    echo "  Archive contents:"
    ls -1 "$ARCHIVE_DIR" | while read -r item; do
        if [[ -d "$ARCHIVE_DIR/$item" ]]; then
            local dir_size
            dir_size=$(du -sh "$ARCHIVE_DIR/$item" 2>/dev/null | cut -f1)
            echo "    ${item}/ ($dir_size)"
        else
            local file_size
            file_size=$(ls -lh "$ARCHIVE_DIR/$item" 2>/dev/null | awk '{print $5}')
            echo "    $item ($file_size)"
        fi
    done
    echo ""

    # Disk space remaining
    local free_kb
    free_kb=$(df -k "$ARCHIVE_DIR" | tail -1 | awk '{print $4}')
    echo "  Disk space remaining: $(format_kb "$free_kb")"
    echo ""
}

# ============================================================
# Main
# ============================================================
main() {
    echo -e "${BOLD}${CYAN}"
    echo "╔══════════════════════════════════════╗"
    echo "║      MoneroSim Simulation Runner     ║"
    echo "╚══════════════════════════════════════╝"
    echo -e "${NC}"

    preflight_checks
    build_and_generate
    run_simulation
    archive_results
    print_summary
}

main
