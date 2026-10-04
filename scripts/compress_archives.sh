#!/usr/bin/env bash
#
# compress_archives.sh - gzip finished runs' daemon logs in place, losing nothing.
#
# For each run dir, compresses every daemon_logs/<node>/bitmonero.log (and
# rotated bitmonero.log-*) that is not already .gz. Plain monerod logs shrink
# about 14x (an 86 MB log-level-1 relay log measured 6.2 MB with gzip -6).
# Read them back with zcat/zgrep or Python's gzip.open.
#
# Live runs (owner pid still alive, see run_dir_lib.sh) are skipped: a running
# sim still appends to its logs. Re-running is safe; .gz files are left alone.
#
# Usage: scripts/compress_archives.sh [-n|--dry-run] [--peerlist-dumps] [--jobs N] [RUN_DIR...]
#   RUN_DIR           run dirs to compress (default: every run under the archive
#                     base, $MONEROSIM_ARCHIVE_BASE or <repo>/archived_runs)
#   -n, --dry-run     only report what would be compressed
#   --peerlist-dumps  also compress daemon_logs/<node>/peerlist_dump.jsonl
#                     (eclipse runs; analysis/eclipse/analyze_peerlist_dumps.py
#                     reads .gz dumps)
#   --jobs N          parallel gzip processes (default 8, run under nice)

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=run_dir_lib.sh
source "$SCRIPT_DIR/run_dir_lib.sh"

DRY_RUN=false
DUMPS=false
JOBS=8
RUNS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run)     DRY_RUN=true; shift ;;
        --peerlist-dumps) DUMPS=true; shift ;;
        --jobs)           JOBS="$2"; shift 2 ;;
        -h|--help)        sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*)               echo "unknown option: $1" >&2; exit 2 ;;
        *)                RUNS+=("$1"); shift ;;
    esac
done
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo "--jobs needs a positive integer" >&2; exit 2; }

if [[ ${#RUNS[@]} -eq 0 ]]; then
    base="$(run_dir_archive_base)"
    for d in "$base"/*/; do
        [[ -d "$d" ]] && RUNS+=("${d%/}")
    done
fi

# Files to compress in one run, NUL-separated.
candidates() {
    local names=(-name 'bitmonero.log' -o -name 'bitmonero.log-*')
    [[ "$DUMPS" == true ]] && names+=(-o -name 'peerlist_dump.jsonl')
    find "$1/daemon_logs" -mindepth 2 -maxdepth 3 -type f \( "${names[@]}" \) ! -name '*.gz' -print0 2>/dev/null
}

gb() { awk -v b="$1" 'BEGIN { printf "%.2f GB", b / 1e9 }'; }
# Total bytes of the given files. Through xargs, not one stat call: a run with
# thousands of nodes and long paths would exceed the argument-length limit.
total_size() { [[ $# -gt 0 ]] || { echo 0; return; }; printf '%s\0' "$@" | xargs -0 -r stat -c %s | awk '{s += $1} END {print s + 0}'; }

failed=0
for run in "${RUNS[@]}"; do
    run="${run%/}"
    [[ -d "$run/daemon_logs" ]] || continue
    if run_dir_is_live "$run"; then
        echo "Skipping $run: run is LIVE (owner pid $(awk '{print $1}' "$run/.owner_pid"))" >&2
        continue
    fi

    mapfile -d '' files < <(candidates "$run")
    echo "=== $run ==="
    if [[ ${#files[@]} -eq 0 ]]; then
        echo "  nothing to compress"
        continue
    fi
    before=$(total_size "${files[@]}")

    if [[ "$DRY_RUN" == true ]]; then
        echo "  WOULD COMPRESS ${#files[@]} files ($(gb "$before"))"
        continue
    fi

    # gzip replaces each file with file.gz only after writing it fully; on a
    # write error (full disk) it removes the partial .gz and keeps the original.
    if ! printf '%s\0' "${files[@]}" | xargs -0 -r -n 16 -P "$JOBS" nice -n 10 gzip -6; then
        echo "  ERROR: gzip failed for some files in $run (originals of those are kept)" >&2
        failed=1
    fi
    gz=()
    for f in "${files[@]}"; do
        [[ -f "$f.gz" && ! -e "$f" ]] && gz+=("$f.gz")
    done
    after=$(total_size "${gz[@]}")
    echo "  compressed ${#gz[@]} of ${#files[@]} files: $(gb "$before") -> $(gb "$after")"
done
exit "$failed"
