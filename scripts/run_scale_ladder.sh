#!/usr/bin/env bash
# Run scale-ladder rungs in order, smallest first, stopping at the first one
# that fails or runs out of RAM, swap headroom or disk. Generalized from the
# 2026-10-19 32 GB ladder driver (docs/PERFORMANCE_AND_SCALE.md).
#
# Usage:
#   scripts/run_scale_ladder.sh [options] <out_dir> <rung.scenario.yaml> ...
# Detach it so it survives the terminal (and a Claude Code restart):
#   setsid nohup scripts/run_scale_ladder.sh <out_dir> <rungs...> > <out_dir>.driver.out 2>&1 &
#
# Per rung:
#   1. Expand the scenario on this box (scripts/generate_config.py
#      --no-safe-tx-interval). The users' activity stagger comes from this
#      box's ~/.monerosim/calibration.json, so it differs between machines.
#   2. Set stop_time = the last user's activity start + 2 h, at least 8 h
#      (every user transacts for 2 h; the 32 GB ladder's rule), capped by
#      --max-stop, and expand again.
#   3. ./run_sim.sh --bootfast --ksm --no-monitor, sampling every 30 s into
#      <rung>.samples.csv. Abort the rung (SIGINT, then SIGKILL, to that
#      rung's shadow only) when MemAvailable < --min-avail-mb, swap grows by
#      > --max-swap-mb since the rung started, or free disk < --min-disk-gb.
# Results: <out_dir>/ladder.log (START/END/ABORT lines), <rung>.log (run_sim
# output), <rung>.rundir (the archive dir), <rung>.yaml (what ran).
#
# Options:
#   --max-stop HOURS     cap stop_time (default: none). Large rungs on fewer
#                        cores can need days at the full rule; RAM peaks at
#                        the end of the boot phase, so a cap still answers
#                        "does it fit".
#   --min-avail-mb MB    default: max(1500, 2% of RAM)
#   --max-swap-mb MB     default: 1500
#   --min-disk-gb GB     default: 50 (the 3k rung wrote 25-30 GB/h at peak)
#   --no-ksm-check       skip scripts/ksm_check.sh (default: stop if KSM is
#                        off or too slow)
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/venv/bin/python"
[[ -x $PY ]] || PY=python3
ME="$(id -un)"
MEM_TOTAL_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)

max_stop=""; min_avail=$(( MEM_TOTAL_MB / 50 > 1500 ? MEM_TOTAL_MB / 50 : 1500 ))
max_swap=1500; min_disk=50; ksm_check=1
while [[ $# -gt 0 && $1 == --* ]]; do
    case $1 in
        --max-stop) max_stop=$2; shift 2 ;;
        --min-avail-mb) min_avail=$2; shift 2 ;;
        --max-swap-mb) max_swap=$2; shift 2 ;;
        --min-disk-gb) min_disk=$2; shift 2 ;;
        --no-ksm-check) ksm_check=0; shift ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
