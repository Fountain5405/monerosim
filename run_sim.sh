#!/bin/bash
#
# run_sim.sh - Run a MoneroSim simulation end-to-end and archive results.
#
# Run ./run_sim.sh --help for the full option list (the usage() function
# below is the source of truth; do not duplicate it in this header).

set -euo pipefail

# ============================================================
# Constants
# ============================================================
SIM_EPOCH=946684800  # 2000-01-01 00:00:00 UTC (Shadow epoch)
MONITOR_INTERVAL=30  # seconds between progress refreshes
MEMORY_SAMPLE_INTERVAL=30

# Colors + shared logging vocabulary (log_step/log_ok/log_warn/log_err/log_info)
source "$(dirname "${BASH_SOURCE[0]}")/scripts/log_lib.sh"

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate the virtual environment if not already active
if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
fi

# ============================================================
# CLI Parsing
# ============================================================
CONFIG=""
RUN_NAME=""
ARCHIVE_BASE=""
REACHABLE=""              # "" = use config default; else fraction in [0,1] passed to monerosim --reachable
TURNOVER_SESSION=""          # "" = no turnover; else mean ONLINE session (e.g. 1h) -> monerosim --turnover-session
TURNOVER_DOWNTIME=""         # mean OFFLINE gap (e.g. 1h) -> monerosim --turnover-downtime
TURNOVER_MAX_SESSION=""      # optional hard session ceiling (e.g. 6h) -> monerosim --turnover-max-session
SHOW_MONITOR=true
RUN_ANALYZE=false
DO_BUILD=true
BLOCKCHAIN_ARCHIVE_PCT=""
DATA_DIR=""
RAMDISK_REQUEST=""        # "" = off, "auto" = size from estimate, else explicit (e.g. "8G")
RAMDISK_PATH=""           # set by mount_ramdisk() if mount succeeds
RAMDISK_MOUNTED=false     # cleared once watchdog has taken over
PREFLIGHT_ONLY=false      # if true, exit after preflight without touching shadow.data or /tmp
NO_ARCHIVE=false          # if true, skip the post-sim archive step (shadow.data, daemon logs,
                          # blockchain snapshots, summary report). Still cleans /tmp/monero-*
                          # unless --no-clean is also set.
NO_CLEAN=false            # if true, skip the /tmp/monero-* cleanup so the user can dig
                          # through raw blockchain DBs / config files / etc. by hand.

usage() {
    cat <<'EOF'
Usage: ./run_sim.sh --config <path.yaml> [options]

Run a MoneroSim simulation end-to-end and archive all results.

Options:
  --config <path>        Monerosim config file (required)
  --name <name>          Run name (default: derived from config filename)
  --reachable <frac>     Fraction of non-seed nodes reachable, [0.0-1.0]. 1.0 =
                         all reachable (default). Lower = mainnet-like NAT
                         majority (the rest get --hide-my-port). Seeds + miners
                         always reachable. Overrides general.reachable_fraction.
  --turnover-session <dur>  Enable peer turnover: mean ONLINE session (e.g. 1h).
                         Relays + users cycle offline/online; supernodes,
                         miners and seeds stay always-on. Overrides general.turnover.
  --turnover-downtime <dur> Mean OFFLINE gap for turnover (e.g. 1h). Average uptime =
                         session/(session+downtime).
  --turnover-max-session <dur>  Optional hard ceiling on a single turnover session.
  --archive-dir <dir>    Archive location (default: archived_runs)
  --data-dir <dir>       Shadow data output directory (default: shadow.data in cwd)
                         Use this to write simulation data to a different volume
  --ramdisk [SIZE]       Mount tmpfs for monerod data dirs (faster LMDB I/O).
                         Mounts at /tmp/monerosim_ramdisk_<pid>/ and overrides
                         general.daemon_data_dir. SIZE optional (e.g. 8G, 16G);
                         omit to auto-size from estimated chain growth.
                         Requires sudo. Cleaned up after shadow exits, even if
                         you Ctrl-C run_sim.sh in the meantime.
  --no-monitor           Skip live progress display
  --analyze              Run post-simulation analysis (off by default)
  --no-build             Skip cargo build (use existing binary)
  --archive-blockchain N   Archive N% of blockchains (default: 1 per type)
  --preflight-only       Run only Phase 1 (config inspection, disk estimate)
                         and exit. Does NOT touch shadow.data, /tmp, or
                         spawn shadow. Safe to run alongside an in-flight
                         simulation.
  --no-archive           Skip the post-simulation archive step. shadow.data/,
                         daemon bitmonero.log files, blockchain snapshots,
                         and summary.txt are NOT preserved. /tmp/monero-*
                         is still cleaned (unless --no-clean is also set).
                         Pre-run artifacts (input_config.yaml,
                         shadow_agents.yaml, build.log, monerosim.log,
                         shadow_run.log) are still kept under archive_runs/.
  --no-clean             Skip the /tmp/monero-*/ cleanup. The raw daemon
                         data directories (blockchain LMDB, monerod config,
                         and — with --no-archive also — bitmonero.log files)
                         remain in /tmp for you to inspect by hand. Can
                         occupy tens of GB; remember to clean up manually
                         when you're done.
  --help                 Show help

Examples:
  ./run_sim.sh --config test_configs/quickstart.yaml
  ./run_sim.sh --config test_configs/quickstart.yaml --name scaling_1000 --analyze
  ./run_sim.sh --config test_configs/quickstart.yaml --archive-blockchain 50
  ./run_sim.sh --config large.yaml --data-dir /scratch/shadow_data
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
        --reachable)
            REACHABLE="$2"
            shift 2
            ;;
        --turnover-session)
            TURNOVER_SESSION="$2"
            shift 2
            ;;
        --turnover-downtime)
            TURNOVER_DOWNTIME="$2"
            shift 2
            ;;
        --turnover-max-session)
            TURNOVER_MAX_SESSION="$2"
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
        --preflight-only)
            PREFLIGHT_ONLY=true
            shift
            ;;
        --no-archive)
            NO_ARCHIVE=true
            shift
            ;;
        --no-clean)
            NO_CLEAN=true
            shift
            ;;
        --archive-blockchain)
            BLOCKCHAIN_ARCHIVE_PCT="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --ramdisk)
            # Optional value: if next arg is a size (digits + optional G/M/K)
            # consume it; otherwise auto-size.
            if [[ -n "${2:-}" && "$2" =~ ^[0-9]+[GMK]?$ ]]; then
                RAMDISK_REQUEST="$2"
                shift 2
            else
                RAMDISK_REQUEST="auto"
                shift
            fi
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
[[ -z "$ARCHIVE_BASE" ]] && ARCHIVE_BASE="$SCRIPT_DIR/archived_runs"
if [[ -z "$RUN_NAME" ]]; then
    # Derive from config filename: test_configs/20260305.yaml -> 20260305
    RUN_NAME=$(basename "$CONFIG" .yaml)
