#!/bin/bash
# check_sim.sh - Quick status check for a MoneroSim simulation
#
# Usage: ./check_sim.sh [SHADOW_DATA_DIR]
#
# Accepts one of:
#   - Path to a shadow.data/ directory (live or archived)
#   - Path to an archived run directory (containing shadow.data/)
#   - No argument: auto-detect from running Shadow process or CWD
#
# Also reads input_config.yaml (if found) for timeline/phase info,
# and /tmp/monerosim_shared/monitoring/ for live monitoring data.

set -uo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

header() { echo -e "\n${BOLD}${CYAN}=== $1 ===${NC}"; }
ok()     { echo -e "  ${GREEN}$1${NC}"; }
warn()   { echo -e "  ${YELLOW}$1${NC}"; }
err()    { echo -e "  ${RED}$1${NC}"; }
info()   { echo -e "  $1"; }

SIM_EPOCH=946684800  # 2000-01-01 00:00:00 UTC (Shadow epoch)

# ============================================================
# Locate shadow.data/hosts and run directory
# ============================================================
HOSTS_DIR=""
RUN_DIR=""
LOG_SOURCE=""

find_hosts_dir() {
    local candidate="$1"

    # Direct shadow.data/hosts path
    if [ -d "$candidate/hosts" ]; then
        HOSTS_DIR="$candidate/hosts"
        return 0
    fi
    # shadow.data directory
    if [ -d "$candidate/shadow.data/hosts" ]; then
        HOSTS_DIR="$candidate/shadow.data/hosts"
        RUN_DIR="$candidate"
        return 0
    fi
    return 1
}

if [ -n "${1:-}" ]; then
    find_hosts_dir "$1" || { err "No shadow.data/hosts found at $1"; exit 1; }
    LOG_SOURCE="specified"
else
    # Auto-detect: check for running Shadow process
    SHADOW_CWD=""
    SHADOW_PID=$(pgrep -xf ".*/shadow .*\\.yaml" 2>/dev/null | head -1 || true)
    if [ -n "$SHADOW_PID" ]; then
        SHADOW_CWD=$(readlink -f "/proc/$SHADOW_PID/cwd" 2>/dev/null || true)
    fi

    if [ -n "$SHADOW_CWD" ] && [ -d "$SHADOW_CWD/shadow.data/hosts" ]; then
        HOSTS_DIR="$SHADOW_CWD/shadow.data/hosts"
        LOG_SOURCE="live (from running Shadow PID $SHADOW_PID)"
    elif [ -d "./shadow.data/hosts" ]; then
        HOSTS_DIR="./shadow.data/hosts"
        LOG_SOURCE="live (CWD)"
    else
        # Fallback: look for CWD-relative input_config or run dir
        err "Could not find shadow.data/hosts."
        info "Pass a path:  $0 /path/to/shadow.data"
        info "         or:  $0 /path/to/archived_run_dir"
        exit 1
    fi
fi

HOSTS_DIR=$(readlink -f "$HOSTS_DIR")

# Try to find input_config.yaml for timeline info
CONFIG_FILE=""
# Build list of candidate locations
_config_candidates=(
    "$(dirname "$HOSTS_DIR")/../input_config.yaml"       # shadow.data/../input_config.yaml
    "$(dirname "$HOSTS_DIR")/../../input_config.yaml"     # run_dir/input_config.yaml
    "${RUN_DIR:-.}/input_config.yaml"
)
# If we detected a Shadow process, also check near its YAML arg
if [ -n "${SHADOW_PID:-}" ]; then
    _yaml_arg=$(cat "/proc/$SHADOW_PID/cmdline" 2>/dev/null | xargs -0 printf '%s\n' | grep -E '\.yaml$' | head -1 || true)
    if [ -n "$_yaml_arg" ]; then
        _config_candidates+=("$(dirname "$_yaml_arg")/input_config.yaml")
        _config_candidates+=("$(dirname "$(dirname "$_yaml_arg")")/input_config.yaml")
    fi
