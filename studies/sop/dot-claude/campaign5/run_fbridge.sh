#!/bin/bash
# COPY for the next session (2026-09-27): the live driver runs from the old session's scratchpad; this copy is for reference only — do NOT run it again (it would relaunch the matrices).
# Campaign 5 (2026-09-27): stranding re-run — attack cells with the bridge running the countermeasure rule (12 cells at once).
# Launch detached:  setsid nohup bash run_stage2.sh > matrix3/stage2.log 2>&1 < /dev/null &
# Progress: matrix_runs/<name>/cells/*.json markers; results.json + table.md when a matrix finishes.
set -u
cd /scratch/monerosim_dev/monerosim || exit 99
OUT=/tmp/claude-1013/-scratch-monerosim-dev-monerosim/30dd96ce-14de-4756-9664-b27918e47284/scratchpad/matrix3
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
finished() {  # a matrix is finished when it wrote results.json or its runner is gone
  local s=$1
  [ -f "matrix_runs/$s/results.json" ] && return 0
  kill -0 "${PID[$s]}" 2>/dev/null && return 1
  return 0
}
wait_all() {
  local s
  for s in "$@"; do
    until finished "$s"; do sleep 120; done
    echo "$s finished=$(date -u +%FT%TZ) results=$([ -f matrix_runs/$s/results.json ] && echo yes || echo NO)" | tee -a "$OUT/stages.txt"
  done
}
echo "fbridge start $(date -u +%FT%TZ)" | tee -a "$OUT/stages.txt"
launch pop_sop2_h10_fbridge; launch pop_sop2_h10_fbridge_rep; launch pop_exact_h10_fbridge; launch pop_exact_h10_fbridge_rep; launch pop_exact_mid_fbridge; launch pop_exact_mid_fbridge_rep
wait_all pop_sop2_h10_fbridge pop_sop2_h10_fbridge_rep pop_exact_h10_fbridge pop_exact_h10_fbridge_rep pop_exact_mid_fbridge pop_exact_mid_fbridge_rep
echo "FBRIDGE_DONE $(date -u +%FT%TZ)" | tee -a "$OUT/stages.txt"