fi

[[ -z "$DATA_DIR" ]] && DATA_DIR="$SCRIPT_DIR/shadow.data"

SHADOW_BIN="$HOME/.monerosim/bin/shadow"
MONEROSIM_BIN="$SCRIPT_DIR/target/release/monerosim"
SHADOW_OUTPUT="$SCRIPT_DIR/shadow_output"
SHARED_DIR="/tmp/monerosim_shared"

# ============================================================
# Utility functions
# ============================================================
# log_step/log_ok/log_warn/log_err/log_info now come from scripts/log_lib.sh

# Convert duration strings like "2.5h", "90m", "6h30m", or raw seconds to seconds
# mirrored at scripts/scaling_test.sh:parse_duration_to_seconds — keep in sync
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
# Ramdisk (tmpfs) helpers
# ============================================================
# We mount tmpfs on a dedicated subdirectory rather than over /tmp itself,
# so we don't hide existing /tmp contents from other processes.
RAMDISK_PARENT="/tmp"

# Sweep stale ramdisks left by prior crashed runs. A ramdisk is "orphaned"
# if no process has any file open on it. Lazy unmount + rmdir on orphans.
sweep_orphan_ramdisks() {
    local found=0
    for d in "$RAMDISK_PARENT"/monerosim_ramdisk_*; do
        [[ -d "$d" ]] || continue
        # Still mounted?
        if mountpoint -q "$d" 2>/dev/null; then
            # Anyone using it?
            if [[ -z "$(lsof +D "$d" 2>/dev/null | tail -n +2)" ]]; then
                log_warn "Cleaning stale ramdisk: $d"
                sudo umount -l "$d" 2>/dev/null || true
                rmdir "$d" 2>/dev/null || true
                found=$((found + 1))
            fi
        else
            # Empty unmounted leftover dir
            rmdir "$d" 2>/dev/null || true
        fi
    done
    if [[ $found -gt 0 ]]; then
        log_info "Cleaned up $found stale ramdisk mount(s)."
    fi
}

# Estimate ramdisk size (MB) needed for monerod LMDBs over the sim duration.
# Per-host: 100 MB base + 10 MB per simulated hour. Min 2 GB total.
# LMDB sparse file alloc means actual page-backed RAM grows with chain
# size, not the apparent file size — these per-host numbers are empirical
# from inspecting du output on running sims.
estimate_ramdisk_mb() {
    local total_monerods=$((CFG_MINERS + CFG_USERS + CFG_RELAYS + CFG_FALLBACK_SEEDS))
    local sim_hours
    sim_hours=$(python3 -c "print(max(1, ${STOP_TIME_SECS:-0} / 3600))")
    python3 scripts/run_sim_helpers.py estimate-ramdisk-mb \
        --total-monerods "$total_monerods" --sim-hours "$sim_hours"
}

# Convert a size argument (e.g. 8G, 4096M, 2048) to MB for the mount call.
size_to_mb() {
    local s="$1"
    case "$s" in
        *G) echo $(( ${s%G} * 1024 )) ;;
        *M) echo "${s%M}" ;;
        *K) echo $(( ${s%K} / 1024 )) ;;
        *)  echo "$s" ;;  # assume already MB
    esac
}

# Mount tmpfs at /tmp/monerosim_ramdisk_<pid>/. Sets RAMDISK_PATH on success.
# Aborts the script on failure.
mount_ramdisk() {
    local request="$1"  # "auto" or explicit (8G, 4096M, etc.)
    local size_mb

    if [[ "$request" == "auto" ]]; then
        size_mb=$(estimate_ramdisk_mb)
        log_info "Auto-sized ramdisk: $(format_kb $((size_mb * 1024))) (estimate)"
    else
        size_mb=$(size_to_mb "$request")
        log_info "Requested ramdisk size: $(format_kb $((size_mb * 1024))) (--ramdisk $request)"
    fi

    # RAM availability check: refuse if estimate > 70% of MemAvailable
    local mem_avail_kb
    mem_avail_kb=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
    local mem_avail_mb=$((mem_avail_kb / 1024))
    local mem_pct=$((size_mb * 100 / mem_avail_mb))
    log_info "Available RAM: $(format_kb "$mem_avail_kb") (ramdisk would consume ${mem_pct}%)"

    if [[ "$mem_pct" -ge 70 ]]; then
        log_err "Refusing to mount ramdisk: ${size_mb} MB exceeds 70% of available RAM (${mem_avail_mb} MB)."
        log_info "Either skip --ramdisk, or pass an explicit smaller size (--ramdisk ${mem_avail_mb}M would be ~100%)."
        exit 1
    elif [[ "$mem_pct" -ge 50 ]]; then
        log_warn "Ramdisk would consume ${mem_pct}% of available RAM. Sim may swap if other processes need memory."
    fi

    RAMDISK_PATH="$RAMDISK_PARENT/monerosim_ramdisk_$$"
    mkdir -p "$RAMDISK_PATH"

    log_info "Mounting tmpfs at $RAMDISK_PATH (${size_mb} MB)..."
    if ! sudo mount -t tmpfs -o "size=${size_mb}M,uid=$(id -u),gid=$(id -g),mode=0755" tmpfs "$RAMDISK_PATH"; then
        log_err "Failed to mount tmpfs. Check sudo permissions."
        rmdir "$RAMDISK_PATH" 2>/dev/null || true
        RAMDISK_PATH=""
        exit 1
    fi

    RAMDISK_MOUNTED=true
    log_ok "Ramdisk mounted: $RAMDISK_PATH"
}

