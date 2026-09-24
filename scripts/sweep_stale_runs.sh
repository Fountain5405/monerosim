#!/usr/bin/env bash
#
# sweep_stale_runs.sh - list (and, with --delete, remove) per-run /tmp dirs
# whose owning run_sim.sh is gone.
#
# run_sim.sh never deletes another run's /tmp/monerosim-<run_id>/ on its own:
# a dead-owner dir is either a --no-clean run kept on purpose (.keep marker)
# or a crashed/killed run whose daemon logs, peer-list dumps and shared/
# never reached archived_runs/ — worth a look before it goes. This script is
# the deliberate step. Without --delete it only reports.
#
# Also candidates: namespaces a bare `monerosim --config` minted for itself
# (.generated_by marker, no .owner_pid — the generator's pid is gone the
# moment it exits) as long as they hold no daemon data; one that does (a
# sim run by hand against that config) is treated like a kept dir.
#
# Skipped always: dirs with a live owner (concurrent run), dirs marked .keep,
# dirs with neither breadcrumb (not created by us), and dirs we don't own.
#
# Usage: scripts/sweep_stale_runs.sh [--delete] [--include-kept] [ROOT]
#   ROOT   directory holding the monerosim-* run dirs (default /tmp)
#   --include-kept   also treat .keep dirs (and generator namespaces holding
#                    daemon data) as candidates; with --delete, removes them

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=run_dir_lib.sh
source "$SCRIPT_DIR/run_dir_lib.sh"

DELETE=false
INCLUDE_KEPT=false
ROOT=/tmp
for arg in "$@"; do
    case "$arg" in
        --delete) DELETE=true ;;
        --include-kept) INCLUDE_KEPT=true ;;
        -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*) echo "unknown option: $arg" >&2; exit 2 ;;
        *) ROOT="$arg" ;;
    esac
done

candidates=0
for d in "$ROOT"/monerosim-*/; do
    [[ -d "$d" ]] || continue
    d="${d%/}"
    if [[ ! -O "$d" ]]; then
        echo "skip   $d  (not ours)"
        continue
    fi
    opid=$(cat "$d/.owner_pid" 2>/dev/null || true)
    opid="${opid%% *}"
    size=$(du -sh "$d" 2>/dev/null | cut -f1 || true)
    if [[ -z "$opid" ]]; then
        if [[ ! -f "$d/.generated_by" ]]; then
            echo "skip   $d  (no .owner_pid / .generated_by — not created by us)"
            continue
        fi
        # Bare-binary namespace. Daemon data inside means someone ran a sim
        # by hand against it: keep unless asked.
        if compgen -G "$d/monero-*" > /dev/null && [[ "$INCLUDE_KEPT" != true ]]; then
            echo "kept   $d  (${size:-?}; generator namespace WITH daemon data; pass --include-kept to sweep it)"
            continue
        fi
        why="generator namespace, no run_sim.sh owner"
    else
        if run_dir_is_live "$d"; then
            echo "live   $d  (owner pid $opid)"
            continue
        fi
        if [[ -f "$d/.keep" && "$INCLUDE_KEPT" != true ]]; then
            echo "kept   $d  (${size:-?}; --no-clean; pass --include-kept to sweep it)"
            continue
        fi
        why="owner pid $opid gone"
    fi
    candidates=$((candidates + 1))
    if [[ "$DELETE" == true ]]; then
        rm -rf "$d" && echo "REMOVED $d  (${size:-?})" || echo "FAILED  $d"
    else
        echo "stale  $d  (${size:-?}; $why)"
    fi
done

if [[ $candidates -gt 0 && "$DELETE" != true ]]; then
    echo "$candidates stale dir(s). Re-run with --delete to remove them."
elif [[ $candidates -eq 0 ]]; then
    echo "nothing to sweep under $ROOT"
fi
