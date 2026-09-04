#!/bin/bash
#
# run_dir_lib.sh - resolve, classify and allocate monerosim run directories.
#
# Bash twin of scripts/run_dirs.py (keep them in sync). Sourced by run_sim.sh,
# scripts/check_sim.sh, start_here.sh and scripts/prune_archives.sh.
#
# A run lives for its whole life in <archive base>/<run_id>/ where
# run_id = YYYYmmdd_HHMMSS_<name>[_N]. Resolution order (resolve_run_dir):
#   1. explicit argument   2. $MONEROSIM_RUN_DIR   3. newest under the base.
# State (run_dir_state): live (.owner_pid names a process that exists),
# complete (summary.txt present), incomplete (neither).

# Guard against double-sourcing.
if [[ -n "${MONEROSIM_RUN_DIR_LIB_SOURCED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
MONEROSIM_RUN_DIR_LIB_SOURCED=1

_run_dir_lib_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# run_dir_archive_base -> echo $MONEROSIM_ARCHIVE_BASE or <repo>/archived_runs
run_dir_archive_base() {
    echo "${MONEROSIM_ARCHIVE_BASE:-$_run_dir_lib_root/archived_runs}"
}

# run_dir_is_live DIR -> 0 iff DIR/.owner_pid names a process that exists.
# /proc rather than `kill -0` so another user's run counts as live.
run_dir_is_live() {
    local pid
    pid=$(cat "$1/.owner_pid" 2>/dev/null) || return 1
    [[ "$pid" =~ ^[0-9]+$ ]] && [[ -d "/proc/$pid" ]]
}

# run_dir_state DIR -> echo live | complete | incomplete
run_dir_state() {
    if run_dir_is_live "$1"; then
        echo live
    elif [[ -f "$1/summary.txt" ]]; then
        echo complete
    else
        echo incomplete
    fi
}

# newest_run_dir [BASE] -> echo the lexically greatest YYYYmmdd_HHMMSS_* dir; rc 1 if none
# Filters to directories BEFORE sorting/picking the max (parity with run_dirs.py,
# which does the same p.is_dir() filter before sorting names) -- a same-named
# regular file must not shadow a real, older run directory.
newest_run_dir() {
    local base="${1:-$(run_dir_archive_base)}" d name
    [[ -d "$base" ]] || return 1
    name=$(
        for d in "$base"/*/; do
            [[ -d "$d" ]] || continue
            basename "$d"
        done | grep -E '^[0-9]{8}_[0-9]{6}_' | LC_ALL=C sort | tail -1
    )
    [[ -n "$name" ]] || return 1
    echo "$base/$name"
}

# resolve_run_dir [DIR] -> echo the run dir; "run: DIR (STATE)" on stderr; rc 2 if none
resolve_run_dir() {
    local dir
    if [[ -n "${1:-}" ]]; then
        dir="$1"
        [[ -d "$dir" ]] || { echo "run dir not a directory: $dir" >&2; return 2; }
    elif [[ -n "${MONEROSIM_RUN_DIR:-}" ]]; then
        dir="$MONEROSIM_RUN_DIR"
        [[ -d "$dir" ]] || { echo "MONEROSIM_RUN_DIR is not a directory: $dir" >&2; return 2; }
    else
        dir=$(newest_run_dir) || {
            echo "no run directory: none given, MONEROSIM_RUN_DIR unset, nothing under $(run_dir_archive_base)" >&2
            return 2
        }
    fi
    dir=$(readlink -f "$dir")
    echo "run: $dir ($(run_dir_state "$dir"))" >&2
    echo "$dir"
}

# allocate_run_dir BASE NAME -> mkdir BASE/<ts>_NAME atomically (suffix _2.._99
# on collision), write .owner_pid = $$ (the sourcing shell), echo the run id.
# rc 1 after 99 collisions. MONEROSIM_RUN_TS overrides the timestamp (tests).
# A failed mkdir counts as a collision only if the target now exists; any other
# mkdir failure (unwritable BASE, disk full, ...) is reported and returns 1
# immediately rather than being misreported as 99 collisions.
allocate_run_dir() {
    local base="$1" name="$2" ts candidate n=1
    [[ -n "$base" ]] || { echo "allocate_run_dir: empty BASE" >&2; return 1; }
    ts="${MONEROSIM_RUN_TS:-$(date '+%Y%m%d_%H%M%S')}"
    mkdir -p "$base" || { echo "allocate_run_dir: cannot create $base" >&2; return 1; }
    candidate="${ts}_${name}"
    until mkdir "$base/$candidate" 2>/dev/null; do
        if [[ ! -e "$base/$candidate" ]]; then
            echo "allocate_run_dir: mkdir failed for $base/$candidate" >&2
            return 1
        fi
        n=$((n + 1))
        if (( n > 99 )); then
            echo "allocate_run_dir: 99 collisions for $base/${ts}_${name}" >&2
            return 1
        fi
        candidate="${ts}_${name}_${n}"
    done
    echo $$ > "$base/$candidate/.owner_pid"
    echo "$candidate"
}