# Pre-shadow trap path: if we abort before shadow is launched, unmount cleanly.
# Once the watchdog is running it owns cleanup, so this is a no-op.
cleanup_ramdisk_pre_shadow() {
    if [[ "$RAMDISK_MOUNTED" == true && -n "$RAMDISK_PATH" ]]; then
        log_warn "Aborting before shadow launch — cleaning up ramdisk $RAMDISK_PATH"
        sudo umount -l "$RAMDISK_PATH" 2>/dev/null || true
        rmdir "$RAMDISK_PATH" 2>/dev/null || true
    fi
}

# Detached watchdog: waits for SHADOW_PID to exit (regardless of why
# run_sim.sh ends), then unmounts the ramdisk and rmdirs the mount point.
# Survives Ctrl-C of run_sim.sh because shadow is in its own setsid session.
start_ramdisk_watchdog() {
    local shadow_pid="$1"
    local path="$2"
    setsid bash -c "
        while kill -0 $shadow_pid 2>/dev/null; do sleep 5; done
        sleep 2  # let any final fsync settle
        sudo umount -l '$path' 2>/dev/null
        rmdir '$path' 2>/dev/null
    " </dev/null >/dev/null 2>&1 &
    disown
    # Watchdog now owns cleanup; the pre-shadow trap path becomes a no-op.
    RAMDISK_MOUNTED=false
    log_ok "Ramdisk watchdog detached (cleanup will fire when shadow PID $shadow_pid exits)"
}

# Top-level orchestrator: mount the ramdisk and rewrite CONFIG so that
# general.daemon_data_dir points at it. Run after preflight_checks (so
# CFG_* and STOP_TIME_SECS are populated) and before build_and_generate
# (so monerosim sees the override).
setup_ramdisk() {
    [[ -z "$RAMDISK_REQUEST" ]] && return  # not requested

    log_step "Setting up tmpfs ramdisk for monerod data"

    # Register pre-shadow trap BEFORE mounting so a signal between mount
    # success and trap setup can't leak the mount. cleanup_ramdisk_pre_shadow
    # checks RAMDISK_MOUNTED, which is only set true after mount succeeds,
    # so it's a no-op until mount completes.
    trap 'cleanup_ramdisk_pre_shadow' EXIT INT TERM

    mount_ramdisk "$RAMDISK_REQUEST"
    # Now $RAMDISK_PATH is set and RAMDISK_MOUNTED=true.

    # Rewrite CONFIG so monerosim emits args pointing daemon data dirs at
    # the ramdisk. Original CONFIG content is preserved verbatim except
    # for general.daemon_data_dir.
    local effective_config="/tmp/monerosim_ramdisk_$$_config.yaml"
    python3 scripts/run_sim_helpers.py rewrite-daemon-data-dir \
        --config "$CONFIG" \
        --daemon-data-dir "$RAMDISK_PATH" \
        --dest "$effective_config" \
        || { log_err "Failed to rewrite config with ramdisk override"; exit 1; }

    CONFIG="$effective_config"
    log_ok "Config rewritten with daemon_data_dir=$RAMDISK_PATH"
    log_info "Effective config: $CONFIG"
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
    STOP_TIME_RAW=$(python3 scripts/run_sim_helpers.py extract-stop-time "$CONFIG" 2>/dev/null)

    if [[ -z "$STOP_TIME_RAW" ]]; then
        log_err "Could not parse stop_time from config"
        exit 1
    fi

    STOP_TIME_SECS=$(parse_duration_to_seconds "$STOP_TIME_RAW")
    log_ok "Simulation duration: $STOP_TIME_RAW ($STOP_TIME_SECS seconds)"

    # Parse agent counts from config metadata or agent list
    # fallback_seeds: monero-seed-NNN hosts the orchestrator injects to
    # populate Monero's hardcoded fallback IPs so peer discovery works.
    # `auto` (default) -> 6 seeds, not in the agents: map.
    # `custom` -> seeds declared explicitly under agents:.
    # `off` -> 0 seeds.
    CONFIG_SUMMARY=$(python3 scripts/run_sim_helpers.py config-summary "$CONFIG" 2>/dev/null)

    read -r CFG_TOTAL CFG_MINERS CFG_USERS CFG_RELAYS CFG_FALLBACK_SEEDS <<< "$CONFIG_SUMMARY"
    log_ok "Agents: ${CFG_TOTAL} total (${CFG_MINERS} miners, ${CFG_USERS} users, ${CFG_RELAYS} relays, ${CFG_FALLBACK_SEEDS} fallback seeds)"

    # Disk space check
    check_disk_space "$ARCHIVE_BASE"
}

