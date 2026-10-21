#!/bin/bash
# Report whether kernel same-page merging (KSM) is usable for `run_sim.sh --ksm`.
#
# Three kernel settings matter, and all reset at every reboot:
#   /sys/kernel/mm/ksm/run              must be 1, or nothing merges
#   /sys/kernel/mm/ksm/pages_to_scan    pages scanned per ksmd wake-up
#   /sys/kernel/mm/ksm/sleep_millisecs  time between wake-ups
# The scan rate is pages_to_scan x 4 KB / sleep_millisecs. The kernel defaults
# (100 pages / 20 ms, ~20 MB/s; Ubuntu 6.8 ships 200 ms, ~2 MB/s) are far slower
# than monerods start: a 125-node run needs ~39 GB before merging catches up.
#
# Prints one status line plus, when something is off, the fix (one-off and
# persistent). Exit status: 0 = ready, 1 = enabled but scanning too slowly,
# 2 = disabled or unavailable. Read-only; never needs root.
#
# With --nodes N it also prints the merge lag to expect for N monerods. A new
# page merges after about two full scans, and a scan covers ~300 MB per
# monerod, so lag ~ 2 x N x 300 MB / scan rate; the unmerged backlog is then
# about (monerod starts per wall-minute) x lag x 256 MB. The X0 pilot of
# 2026-10-20 (~455 daemons, relays starting ~9 per wall-minute) matched this:
# ~20 relays' caches unmerged at 10000 pages, ~11 at 20000. Informational only,
# since ksmd is one kernel thread (~0.4 core at 10000 pages there, about one
# core at most): past that, only slower node starts shrink the backlog.
#
# Usage: scripts/ksm_check.sh [--quiet-ok] [--nodes N]

KSM_DIR=/sys/kernel/mm/ksm
RECOMMENDED_PAGES=20000
RECOMMENDED_SLEEP_MS=20
MIN_RATE_MB=1000           # recommended is ~4 GB/s
MB_PER_NODE=300            # mergeable anon memory one scan covers per monerod

quiet_ok=0; nodes=
while (( $# )); do
    case $1 in
        --quiet-ok) quiet_ok=1; shift ;;
        --nodes) nodes=$2; shift 2 ;;
        *) echo "usage: $0 [--quiet-ok] [--nodes N]" >&2; exit 2 ;;
    esac
done

if [[ ! -r "$KSM_DIR/run" ]]; then
    echo "KSM: not available in this kernel ($KSM_DIR missing); --ksm will have no effect"
    exit 2
fi

run=$(cat "$KSM_DIR/run")
pages=$(cat "$KSM_DIR/pages_to_scan")
sleep_ms=$(cat "$KSM_DIR/sleep_millisecs")
(( sleep_ms > 0 )) || sleep_ms=1
rate_mb=$(( pages * 4096 * 1000 / sleep_ms / 1000000 ))

fix() {
    echo "  Fix now (needs root, lasts until reboot):"
    echo "    sudo sh -c 'echo $RECOMMENDED_PAGES > $KSM_DIR/pages_to_scan && echo $RECOMMENDED_SLEEP_MS > $KSM_DIR/sleep_millisecs && echo 1 > $KSM_DIR/run'"
    echo "  Fix permanently (applied at every boot by systemd-tmpfiles):"
    echo "    printf 'w $KSM_DIR/pages_to_scan - - - - $RECOMMENDED_PAGES\\nw $KSM_DIR/sleep_millisecs - - - - $RECOMMENDED_SLEEP_MS\\nw $KSM_DIR/run - - - - 1\\n' \\"
    echo "      | sudo tee /etc/tmpfiles.d/monerosim-ksm.conf && sudo systemd-tmpfiles --create /etc/tmpfiles.d/monerosim-ksm.conf"
}

if [[ "$run" != "1" ]]; then
    echo "KSM: kernel merging is disabled ($KSM_DIR/run=$run); --ksm runs use ~10x the RAM (~320 MB/node)"
    fix
    exit 2
fi

if (( rate_mb < MIN_RATE_MB )); then
    echo "KSM: enabled but scanning slowly (pages_to_scan=$pages every ${sleep_ms} ms, ~${rate_mb} MB/s); merging"
    echo "  falls behind node starts, so RAM peaks near the no-KSM ~320 MB/node."
    echo "  Recommended: pages_to_scan=$RECOMMENDED_PAGES, sleep_millisecs=$RECOMMENDED_SLEEP_MS (~$(( RECOMMENDED_PAGES * 4096 * 1000 / RECOMMENDED_SLEEP_MS / 1000000 )) MB/s)"
    fix
    exit 1
fi

(( quiet_ok )) || echo "KSM: ready (run=1, pages_to_scan=$pages every ${sleep_ms} ms, ~${rate_mb} MB/s)"
if [[ -n $nodes ]]; then
    rec_mb=$(( RECOMMENDED_PAGES * 4096 * 1000 / RECOMMENDED_SLEEP_MS / 1000000 ))
    echo "KSM: ~$(( 2 * nodes * MB_PER_NODE / rate_mb )) s merge lag for $nodes monerods at this rate" \
         "(~$(( 2 * nodes * MB_PER_NODE / rec_mb )) s at the recommended $RECOMMENDED_PAGES pages / $RECOMMENDED_SLEEP_MS ms)"
fi
exit 0