done
[[ $# -ge 2 ]] || { sed -n '2,/^set /p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 2; }
OUT=$(mkdir -p "$1" && cd "$1" && pwd); shift
LOG=$OUT/ladder.log
cd "$REPO"

note() { echo "$(date -Is) $*" | tee -a "$LOG"; }

if (( ksm_check )); then
    if ! scripts/ksm_check.sh >> "$LOG" 2>&1; then
        note "LADDER STOP: KSM not ready (scripts/ksm_check.sh; --no-ksm-check to skip)"
        exit 1
    fi
fi
note "LADDER $* (RAM ${MEM_TOTAL_MB} MB, $(nproc) CPUs; abort at avail<${min_avail} MB, swap+${max_swap} MB, disk<${min_disk} GB)"

swap_used_mb() { awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo; }

# Last user's activity_start_time (s) in an expanded config.
last_activity() {
    "$PY" - "$1" <<'EOF'
import sys, yaml
agents = yaml.safe_load(open(sys.argv[1]))["agents"]
if isinstance(agents, dict):
    agents = [dict(id=k, **v) for k, v in agents.items()]
print(max((int(a.get("activity_start_time") or 0) for a in agents
           if str(a.get("id", "")).startswith("user")), default=0))
EOF
}

for scen in "$@"; do
    rung=$(basename "$scen" .scenario.yaml)
    tmp=$OUT/$rung.scenario.yaml; cfg=$OUT/$rung.yaml
    log=$OUT/$rung.log; samples=$OUT/$rung.samples.csv; rdf=$OUT/$rung.rundir
    cp "$scen" "$tmp"
    if ! "$PY" scripts/generate_config.py --from "$tmp" -o "$cfg" --no-safe-tx-interval > "$log" 2>&1; then
        note "LADDER STOP: expanding $scen failed (see $log)"; exit 1
    fi
    last=$(last_activity "$cfg")
    stop_h=$(( (last + 7200 + 3599) / 3600 )); (( stop_h < 8 )) && stop_h=8
    [[ -n $max_stop ]] && (( stop_h > max_stop )) && stop_h=$max_stop
    sed -i "s/^\(  stop_time:\) *[^ #]*/\1 ${stop_h}h/" "$tmp"
    if ! "$PY" scripts/generate_config.py --from "$tmp" -o "$cfg" --no-safe-tx-interval >> "$log" 2>&1; then
        note "LADDER STOP: expanding $scen failed (see $log)"; exit 1
    fi
    note "START $rung: last user active from $(( last / 60 )) min, stop_time ${stop_h}h"

    echo "epoch,mem_avail_mb,swap_used_mb,ksm_sharing_pages,ksm_shared_pages,user_rss_mb,disk_free_gb,load1" > "$samples"
    # Own session, so an abort can find this rung's shadow and nothing else.
    setsid ./run_sim.sh --config "$cfg" --bootfast --ksm --no-monitor --name "ladder_$rung" \
        --run-dir-file "$rdf" >> "$log" 2>&1 &
    rp=$!
    killed=""
    sw0=$(swap_used_mb)
    while kill -0 "$rp" 2>/dev/null; do
        ma=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
        sw=$(swap_used_mb)
        ks=$(cat /sys/kernel/mm/ksm/pages_sharing 2>/dev/null || echo 0)
        kd=$(cat /sys/kernel/mm/ksm/pages_shared 2>/dev/null || echo 0)
        rss=$(ps -u "$ME" -o rss= | awk '{s+=$1}END{print int(s/1024)}')   # double counts KSM pages
        df_=$(df -BG --output=avail "$REPO" | tail -1 | tr -dc 0-9)
        echo "$(date +%s),$ma,$sw,$ks,$kd,$rss,$df_,$(cut -d' ' -f1 /proc/loadavg)" >> "$samples"
        if [[ -z $killed ]] && (( ma < min_avail || sw - sw0 > max_swap || df_ < min_disk )); then
            killed="mem_avail=${ma}MB swap=${sw}MB disk=${df_}GB"
            note "ABORT $rung: $killed"
            pids=$(pgrep -s "$rp" -x shadow)
            [[ -n $pids ]] && kill -INT $pids
            sleep 60
            pids=$(pgrep -s "$rp" -x shadow)
            [[ -n $pids ]] && kill -KILL $pids
        fi
        sleep 30
    done
    wait "$rp"; rc=$?
    peak=$(awk -F, 'NR>1 && (min==""||$2<min){min=$2}END{print min}' "$samples")
    note "END $rung rc=$rc min_mem_avail=${peak}MB ${killed:+aborted:$killed} rundir=$(cat "$rdf" 2>/dev/null)"
    if [[ $rc -ne 0 || -n $killed ]]; then
        note "LADDER STOP at $rung"; exit 1
    fi
done
note "LADDER DONE"