check_disk_space() {
    local archive_dir="$1"

    # Create dirs if needed (for df check)
    mkdir -p "$archive_dir"
    mkdir -p "$(dirname "$DATA_DIR")"

    # Check free space on the DATA_DIR filesystem (where shadow.data goes)
    local data_parent
    data_parent="$(dirname "$DATA_DIR")"
    local free_kb
    free_kb=$(df -k "$data_parent" | tail -1 | awk '{print $4}')

    # Check if data dir and archive dir are on different filesystems
    local data_dev archive_dev
    data_dev=$(df "$data_parent" | tail -1 | awk '{print $1}')
    archive_dev=$(df "$archive_dir" | tail -1 | awk '{print $1}')
    local archive_free_kb
    archive_free_kb=$(df -k "$archive_dir" | tail -1 | awk '{print $4}')

    # Estimate disk usage using per-node-type rates from previous runs,
    # falling back to defaults if no history exists.
    local num_miners="${CFG_MINERS:-0}"
    local num_users="${CFG_USERS:-0}"
    local num_relays="${CFG_RELAYS:-0}"
    # CFG_TOTAL excludes fallback seeds (they're injected daemon-only hosts);
    # include them in the host count so the estimator counts their disk usage.
    local num_hosts=$((${CFG_TOTAL:-0} + ${CFG_FALLBACK_SEEDS:-0}))
    local sim_hours
    sim_hours=$(python3 -c "print(max(1, ${STOP_TIME_SECS:-0} / 3600))")

    local estimated_mb
    estimated_mb=$(python3 scripts/run_sim_helpers.py estimate-disk-mb \
        --archive-dir "$archive_dir" \
        --num-miners "$num_miners" \
        --num-users "$num_users" \
        --num-relays "$num_relays" \
        --num-hosts "$num_hosts" \
        --sim-hours "$sim_hours" \
        2>/tmp/monerosim_disk_est_info.txt)

    # Read rate info
    local rate_info=""
    if [[ -f /tmp/monerosim_disk_est_info.txt ]]; then
        rate_info=$(cat /tmp/monerosim_disk_est_info.txt)
        rm -f /tmp/monerosim_disk_est_info.txt
    fi
    local source="default estimates"
    if [[ "$rate_info" == *"learned from previous run"* ]]; then
        source="learned from previous run"
    fi

    local estimated_kb=$((estimated_mb * 1024))

    log_info "Estimated disk usage: $(format_kb "$estimated_kb") ($source)"
    log_info "  ${CFG_MINERS} miners, ${CFG_USERS} users, ${CFG_RELAYS} relays x ${sim_hours}h"
    log_info "Free disk space: $(format_kb "$free_kb") (on $(dirname "$DATA_DIR"))"
    if [[ "$data_dev" != "$archive_dev" ]]; then
        log_info "Archive disk space: $(format_kb "$archive_free_kb") (on $archive_dir)"
    fi

    if [[ "$estimated_kb" -gt "$free_kb" ]]; then
        echo ""
        log_warn "Not enough disk space for this simulation!"
        log_info "  Estimated: $(format_kb "$estimated_kb")"
        log_info "  Available: $(format_kb "$free_kb")"
        log_info "  Shortfall: $(format_kb "$((estimated_kb - free_kb))")"
        echo ""
        echo "  Tips:"
        echo "    - Delete old runs: rm -rf archived_runs/<run_name>"
        echo "    - Reduce simulation duration (stop_time)"
        echo "    - Reduce node count (fewer relays)"
        echo "    - Use --data-dir to write to a different volume"
        echo ""
        if [[ -d "$archive_dir" ]]; then
            echo "  Existing archived runs (by size):"
            du -sh "$archive_dir"/*/ 2>/dev/null | sort -rh | head -10 | while read -r line; do
                echo "    $line"
            done
            echo ""
        fi
        read -rp "  Continue anyway? (yes/no): " CONFIRM
        if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
            echo "Aborted."
            exit 1
        fi
    elif [[ "$((estimated_kb * 2))" -gt "$free_kb" ]]; then
        log_warn "Disk space is tight (estimated $(format_kb "$estimated_kb"), free $(format_kb "$free_kb"))"
    else
        log_ok "Disk space: $(format_kb "$free_kb") free (estimated need: $(format_kb "$estimated_kb"))"
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
        # Ensure cargo is on PATH. setup.sh sources ~/.cargo/env in its own
        # shell, but those modifications don't propagate to a parent shell
        # that hasn't re-read .bashrc — so a fresh-install user who runs
        # ./setup.sh then ./run_sim.sh in the same SSH session would hit
        # `cargo: command not found` here. rustup-installed cargo lives at
        # ~/.cargo/bin/cargo via ~/.cargo/env.
        if ! command -v cargo &> /dev/null && [[ -f "$HOME/.cargo/env" ]]; then
            # shellcheck source=/dev/null
            source "$HOME/.cargo/env"
        fi

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
    REACHABLE_ARGS=()
    if [[ -n "$REACHABLE" ]]; then
        REACHABLE_ARGS=(--reachable "$REACHABLE")
        log_info "Reachability override: --reachable $REACHABLE"
    fi
    TURNOVER_ARGS=()
    [[ -n "$TURNOVER_SESSION" ]] && TURNOVER_ARGS+=(--turnover-session "$TURNOVER_SESSION")
    [[ -n "$TURNOVER_DOWNTIME" ]] && TURNOVER_ARGS+=(--turnover-downtime "$TURNOVER_DOWNTIME")
    [[ -n "$TURNOVER_MAX_SESSION" ]] && TURNOVER_ARGS+=(--turnover-max-session "$TURNOVER_MAX_SESSION")
    [[ ${#TURNOVER_ARGS[@]} -gt 0 ]] && log_info "Turnover override: ${TURNOVER_ARGS[*]}"
    if "$MONEROSIM_BIN" --config "$CONFIG" --output "$SHADOW_OUTPUT" "${REACHABLE_ARGS[@]}" "${TURNOVER_ARGS[@]}" > "$ARCHIVE_DIR/monerosim.log" 2>&1; then
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

    # Clean old simulation data.
    # Safety guard: refuse to recursively delete $DATA_DIR unless it lives
    # under the project tree ($SCRIPT_DIR) or under /tmp. A user who passes
    # --data-dir /scratch/foo might be pointing us at a real directory of
    # theirs; we shouldn't silently wipe it without intent. The same path
    # gets archived intact by archive_results() at end-of-run, so a real
    # workflow should already be safe; this guard catches typos.
    log_info "Cleaning previous simulation data..."
    if [[ -d "$DATA_DIR" ]]; then
        data_abs="$(readlink -f "$DATA_DIR")"
        script_abs="$(readlink -f "$SCRIPT_DIR")"
        if [[ "$data_abs" != "$script_abs"/* && "$data_abs" != /tmp/* ]]; then
            log_err "Refusing to 'rm -rf' $DATA_DIR — path is outside the"
            log_err "project tree ($SCRIPT_DIR) and outside /tmp."
            log_err "If you really want to delete it, remove it manually"
            log_err "before re-running, or pick a --data-dir inside the"
            log_err "project tree or /tmp."
            exit 1
        fi
    fi
    rm -rf "$DATA_DIR" shadow.log

    # Start Shadow in its own process group (via setsid) so Ctrl+C won't reach it
    SHADOW_LOG="$ARCHIVE_DIR/shadow_run.log"
    log_info "Starting Shadow (data dir: $DATA_DIR)..."
    setsid "$SHADOW_BIN" -d "$DATA_DIR" "$SHADOW_OUTPUT/shadow_agents.yaml" > "$SHADOW_LOG" 2>&1 &
    SHADOW_PID=$!
    START_TIME=$(date +%s)
    START_TIME_FMT=$(date '+%Y-%m-%d %H:%M:%S')

    log_ok "Shadow started (PID: $SHADOW_PID)"
    log_ok "Log: $SHADOW_LOG"

    # If we mounted a ramdisk, hand cleanup off to the detached watchdog
    # so it survives Ctrl-C of run_sim.sh while shadow keeps running.
    if [[ -n "$RAMDISK_PATH" ]]; then
        start_ramdisk_watchdog "$SHADOW_PID" "$RAMDISK_PATH"
    fi

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
        local other=$((CFG_TOTAL - CFG_MINERS - CFG_USERS - CFG_RELAYS))
        local config_detail="${CFG_MINERS} miners, ${CFG_USERS} users"
        [[ $CFG_RELAYS -gt 0 ]] && config_detail+=", ${CFG_RELAYS} relays"
        [[ $other -gt 0 ]] && config_detail+=", ${other} support"
        output+="Config:     ${CFG_TOTAL} agents (${config_detail})\n"; lines=$((lines + 1))
        output+="Started:    ${START_TIME_FMT}\n"; lines=$((lines + 1))
        output+="\n"; lines=$((lines + 1))

        # Progress calculation
        local sim_timestamp=""
        local sim_elapsed_secs=0
        local progress_pct=0

        # Extract simulated time from Shadow's progress lines
        # Format: "Progress: 1% — simulated: 00:10:50.014/16:00:00, realtime: ..."
        # Progress lines are emitted ~every wall second, so the latest one is
        # always near the end of the file. Read a small tail and grow if the
        # tail somehow didn't contain a Progress line (e.g. during early
        # bootstrap or after a long stall). Avoids the O(filesize) cost of
        # `tac` on multi-tens-of-MB shadow.logs.
        for tail_kb in 64 256 1024 4096; do
            sim_timestamp=$(tail -c $((tail_kb * 1024)) "$shadow_log" 2>/dev/null \
                | grep -oP '(?<=simulated: )\d{2}:\d{2}:\d{2}' | tail -1 || true)
            [[ -n "$sim_timestamp" ]] && break
        done

        if [[ -n "$sim_timestamp" ]]; then
            sim_elapsed_secs=$(python3 scripts/run_sim_helpers.py hms-to-seconds "$sim_timestamp" 2>/dev/null || echo 0)

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

        local stop_dur_fmt
        stop_dur_fmt=$(format_duration "$STOP_TIME_SECS")

        if [[ -z "$sim_timestamp" ]]; then
            output+="Progress:   [${bar}] Starting...  (waiting for first update)\n"; lines=$((lines + 1))
        else
            local sim_dur_fmt
            sim_dur_fmt=$(format_duration "$sim_elapsed_secs")
            output+="Progress:   [${bar}] ${progress_pct}%  (${sim_dur_fmt} / ${stop_dur_fmt})\n"; lines=$((lines + 1))
        fi

        if [[ -n "$sim_timestamp" ]]; then
            output+="Sim time:   ${sim_timestamp}\n"; lines=$((lines + 1))
        fi
        output+="Stop at:    ${stop_dur_fmt} sim (configured stop_time: ${STOP_TIME_RAW})\n"; lines=$((lines + 1))

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

        local total_expected=$((CFG_MINERS + CFG_USERS + CFG_RELAYS + CFG_FALLBACK_SEEDS))
        output+="Nodes:      ${nodes_online}/${total_expected} online"; lines=$((lines + 1))

        if [[ ${#deltas[@]} -gt 0 ]]; then
            output+="  |  ${nodes_syncing} grew chain in last ${MONITOR_INTERVAL}s\n"

            # Compute stats on deltas (helper expects comma-separated --deltas).
            # Use --deltas=... so a leading negative value (rare LMDB shrink)
            # isn't parsed as a flag.
            local stats
            local deltas_csv
            deltas_csv=$(IFS=,; echo "${deltas[*]}")
            stats=$(python3 scripts/run_sim_helpers.py chain-growth-stats \
                "--deltas=$deltas_csv" 2>/dev/null || echo "")

            if [[ -n "$stats" ]]; then
                output+="Chain growth (${MONITOR_INTERVAL}s): ${stats}\n"; lines=$((lines + 1))
            fi
        else
            output+="\n"
        fi

        # Block-rate status board: parse miner-001's bitmonero.log tail and
        # surface the live block height, rolling rate, time since the last
        # block, and a run-cumulative interval histogram. Cheap (tail-only
        # reads + small JSON state file inside shadow.data/).
        local miner_log="/tmp/monero-miner-001/bitmonero.log"
        if [[ -f "$miner_log" ]]; then
            local LAST_HEIGHT="" LAST_BLOCK_AGO_SEC=""
            local RECENT_RATE_PER_MIN="" RECENT_MIN_PER_BLOCK=""
            local RECENT_RATE_WINDOW_SEC="" RECENT_RATE_BLOCKS=""
            local HISTOGRAM="" HISTOGRAM_AXIS="" HISTOGRAM_TOTAL=""
            local HISTOGRAM_RECENT="" HISTOGRAM_RECENT_N="" HISTOGRAM_RECENT_WINDOW=""
            local block_state="$DATA_DIR/block_histogram_state.json"
            eval "$(python3 scripts/run_sim_helpers.py block-rate \
                --log "$miner_log" \
                --state-file "$block_state" 2>/dev/null || true)"
            if [[ -n "$LAST_HEIGHT" ]]; then
                output+="Chain tip:  height ${LAST_HEIGHT}"
                if [[ -n "$RECENT_MIN_PER_BLOCK" ]]; then
                    output+="  |  recent: ${RECENT_MIN_PER_BLOCK} min/block over $((RECENT_RATE_WINDOW_SEC / 60))m (${RECENT_RATE_BLOCKS} blocks, target 2 min/block)"
                fi
                output+="\n"; lines=$((lines + 1))
                if [[ -n "$LAST_BLOCK_AGO_SEC" ]]; then
                    if [[ $LAST_BLOCK_AGO_SEC -ge 300 ]]; then
                        output+="${YELLOW}Last block: ${LAST_BLOCK_AGO_SEC}s sim ago${NC}\n"
                    else
                        output+="Last block: ${LAST_BLOCK_AGO_SEC}s sim ago\n"
                    fi
                    lines=$((lines + 1))
                fi
                if [[ -n "$HISTOGRAM" ]]; then
                    output+="Block-interval histogram  ${DIM}(cell = 15s sim; cell value: 0=empty, 1-9 literal, a-g=10-16, ^=17+)${NC}\n"; lines=$((lines + 1))
                    output+="   ${DIM}min:${NC}  ${DIM}${HISTOGRAM_AXIS}${NC}\n"; lines=$((lines + 1))
                    output+="   ${DIM}all:${NC}  ${HISTOGRAM}  ${DIM}(${HISTOGRAM_TOTAL} blocks)${NC}\n"; lines=$((lines + 1))
                    if [[ -n "$HISTOGRAM_RECENT" && "$HISTOGRAM_RECENT_N" -gt 0 ]]; then
                        output+="  ${DIM}last:${NC}  ${HISTOGRAM_RECENT}  ${DIM}(last ${HISTOGRAM_RECENT_N} of ${HISTOGRAM_RECENT_WINDOW})${NC}\n"; lines=$((lines + 1))
                    fi
                fi
            fi
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
    if [[ -d "$DATA_DIR" ]]; then
        log_info "Moving $DATA_DIR to archive..."
        mv "$DATA_DIR" "$ARCHIVE_DIR/shadow.data/"
        log_ok "shadow.data archived"
    else
        log_warn "$DATA_DIR not found"
    fi

    # Copy monitoring data (generated by simulation-monitor agent)
    local monitor_dir="$SHARED_DIR/monitoring"
    if [[ -d "$monitor_dir" ]]; then
        cp -r "$monitor_dir" "$ARCHIVE_DIR/monitoring"
        log_ok "Monitoring data archived (final_report.json, historical_data.json)"
    fi
    local monitor_log
    monitor_log=$(find "$SHARED_DIR" -maxdepth 1 -name 'monerosim_monitor.log' 2>/dev/null | head -1)
    if [[ -n "$monitor_log" && -f "$monitor_log" ]]; then
        cp "$monitor_log" "$ARCHIVE_DIR/monerosim_monitor.log"
        log_ok "monerosim_monitor.log archived"
    fi

    # Each step is guarded so a failure in one doesn't skip the rest
    archive_blockchain_snapshots  || log_warn "Blockchain snapshot archiving failed"
    archive_daemon_logs           || log_warn "Daemon log archiving failed"
    archive_transaction_registry  || log_warn "Transaction registry archiving failed"
    generate_summary_report       || log_warn "Summary report generation failed"

    if [[ "$RUN_ANALYZE" == true ]]; then
        run_analysis || log_warn "Post-simulation analysis failed"
    fi
}

generate_summary_report() {
    local report_file="$SHARED_DIR/monitoring/final_report.json"
    local report_out="$ARCHIVE_DIR/summary.txt"

    if [[ ! -f "$report_file" ]]; then
        log_warn "No final_report.json found, skipping summary report"
        return
    fi

    python3 scripts/run_sim_helpers.py write-summary-report \
        --report "$report_file" \
        --out "$report_out" \
        --run-name "$RUN_NAME" \
        --wall-time "$(format_duration "$WALL_DURATION")" \
        --exit-code "$SHADOW_EXIT" \
        2>/dev/null

    if [[ -f "$report_out" ]]; then
        # Append the full block-time analysis (mean/median/stdev + histogram)
        # to summary.txt. block_time_analysis.py drops ANSI escapes when
        # stdout isn't a TTY, so the file stays clean.
        {
            echo ""
            echo "============================================================"
            echo "BLOCK PRODUCTION"
            echo "============================================================"
            python3 "$SCRIPT_DIR/scripts/block_time_analysis.py" "$ARCHIVE_DIR" \
                2>/dev/null
        } >> "$report_out"
        log_ok "Summary report: $report_out"
    else
        log_warn "Failed to generate summary report"
    fi
}

archive_blockchain_snapshots() {
    log_info "Archiving blockchain snapshots..."

    local shadow_agents="$ARCHIVE_DIR/shadow_agents.yaml"
    if [[ ! -f "$shadow_agents" ]]; then
        log_warn "shadow_agents.yaml not found, skipping blockchain snapshots"
        return
    fi

    # Extract all data-dir paths
    local all_dirs
    all_dirs=$(grep -oP 'data-dir=\K/tmp/monero-[^ "]+' "$shadow_agents" 2>/dev/null | sort -u || true)
    local total
    total=$(echo "$all_dirs" | grep -c . || true)

    if [[ $total -eq 0 ]]; then
        log_warn "No blockchain data directories found"
        return
    fi

    if [[ -n "$BLOCKCHAIN_ARCHIVE_PCT" ]]; then
        # Percentage mode: archive N% of all blockchains
        local pct=$BLOCKCHAIN_ARCHIVE_PCT
        local count=$(python3 -c "import math; print(max(1, math.ceil($total * $pct / 100)))")
        log_info "Archiving $count of $total blockchains (${pct}%)"

        # Select evenly: take every Nth node to get a representative sample
        echo "$all_dirs" | shuf --random-source=<(echo "$STOP_TIME_SECS") 2>/dev/null | head -"$count" | sort | while read -r data_dir; do
            [[ -n "$data_dir" ]] && copy_blockchain_snapshot "$data_dir"
        done
    else
        # Default: 1 per type (miner, user, relay)
        local miner_dirs user_dirs relay_dirs
        miner_dirs=$(echo "$all_dirs" | grep '/monero-miner-' || true)
        user_dirs=$(echo "$all_dirs" | grep '/monero-user-' || true)
        relay_dirs=$(echo "$all_dirs" | grep '/monero-relay-' || true)

        [[ -n "$miner_dirs" ]] && copy_blockchain_snapshot "$(echo "$miner_dirs" | head -1)"
        [[ -n "$user_dirs" ]] && copy_blockchain_snapshot "$(echo "$user_dirs" | shuf 2>/dev/null | head -1)"
        [[ -n "$relay_dirs" ]] && copy_blockchain_snapshot "$(echo "$relay_dirs" | shuf 2>/dev/null | head -1)"
    fi

    return 0
}

copy_blockchain_snapshot() {
    local data_dir="$1"

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
        log_warn "No blockchain data for $node_name at $lmdb_dir"
    fi
}

cleanup_tmp_monero() {
    # Always-safe cleanup: removes /tmp/monero-*/ leftovers regardless of
    # whether the archive step ran. Called from archive_daemon_logs() in the
    # normal path, and standalone from main() in the --no-archive path.
    # Skipped entirely with --no-clean so users can dig through raw data.
    if [[ "$NO_CLEAN" == true ]]; then
        local tmp_size
        tmp_size=$(du -shc /tmp/monero-* 2>/dev/null | tail -1 | cut -f1)
        log_warn "Skipping /tmp/monero-*/ cleanup (--no-clean). "
        log_warn "${tmp_size:-?} left in /tmp/monero-*/ for inspection."
        log_warn "Remember to 'rm -rf /tmp/monero-*' when you're done."
        return
    fi
    log_info "Cleaning up /tmp/monero-*/ leftovers..."
    local tmp_size
    tmp_size=$(du -shc /tmp/monero-* 2>/dev/null | tail -1 | cut -f1)
    rm -rf /tmp/monero-* 2>/dev/null || true
    log_ok "Freed ~${tmp_size:-0} from /tmp/monero-*/"
}

