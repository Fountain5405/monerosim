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
# Usage: scripts/ksm_check.sh [--quiet-ok]

KSM_DIR=/sys/kernel/mm/ksm
RECOMMENDED_PAGES=10000
RECOMMENDED_SLEEP_MS=20
MIN_RATE_MB=1000           # recommended is ~2 GB/s

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

[[ "$1" == "--quiet-ok" ]] || echo "KSM: ready (run=1, pages_to_scan=$pages every ${sleep_ms} ms, ~${rate_mb} MB/s)"
exit 0
