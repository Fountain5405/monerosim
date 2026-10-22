#!/bin/bash
# Sequential queue of X0 cells. Usage: x0_queue.sh <queue-file>
# Each non-comment line is a cell name (test_configs/x0/cells/<name>.yaml) or a path to a
# scenario yaml. The first line is popped and run under a RAM/swap/disk guard, then scored
# with analysis/spy/x0_calibration.py; the next one starts. Stops on any failure or trip.
# Edit the queue file while it runs: it is re-read before each cell.
set -u
REPO=/home/lever65/monerosim
S=/tmp/claude-1002/-home-lever65-monerosim/df57b8d8-00c1-4e9b-8f85-c70f598c44e3/scratchpad
ARCH=/mnt/ssdpool/monerosim_archives
Q=$1
EV=$S/x0_queue.events
mkdir -p "$ARCH"
ev() { echo "$(date +%H:%M) $*" | tee -a "$EV"; }
strip() { sed 's/\x1b\[[0-9;]*m//g'; }
avail() { awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo; }
swapused() { awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo; }

rp=""; spid=""
trap 'ev "STOPPED by signal"; [ -n "$spid" ] && kill -TERM "$spid" 2>/dev/null; [ -n "$rp" ] && kill "$rp" 2>/dev/null; exit 130' TERM INT

while :; do
  line=$(grep -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' "$Q" | head -1)
  [ -z "$line" ] && { ev "QUEUE EMPTY"; exit 0; }
  python3 - "$Q" "$line" <<'PY'
import sys
q, line = sys.argv[1], sys.argv[2]
rows = open(q).read().split("\n")
for i, r in enumerate(rows):
    if r.strip() == line.strip():
        del rows[i]
        break
open(q, "w").write("\n".join(rows))
PY
  if [[ "$line" == */* ]]; then cfg=$line; name=$(basename "$line" .yaml)
  else cfg=$REPO/test_configs/x0/cells/$line.yaml; name=$line; fi

  if pgrep -x shadow > /dev/null; then ev "FAIL $name: another Shadow is running"; exit 1; fi
  a=$(avail)
  if [ "$a" -lt 18000 ]; then ev "FAIL $name: only $a MB available before start"; exit 1; fi

  cd "$REPO" || exit 1
  rm -f "$S/q.rundir"
  LOG=$S/q_$name.log
  setsid nohup ./run_sim.sh --config "$cfg" --bootfast --ksm --no-monitor --name "$name" \
      --archive-dir "$ARCH" --run-dir-file "$S/q.rundir" > "$LOG" 2>&1 < /dev/null &
  rp=$!
  for _ in $(seq 90); do [ -s "$S/q.rundir" ] && break; sleep 2; done
  RUN=$(cat "$S/q.rundir" 2>/dev/null)
  ev "START $name run=$RUN"

  spid=""; trip=""; swbase=$(swapused); t0=$(date +%s)
  while kill -0 "$rp" 2>/dev/null; do
    [ -z "$spid" ] && spid=$(strip < "$LOG" | grep -oP 'Shadow started \(PID: \K[0-9]+' | tail -1)
    a=$(avail); sw=$(swapused); dk=$(df -BG --output=avail "$ARCH" | tail -1 | tr -dc 0-9)
    echo "$(date +%H:%M:%S) $name avail_mb=$a swap_mb=$sw swap_base=$swbase disk_gb=$dk" >> "$S/q_mem.log"
    if [ "$a" -lt 1500 ] || [ $((sw - swbase)) -gt 1500 ] || [ "$dk" -lt 30 ]; then
      trip="avail_mb=$a swap_growth_mb=$((sw - swbase)) disk_gb=$dk"
      ev "TRIP $name: $trip; killing Shadow (pid ${spid:-unknown})"
      [ -n "$spid" ] && kill -TERM "$spid"
      break
    fi
    sleep 20
  done
  while kill -0 "$rp" 2>/dev/null; do sleep 5; done
  wall=$(( ($(date +%s) - t0) / 60 ))

  code=$(strip < "$LOG" | awk '/Exit code:/{print $3}' | tail -1)
  summ=$(strip < "$LOG" | grep -E "Created:|In blocks:" | awk '{printf "%s%s ", $1, $2" "$3}' )
  minav=$(awk -F, 'NR>1 && $12!=""{if(m==""||$12+0<m)m=$12+0}END{print m}' "$RUN/memory_samples.csv" 2>/dev/null)
  rep="n/a"
  if [ -n "$RUN" ] && [ -d "$RUN" ]; then
    "$REPO/venv/bin/python" "$REPO/analysis/spy/x0_calibration.py" "$RUN" --json "$RUN/x0_calibration.json" \
        > "$RUN/x0_calibration.txt" 2>&1
    share=$(awk '$1=="light"{print $3}' "$RUN/x0_calibration.txt")
    fluff=$(grep -oP 'fluff per hop \K[0-9.]+' "$RUN/x0_calibration.txt" | head -1)
    stems=$(grep -oP 'stems: \K[0-9]+' "$RUN/x0_calibration.txt" | head -1)
    rep="light_out_share=${share:-?} fluff_per_hop=${fluff:-?} stem_txs=${stems:-?}"
  fi
  ev "DONE $name exit=${code:-?} wall=${wall}m min_avail_mb=${minav:-?} $rep run=$RUN"
  if [ -n "$trip" ] || [ "${code:-1}" != "0" ]; then ev "STOPPING QUEUE after $name (trip='${trip}' exit=${code:-?})"; exit 1; fi
done