archive_daemon_logs() {
    log_info "Archiving daemon logs (bitmonero.log)..."

    local logs_dir="$ARCHIVE_DIR/daemon_logs"
    mkdir -p "$logs_dir"

    local count=0
    for log_file in /tmp/monero-*/bitmonero.log; do
        [[ -f "$log_file" ]] || continue
        local node_dir
        node_dir=$(dirname "$log_file")
        local node_name
        node_name=$(basename "$node_dir")
        mkdir -p "$logs_dir/$node_name"
        # mv is free within the same filesystem and avoids the 2x disk-space
        # requirement that cp creates. Falls back to copy-then-unlink if the
        # destination is on a different filesystem.
        mv "$log_file" "$logs_dir/$node_name/"
        count=$((count + 1))
    done

    if [[ $count -gt 0 ]]; then
        local total_size
        total_size=$(du -sh "$logs_dir" 2>/dev/null | cut -f1)
        log_ok "Daemon logs: $count bitmonero.log files archived ($total_size total)"
    else
        log_warn "No bitmonero.log files found in /tmp/monero-*/"
    fi

    # Clean up the leftover /tmp/monero-*/ directories (blockchain DBs, config,
    # lock files, etc. — everything that isn't bitmonero.log, which we moved
    # above). Can run into tens of GB on a 1000-node sim. Skipped under
    # --no-clean.
    cleanup_tmp_monero
}

