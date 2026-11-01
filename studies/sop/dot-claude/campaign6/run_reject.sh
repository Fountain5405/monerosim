# COPY for reference only — do NOT run (it would relaunch the six *_reject matrices). Live driver: scratchpad run_reject.sh
# Campaign 6 (2026-09-29): stranding-free re-run — flagged bridge + reject_aware attacker, 16 cells, 12 at a time.
# Progress: matrix_runs/<name>/cells/*.json markers; results.json + table.md when a matrix finishes.
set -u
cd /scratch/monerosim_dev/monerosim || exit 99
OUT=/tmp/claude-1013/-scratch-monerosim-dev/37d8b7f9-1d74-4129-91d4-057d3646e295/scratchpad/matrix6
mkdir -p "$OUT"
: >> "$OUT/pids.txt"
declare -A PID
launch() {
  local s=$1
  setsid nohup venv/bin/python scripts/selfish_matrix.py "test_configs/matrix/$s.yaml" > "$OUT/$s.driver.log" 2>&1 < /dev/null &
  PID[$s]=$!
  echo "$s pid=$! started=$(date -u +%FT%TZ)" | tee -a "$OUT/pids.txt"
  sleep 20   # stagger the runners' initial cargo-build / archive scans
}
finished() {
  local s=$1
  [ -f "matrix_runs/$s/results.json" ] && return 0
  kill -0 "${PID[$s]}" 2>/dev/null && return 1
  return 0
}
ALL="pop_sop2_h10_reject pop_sop2_h10_reject_rep pop_exact_h10_reject pop_exact_h10_reject_rep pop_exact_mid_reject pop_exact_mid_reject_rep"
echo "reject start $(date -u +%FT%TZ) HEAD=$(git rev-parse --short HEAD)" | tee -a "$OUT/stages.txt"
for s in $ALL; do launch $s; done
for s in $ALL; do
  until finished "$s"; do sleep 120; done
  echo "$s finished=$(date -u +%FT%TZ) results=$([ -f matrix_runs/$s/results.json ] && echo yes || echo NO)" | tee -a "$OUT/stages.txt"
done
echo "REJECT_DONE $(date -u +%FT%TZ)" | tee -a "$OUT/stages.txt"
