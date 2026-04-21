#!/usr/bin/env bash
#
# prune_archives.sh — shrink archived Monerosim run directories to their
# essentials while keeping enough to diagnose / compare later.
#
# For each archive directory passed in, keeps:
#   * All small top-level files (summary.txt, input_config.yaml, logs, etc.)
#   * blockchain/, monitoring/, transaction_registry/
#   * shadow.data/{processed-config.yaml,sim-stats.json,monerosim_monitor.log}
#   * A small set of sample hosts in daemon_logs/ and shadow.data/hosts/:
#       - Always:  miner-001, relay-001, miner-distributor, simulation-monitor, dnsserver
#       - Auto:    top-N tx senders from summary.txt (likely "survivors")
#       - Auto:    N failed-user samples (bottom of the tx list, excluding zeros)
#       - Auto:    any user whose wallet-rpc was killed by a signal (SIGABRT/SIGSEGV)
#       - Manual:  anything passed via --keep
# Everything else in daemon_logs/ and shadow.data/hosts/ is deleted.
#
# Usage:
#   prune_archives.sh [OPTIONS] <archive_dir>...
#
# Typical: 100-user, 895-relay run goes from ~150 GB to ~1.5 GB.

set -eu

# ---------- defaults ----------
TOP_USERS=4
SAMPLE_FAILED=3
EXTRA_KEEP=""
DRY_RUN=false
FORCE=false

# Small hosts we always keep.
ALWAYS_HOSTS="dnsserver miner-001 miner-distributor simulation-monitor relay-001"
ALWAYS_DAEMONS="monero-miner-001 monero-relay-001"

# ---------- arg parsing ----------
usage() {
    cat <<'EOF'
Usage: prune_archives.sh [OPTIONS] <archive_dir>...

Options:
  -n, --dry-run             Show what would be kept/deleted; don't delete anything
  --top-users N             Keep top-N users by tx count from summary (default: 4)
  --sample-failed N         Keep N additional failed-user samples (default: 3)
  --keep USER[,USER...]     Extra agent IDs to always keep (comma-separated, e.g. user-001,user-042)
  --force                   Prune even if summary.txt is missing (incomplete runs)
  -h, --help                Show this help

Always keeps (in addition to anything above):
  - All small top-level files (summary, configs, logs, monitoring data)
  - Sample hosts: miner-001, relay-001, miner-distributor, simulation-monitor, dnsserver
  - Any user whose wallet-rpc died with SIGABRT/SIGSEGV (auto-detected)
EOF
    exit "${1:-0}"
}

ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run)     DRY_RUN=true; shift ;;
        --top-users)      TOP_USERS="$2"; shift 2 ;;
        --sample-failed)  SAMPLE_FAILED="$2"; shift 2 ;;
        --keep)           EXTRA_KEEP="$2"; shift 2 ;;
        --force)          FORCE=true; shift ;;
        -h|--help)        usage ;;
        -*)               echo "Unknown option: $1" >&2; usage 1 ;;
        *)                ARGS+=("$1"); shift ;;
    esac
done

[[ ${#ARGS[@]} -eq 0 ]] && usage 1

# ---------- helpers ----------
# Extract the top-N highest-tx users from summary.txt "Created by:" block.
top_tx_users() {
    local summary="$1" n="$2"
    grep -E "^    user-[0-9]+ +[0-9]+ txs" "$summary" 2>/dev/null \
        | awk '{print $2, $1}' | sort -n -r | head -n "$n" | awk '{print $2}'
}

# Extract N failed-user samples (the ones with tx >= 1 but not in the top).
sample_failed_users() {
    local summary="$1" n="$2" top="$3"
    # exclude users that appear in $top (space-separated)
    grep -E "^    user-[0-9]+ +[0-9]+ txs" "$summary" 2>/dev/null \
        | awk '{print $2, $1}' | sort -n \
        | awk -v top=" $top " '{
            if (index(top, " " $2 " ") == 0) print $2
          }' \
        | head -n "$n"
}

# Extract users whose wallet-rpc exited via signal.
crashed_users() {
    local shadow_log="$1"
    grep -oE "user-[0-9]+[^ ]*\.bash\.1028' exited with status Signaled" "$shadow_log" 2>/dev/null \
        | grep -oE "user-[0-9]+" | sort -u
}

rm_or_echo() {
    local dir="$1"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  WOULD DELETE: $dir"
    else
        rm -rf "$dir"
    fi
}

prune_one() {
    local archive="$1"
    archive="${archive%/}"
    [[ -d "$archive" ]] || { echo "Not a directory: $archive" >&2; return 1; }

    local summary="$archive/summary.txt"
    if [[ ! -f "$summary" ]] && [[ "$FORCE" == "false" ]]; then
        echo "Skipping $archive: no summary.txt (use --force to prune anyway)" >&2
        return 1
    fi

    echo "=== $archive ==="
    local before
    before=$(du -sh "$archive" 2>/dev/null | cut -f1)
    echo "  Size before: $before"

    # Build keep lists
    local top_users=""
    local failed_samples=""
    local crashes=""

    if [[ -f "$summary" ]]; then
        top_users=$(top_tx_users "$summary" "$TOP_USERS" | tr '\n' ' ')
        failed_samples=$(sample_failed_users "$summary" "$SAMPLE_FAILED" "$top_users" | tr '\n' ' ')
    fi

    local shadow_log="$archive/shadow_run.log"
    if [[ -f "$shadow_log" ]]; then
        crashes=$(crashed_users "$shadow_log" | tr '\n' ' ')
    fi

    # EXTRA_KEEP comma->space
    local extra="${EXTRA_KEEP//,/ }"

    # Build the combined keep set (dedup + pad with spaces)
    local users_keep
    users_keep=$(echo "$top_users $failed_samples $crashes $extra" | tr ' ' '\n' | awk 'NF' | sort -u | tr '\n' ' ')

    # Final host/daemon keep lists.
    local hosts_keep="$ALWAYS_HOSTS $users_keep"
    local daemons_keep="$ALWAYS_DAEMONS"
    for u in $users_keep; do
        daemons_keep="$daemons_keep monero-$u"
    done

    echo "  Keeping users:  ${users_keep:-<none>}"
    echo "    - top:    ${top_users:-<none>}"
    echo "    - failed: ${failed_samples:-<none>}"
    echo "    - crash:  ${crashes:-<none>}"
    [[ -n "$extra" ]] && echo "    - extra:  $extra"

    # Prune daemon_logs/
    if [[ -d "$archive/daemon_logs" ]]; then
        for d in "$archive/daemon_logs"/*/; do
            [[ -d "$d" ]] || continue
            local name="${d%/}"; name="${name##*/}"
            case " $daemons_keep " in
                *" $name "*) ;;
                *) rm_or_echo "$d" ;;
            esac
        done
    fi

    # Prune shadow.data/hosts/
    if [[ -d "$archive/shadow.data/hosts" ]]; then
        for d in "$archive/shadow.data/hosts"/*/; do
            [[ -d "$d" ]] || continue
            local name="${d%/}"; name="${name##*/}"
            case " $hosts_keep " in
                *" $name "*) ;;
                *) rm_or_echo "$d" ;;
            esac
        done
    fi

    if [[ "$DRY_RUN" == "false" ]]; then
        local after
        after=$(du -sh "$archive" 2>/dev/null | cut -f1)
        echo "  Size after:  $after"
    fi
    echo ""
}

# ---------- main ----------
for arg in "${ARGS[@]}"; do
    prune_one "$arg" || true
done