archive_transaction_registry() {
    log_info "Archiving transaction registry..."

    local tx_dir="$ARCHIVE_DIR/transaction_registry"
    mkdir -p "$tx_dir"

    # Registry JSON (+ lock) files go into transaction_registry/.
    local count=0
    for f in "$SHARED_DIR"/*.json "$SHARED_DIR"/*.lock; do
        [[ -f "$f" ]] || continue
        mv "$f" "$tx_dir/"
        count=$((count + 1))
    done

    if [[ $count -gt 0 ]]; then
        log_ok "Transaction registry: $count files archived"
    else
        log_warn "No registry files found in $SHARED_DIR"
    fi

    # Per-agent wallet state (keys, balance, tx history) and ringdb state.
    # Useful for post-run forensics (spin up wallet-rpc against the archived
    # wallet + a preserved daemon, query balances, etc.).
    local wallets_dir="$ARCHIVE_DIR/wallets"
    local ringdbs_dir="$ARCHIVE_DIR/ringdbs"
    local wallet_count=0 ringdb_count=0
    for d in "$SHARED_DIR"/*_wallet; do
        [[ -d "$d" ]] || continue
        mkdir -p "$wallets_dir"
        mv "$d" "$wallets_dir/"
        wallet_count=$((wallet_count + 1))
    done
    for d in "$SHARED_DIR"/*_ringdb; do
        [[ -d "$d" ]] || continue
        mkdir -p "$ringdbs_dir"
        mv "$d" "$ringdbs_dir/"
        ringdb_count=$((ringdb_count + 1))
    done
    if [[ $wallet_count -gt 0 || $ringdb_count -gt 0 ]]; then
        log_ok "Wallet state: $wallet_count wallets, $ringdb_count ringdbs archived"
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
        if [[ "$analysis_script" == "$SCRIPT_DIR/scripts/post_run_analysis.sh" ]]; then
            # Pass the config path through so analyze_network_connectivity.py's
            # required --config can be wired up instead of skipped.
            bash "$analysis_script" "$CONFIG" > "$ARCHIVE_DIR/analysis.log" 2>&1 || true
        else
            bash "$analysis_script" > "$ARCHIVE_DIR/analysis.log" 2>&1 || true
        fi
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
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║            Simulation Results                     ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    # --- Run overview ---
    echo -e "  ${BOLD}Run${NC}"
    echo "  Wall time:    $(format_duration $WALL_DURATION)"
    echo "  Exit code:    $SHADOW_EXIT"

    local archive_size
    archive_size=$(du -sh "$ARCHIVE_DIR" 2>/dev/null | cut -f1)
    echo "  Archive:      $ARCHIVE_DIR ($archive_size)"
    echo ""

    # --- Simulation results from monitor final report ---
    local report_file="$SHARED_DIR/monitoring/final_report.json"
    if [[ -f "$report_file" ]]; then
        local sim_results
        sim_results=$(python3 scripts/run_sim_helpers.py print-summary-kv \
            --report "$report_file" 2>/dev/null)

        if [[ -n "$sim_results" ]]; then
            local nodes sync height blocks tx_created tx_in_blocks wallets_funded alerts all_pass
            nodes=$(echo "$sim_results" | grep '^NODES=' | cut -d= -f2)
            sync=$(echo "$sim_results" | grep '^SYNC=' | cut -d= -f2)
            height=$(echo "$sim_results" | grep '^HEIGHT=' | cut -d= -f2)
            blocks=$(echo "$sim_results" | grep '^BLOCKS=' | cut -d= -f2)
            tx_created=$(echo "$sim_results" | grep '^TX_CREATED=' | cut -d= -f2)
            tx_in_blocks=$(echo "$sim_results" | grep '^TX_IN_BLOCKS=' | cut -d= -f2)
            wallets_funded=$(echo "$sim_results" | grep '^WALLETS_FUNDED=' | cut -d= -f2)
            alerts=$(echo "$sim_results" | grep '^ALERTS=' | cut -d= -f2)
            all_pass=$(echo "$sim_results" | grep '^ALL_PASS=' | cut -d= -f2)

            echo -e "  ${BOLD}Network${NC}"
            echo "  Nodes:        $nodes"
            echo "  Sync:         ${sync}%"
            echo "  Block height: $height"
            echo "  Blocks mined: $blocks"
            echo ""

            echo -e "  ${BOLD}Transactions${NC}"
            echo "  Created:      $tx_created"
            echo "  In blocks:    $tx_in_blocks"
            echo "  Wallets funded: $wallets_funded"
            echo ""

            echo -e "  ${BOLD}Health${NC}"
            echo "  Alerts:       $alerts"
            echo ""

            echo -e "  ${BOLD}Success Criteria${NC}"
            echo "$sim_results" | grep '^CRITERIA=' | cut -d= -f2- | while read -r line; do
                if [[ "$line" == *"PASS" ]]; then
                    echo -e "    ${GREEN}$line${NC}"
                else
                    echo -e "    ${YELLOW}$line${NC}"
                fi
            done
            echo ""

            if [[ "$all_pass" == "yes" ]]; then
                echo -e "  ${BOLD}${GREEN}Result: ALL CHECKS PASSED${NC}"
            else
                echo -e "  ${BOLD}${YELLOW}Result: SOME CHECKS FAILED${NC}"
            fi
            echo ""
        fi

        # Block-time analysis (best-effort; never aborts the summary).
        # Reads daemon_logs/monero-miner-001/bitmonero.log from the archive
        # and prints interval stats + a histogram.
        python3 "$SCRIPT_DIR/scripts/block_time_analysis.py" "$ARCHIVE_DIR" \
            2>/dev/null || true
    else
        # No monitor report — fall back to shadow log parsing
        echo -e "  ${DIM}(No simulation monitor report found)${NC}"
        echo ""

        # Try to get basic stats from shadow log
        local final_height
        final_height=$(grep -oP 'height \K\d+' "$SHADOW_LOG" 2>/dev/null | sort -n | tail -1)
        if [[ -n "$final_height" ]]; then
            echo "  Block height: $final_height (from daemon logs)"
            echo ""
        fi
    fi

    # --- Archive details ---
    echo -e "  ${BOLD}Archive${NC}"
    if [[ -d "$ARCHIVE_DIR/daemon_logs" ]]; then
        local log_count logs_size
        log_count=$(find "$ARCHIVE_DIR/daemon_logs" -name 'bitmonero.log' 2>/dev/null | wc -l)
        logs_size=$(du -sh "$ARCHIVE_DIR/daemon_logs" 2>/dev/null | cut -f1)
        echo "  Daemon logs:  $log_count files ($logs_size)"
    fi
    if [[ -d "$ARCHIVE_DIR/blockchain" ]]; then
        local snap_count snap_size
        snap_count=$(find "$ARCHIVE_DIR/blockchain" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        snap_size=$(du -sh "$ARCHIVE_DIR/blockchain" 2>/dev/null | cut -f1)
        echo "  Blockchain:   $snap_count snapshots ($snap_size)"
    fi
    if [[ -d "$ARCHIVE_DIR/transaction_registry" ]]; then
        local tx_file_count
        tx_file_count=$(ls -1 "$ARCHIVE_DIR/transaction_registry/"*.json 2>/dev/null | wc -l)
        echo "  Tx registry:  $tx_file_count files"
    fi

    local free_kb
    free_kb=$(df -k "$ARCHIVE_DIR" | tail -1 | awk '{print $4}')
    echo "  Disk free:    $(format_kb "$free_kb")"
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

    if [[ "$PREFLIGHT_ONLY" == true ]]; then
        # Skip sweep_orphan_ramdisks too — it could unmount a ramdisk used
        # by another in-flight run if its lsof check races.
        preflight_checks
        log_ok "Preflight complete (--preflight-only). Exiting without touching shadow.data, /tmp, or spawning shadow."
        exit 0
    fi

    sweep_orphan_ramdisks
    preflight_checks
    setup_ramdisk
    build_and_generate
    run_simulation
    if [[ "$NO_ARCHIVE" == true ]]; then
        log_step "Phase 5: Archive skipped (--no-archive)"
        log_warn "shadow.data/, daemon bitmonero.log files, blockchain snapshots,"
        log_warn "monitoring data, and summary.txt are NOT being preserved."
        log_warn "Pre-run artifacts (input_config.yaml, shadow_agents.yaml,"
        log_warn "monerosim.log, shadow_run.log, build.log, memory_samples.csv)"
        log_warn "remain in $ARCHIVE_DIR."
        cleanup_tmp_monero  # internally respects --no-clean
    else
        archive_results
    fi
    print_summary
}

main
