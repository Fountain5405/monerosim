#!/bin/bash
# Knob smoke gate on a sop_knob_smoke run (on lithium): per SoP daemon, the startup mode line,
# the number of "first seen at notify" lines, exceptions; the run's check verdict line.
# Usage: knob_gate.sh <cell>
cell=$1
timeout 300 ssh -o BatchMode=yes lithium "cd ~/monerosim; d=\$(ls -dt archived_runs/2*_sop_knob_smoke__$cell/ | head -1); echo \"run: \$(basename \$d)\"
grep -oE 'Progress: [0-9]+%.*realtime: [0-9:]+' \$d/shadow_run.log | tail -1
for h in \$(ls \$d/shadow.data/hosts); do f=\$(ls -S \$d/shadow.data/hosts/\$h/monerod*.stdout 2>/dev/null | head -1); [ -n \"\$f\" ] || continue
  mode=\$(grep -a -m1 -oE 'first-seen stamped at [^(]*' \$f); n=\$(grep -a -c 'first seen at notify' \$f); ex=\$(grep -a -ciE 'exception|terminate called|Segmentation' \$f)
  printf '%-18s mode=[%s] notify_lines=%s exceptions=%s\n' \$h \"\$mode\" \$n \$ex; done
grep -h ' check ' .claude/campaign9/queue.log | grep sop_knob_smoke | tail -n 2 | cut -c1-230"