fi
# Also check the most recent directory in common run-log locations
for _logbase in "$HOME/scale_run_logs" "$HOME/monerosim_runs" "$(dirname "$HOSTS_DIR")/../../.."; do
    if [ -d "$_logbase" ]; then
        _newest=$(ls -td "$_logbase"/*/ 2>/dev/null | head -1)
        if [ -n "$_newest" ]; then
            _config_candidates+=("${_newest}input_config.yaml")
        fi
    fi
done
for candidate in "${_config_candidates[@]}"; do
    if [ -f "$candidate" ]; then
        CONFIG_FILE=$(readlink -f "$candidate")
        break
    fi
done

# Try to find the run directory (for memory_samples.csv etc)
if [ -z "$RUN_DIR" ] && [ -n "$CONFIG_FILE" ]; then
    RUN_DIR=$(dirname "$CONFIG_FILE")
elif [ -z "$RUN_DIR" ]; then
    # Walk up from hosts dir
    candidate=$(dirname "$HOSTS_DIR")  # shadow.data
    candidate=$(dirname "$candidate")  # run dir
    if [ -f "$candidate/input_config.yaml" ]; then
        RUN_DIR="$candidate"
    fi
fi

# ============================================================
# Parse config for timeline milestones (if available)
# ============================================================
# Returns timeline as shell variables: DURATION_H, ACTIVITY_START_H, etc.
TIMELINE_INFO=""
if [ -n "$CONFIG_FILE" ]; then
    TIMELINE_INFO=$(python3 -c "
import yaml, sys
try:
    with open('$CONFIG_FILE') as f:
        cfg = yaml.safe_load(f)
    meta = cfg.get('metadata', {})
    timing = meta.get('timing', {})
    upgrade = meta.get('upgrade', {})
    general = cfg.get('general', {})
    agents_meta = meta.get('agents', {})

    # Duration
    dur_s = timing.get('duration_s', 0)
    if not dur_s:
        stop = general.get('stop_time', '')
        if isinstance(stop, str) and stop.endswith('h'):
            dur_s = float(stop.rstrip('h')) * 3600
    dur_h = dur_s / 3600 if dur_s else 0

    # Activity start
    act_s = timing.get('activity_start_s', 0)
    act_h = act_s / 3600 if act_s else 0

    # Bootstrap end
    boot_s = timing.get('bootstrap_end_s', 0)
    boot_h = boot_s / 3600 if boot_s else 0

    # Upgrade
    upg_start_s = upgrade.get('start_s', 0)
    upg_start_h = upg_start_s / 3600 if upg_start_s else 0
    upg_end_s = upgrade.get('complete_s', 0)
    upg_end_h = upg_end_s / 3600 if upg_end_s else 0

    # Agent counts
    n_miners = agents_meta.get('miners', 0)
    n_users = agents_meta.get('users', 0)
    n_total = agents_meta.get('total', 0)

    # Scenario
    scenario = meta.get('scenario', 'unknown')

    print(f'DURATION_H={dur_h:.1f}')
    print(f'ACTIVITY_START_H={act_h:.1f}')
    print(f'BOOTSTRAP_END_H={boot_h:.1f}')
    print(f'UPGRADE_START_H={upg_start_h:.1f}')
    print(f'UPGRADE_END_H={upg_end_h:.1f}')
    print(f'CFG_MINERS={n_miners}')
    print(f'CFG_USERS={n_users}')
    print(f'CFG_TOTAL={n_total}')
    print(f'SCENARIO={scenario}')
except Exception as e:
    print(f'# config parse error: {e}', file=sys.stderr)
" 2>/dev/null || true)
    eval "$TIMELINE_INFO" 2>/dev/null || true
fi

# ============================================================
# Process Status
# ============================================================
header "Process Status"
if [[ "$LOG_SOURCE" != "specified" ]]; then
    SHADOW_PID=$(pgrep -xf ".*/shadow .*\\.yaml" 2>/dev/null | head -1 || true)
    if [ -n "$SHADOW_PID" ]; then
        ok "Shadow running (PID $SHADOW_PID)"
        ELAPSED=$(ps -o etime= -p "$SHADOW_PID" 2>/dev/null | xargs)
        info "Wall-clock elapsed: ${ELAPSED:-unknown}"
    else
        warn "Shadow not running"
    fi
else
    info "Viewing archived run"
fi
info "Hosts dir: $HOSTS_DIR ($LOG_SOURCE)"
if [ -n "$CONFIG_FILE" ]; then
    info "Config: $CONFIG_FILE"
    if [ -n "${SCENARIO:-}" ]; then
        info "Scenario: $SCENARIO | Config agents: ${CFG_MINERS:-?} miners + ${CFG_USERS:-?} users = ${CFG_TOTAL:-?}"
    fi
fi

# ============================================================
# Simulation Time & Phase
# ============================================================
header "Simulation Time"

# Get sim time from actual agent logs by sampling a few hosts for the latest timestamp.
# We check a miner agent log (most active), then a few user agent logs, and take the max.
SIM_HOURS=""
LATEST_TS=""

_sample_logs=()
# Grab a few miner agent logs
for d in "$HOSTS_DIR"/miner-0*/; do
    [ -d "$d" ] || continue
    for f in "$d"/bash.*.stdout; do
        [ -s "$f" ] && _sample_logs+=("$f") && break
    done
    [ "${#_sample_logs[@]}" -ge 2 ] && break
done
# Grab a couple of user agent logs (first and last alphabetically)
_user_dirs=("$HOSTS_DIR"/user-*/)
if [ "${#_user_dirs[@]}" -gt 0 ]; then
    for _ud in "${_user_dirs[0]}" "${_user_dirs[-1]}"; do
        [ -d "$_ud" ] || continue
        for f in "$_ud"/bash.*.stdout; do
            [ -s "$f" ] && _sample_logs+=("$f") && break
        done
    done
fi

if [ "${#_sample_logs[@]}" -gt 0 ]; then
    # Get the last timestamp from each sample log, then pick the max
    LATEST_TS=$(
        for _sl in "${_sample_logs[@]}"; do
            grep -oP "2000-01-\d+ \d+:\d+:\d+" "$_sl" 2>/dev/null | tail -1
        done | sort | tail -1
    )
fi

if [ -n "$LATEST_TS" ]; then
    SIM_HOURS=$(python3 -c "
from datetime import datetime
dt = datetime.strptime('$LATEST_TS', '%Y-%m-%d %H:%M:%S')
epoch = datetime(2000, 1, 1)
print(f'{(dt - epoch).total_seconds() / 3600:.2f}')
" 2>/dev/null || true)
    info "Sim time: $LATEST_TS (${SIM_HOURS}h)"
else
    warn "No timestamps found in agent logs"
fi

# Phase detection (uses config timeline if available)
if [ -n "$SIM_HOURS" ] && [ -n "$TIMELINE_INFO" ]; then
    PHASE=$(python3 -c "
hours = $SIM_HOURS
dur = ${DURATION_H:-0}
act = ${ACTIVITY_START_H:-0}
boot = ${BOOTSTRAP_END_H:-0}
upg_start = ${UPGRADE_START_H:-0}
upg_end = ${UPGRADE_END_H:-0}

# Build phase list from config milestones
if dur > 0 and hours >= dur:
    print('Simulation complete')
elif upg_end > 0 and hours >= upg_end:
    print('Post-upgrade observation')
elif upg_start > 0 and hours >= upg_start:
    print('UPGRADE IN PROGRESS')
elif act > 0 and hours >= act:
    if upg_start > 0:
        print('User activity (pre-upgrade)')
    else:
        print('User activity')
elif boot > 0 and hours >= boot:
    print('Distributor funding / pre-activity')
elif hours >= 1:
    print('Bootstrap / agents starting')
else:
    print('Initializing')
" 2>/dev/null || echo "unknown")
    info "Phase:      $PHASE"
fi

# ============================================================
# Discover agent types by scanning host directories
# ============================================================
# We identify miners, users, distributor, monitor by checking log content
MINER_DIRS=()
USER_DIRS=()
DIST_DIR=""
MONITOR_DIR=""

for d in "$HOSTS_DIR"/*/; do
    name=$(basename "$d")
    case "$name" in
        miner-0*|miner-1*|miner-2*|miner-3*|miner-4*|miner-5*|miner-6*|miner-7*|miner-8*|miner-9*)
            MINER_DIRS+=("$d") ;;
        miner-distributor*)
            DIST_DIR="$d" ;;
        simulation-monitor*)
            MONITOR_DIR="$d" ;;
        user-*|regular-*|node-*)
            USER_DIRS+=("$d") ;;
        dnsserver*) ;;  # skip
        *)
            # Unknown host type - could be a user or custom agent
            # Check if it has a Python agent log with RegularUser
            for f in "$d"/bash.*.stdout; do
                if grep -q "RegularUserAgent\|regular_user" "$f" 2>/dev/null; then
                    USER_DIRS+=("$d")
                    break
                elif grep -q "AutonomousMiner\|autonomous_miner" "$f" 2>/dev/null; then
                    MINER_DIRS+=("$d")
                    break
                fi
            done
            ;;
    esac
done

NUM_MINERS=${#MINER_DIRS[@]}
NUM_USERS=${#USER_DIRS[@]}

# ============================================================
# Miners
# ============================================================
header "Miners ($NUM_MINERS)"
for miner_dir in "${MINER_DIRS[@]}"; do
    miner=$(basename "$miner_dir")
    # Find the mining agent log by content
    agent_log=""
    for f in "$miner_dir"/bash.*.stdout; do
        if grep -q "New height\|AutonomousMiner" "$f" 2>/dev/null; then
            agent_log="$f"
            break
        fi
    done
    if [ -n "$agent_log" ]; then
        last_height=$(grep -oP "New height: \K\d+" "$agent_log" 2>/dev/null | tail -1)
        if [ -n "$last_height" ]; then
            ok "$miner: height $last_height"
        else
            info "$miner: active (no height yet)"
        fi
    else
        info "$miner: no agent log"
    fi
done

# ============================================================
# Miner Distributor
# ============================================================
header "Miner Distributor"
if [ -n "$DIST_DIR" ] && [ -d "$DIST_DIR" ]; then
    DIST_LOG=""
    for f in "$DIST_DIR"/bash.*.stdout; do
        if [ -s "$f" ] && grep -q "distributor\|MinerDistributor\|Batch\|funding" "$f" 2>/dev/null; then
            DIST_LOG="$f"
            break
        fi
    done
    if [ -n "$DIST_LOG" ]; then
        BATCHES_OK=$(grep -c "Batch transaction sent successfully\|batch.*success" "$DIST_LOG" 2>/dev/null || true)
        BATCHES_FAIL=$(grep -c "Batch.*failed\|Failed to send batch\|real output" "$DIST_LOG" 2>/dev/null || true)
        LAST_TS=$(grep -oP "2000-01-\d+ \d+:\d+:\d+" "$DIST_LOG" 2>/dev/null | tail -1)
        ok "Active (last: ${LAST_TS:-unknown})"
        info "Successful batches: ${BATCHES_OK:-0} | Failed: ${BATCHES_FAIL:-0}"
    else
        warn "Not started yet (no agent log with content)"
    fi
else
    info "No miner-distributor host found"
fi

# ============================================================
# User Transactions
# ============================================================
header "User Transactions ($NUM_USERS users)"
if [ "$NUM_USERS" -gt 0 ]; then
    # Auto-detect the agent log filename by sampling the first user
    FIRST_USER="${USER_DIRS[0]}"
    AGENT_FILE=""
    for f in "$FIRST_USER"/bash.*.stdout; do
        if grep -q "RegularUserAgent\|regular_user\|UserAgent" "$f" 2>/dev/null; then
            AGENT_FILE=$(basename "$f")
            break
        fi
    done

    if [ -z "$AGENT_FILE" ]; then
        warn "Could not identify user agent log file (users may not have started)"
    else
        info "Agent log file: $AGENT_FILE"
        echo ""

        USERS_SENT=$(grep -rl "Sent transaction:" "$HOSTS_DIR"/user-*/"$AGENT_FILE" 2>/dev/null | wc -l)
        USERS_REAL_OUTPUT=$(grep -rl "real output" "$HOSTS_DIR"/user-*/"$AGENT_FILE" 2>/dev/null | wc -l)
        USERS_TIMEOUT=$(grep -rl "Read timed out" "$HOSTS_DIR"/user-*/"$AGENT_FILE" 2>/dev/null | wc -l)
        USERS_RING_SIZE=$(grep -rl "ring size" "$HOSTS_DIR"/user-*/"$AGENT_FILE" 2>/dev/null | wc -l)
        USERS_NOT_ENOUGH=$(grep -rl "not enough.*money" "$HOSTS_DIR"/user-*/"$AGENT_FILE" 2>/dev/null | wc -l)

        if [ "$USERS_SENT" -gt 0 ]; then
            ok "Users who sent >= 1 tx:        $USERS_SENT / $NUM_USERS"
        else
            info "Users who sent >= 1 tx:        $USERS_SENT / $NUM_USERS"
        fi
        [ "$USERS_REAL_OUTPUT" -gt 0 ] && warn "Users with 'real output' err:  $USERS_REAL_OUTPUT"
        [ "$USERS_TIMEOUT" -gt 0 ]     && err  "Users with timeout errors:     $USERS_TIMEOUT"
        [ "$USERS_RING_SIZE" -gt 0 ]   && err  "Users with ring size errors:   $USERS_RING_SIZE"
        [ "$USERS_NOT_ENOUGH" -gt 0 ]  && warn "Users with 'not enough money': $USERS_NOT_ENOUGH"

        TOTAL_SENT=$(grep -rh "Sent transaction:" "$HOSTS_DIR"/user-*/"$AGENT_FILE" 2>/dev/null | wc -l)
        TOTAL_FAILED=$(grep -rh "Failed to send" "$HOSTS_DIR"/user-*/"$AGENT_FILE" 2>/dev/null | wc -l)
        echo ""
        info "Total sent: $TOTAL_SENT | Total failed: $TOTAL_FAILED"
    fi
else
    info "No user hosts found"
fi

# ============================================================
# Chain Health (scan miner daemon logs)
# ============================================================
header "Chain Health"
if [ "$NUM_MINERS" -gt 0 ]; then
    ALT_BLOCKS=0
    REORGS=0
    for miner_dir in "${MINER_DIRS[@]}"; do
        # Find daemon log (largest stdout file, or one with p2p traffic)
        daemon_log=""
        for f in "$miner_dir"/bash.*.stdout; do
            if [ -s "$f" ] && grep -q "BLOCK SUCCESSFULLY ADDED\|net.p2p\|Synced\|blockchain" "$f" 2>/dev/null; then
                daemon_log="$f"
                break
            fi
        done
        if [ -n "$daemon_log" ]; then
            cnt=$(grep -c "ALTERNATIVE" "$daemon_log" 2>/dev/null || true)
            ALT_BLOCKS=$((ALT_BLOCKS + ${cnt:-0}))
            cnt=$(grep -c "REORGANIZE" "$daemon_log" 2>/dev/null || true)
            REORGS=$((REORGS + ${cnt:-0}))
        fi
    done
    [ "$REORGS" -gt 0 ]     && err  "Chain reorgs (miners): $REORGS"
    [ "$ALT_BLOCKS" -gt 0 ] && warn "Alternative blocks (miners): $ALT_BLOCKS"
    [ "$REORGS" -eq 0 ] && [ "$ALT_BLOCKS" -eq 0 ] && ok "No forks detected in miner logs"
else
    info "No miner hosts to check"
fi

# ============================================================
# Resources
# ============================================================
header "Resources"
if [ -n "${RUN_DIR:-}" ]; then
    MEM_FILE="$RUN_DIR/memory_samples.csv"
    if [ -f "$MEM_FILE" ] && [ -s "$MEM_FILE" ]; then
        LAST_MEM=$(tail -1 "$MEM_FILE")
        info "Latest memory sample: $LAST_MEM"
    fi
fi
if [ -n "${SHADOW_PID:-}" ]; then
    RSS=$(ps -o rss= -p "$SHADOW_PID" 2>/dev/null | xargs || true)
    if [ -n "${RSS:-}" ]; then
        RSS_GB=$(python3 -c "print(f'{int($RSS) / 1048576:.1f}')" 2>/dev/null || echo "?")
        info "Shadow RSS: ${RSS_GB} GB"
    fi
fi

# ============================================================
# Footer
# ============================================================
echo ""
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
echo -e "${DIM}For detailed log analysis:${NC}"
echo -e "${DIM}  python3 $SCRIPT_DIR/log_processor.py --base-dir $HOSTS_DIR --chunk \"3,500\" --dry-run --max-workers 4${NC}"
echo ""
