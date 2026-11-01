#!/bin/bash
# relaunch_failed.sh: relaunch the one cell per box that lost the cold-cache
# race. Verifies the snapshot cache is warm, clears HALT, removes the failed
# cell's marker JSON (selfish_matrix would otherwise treat the cell as done),
# parks the failed run dir (only a generation log) under archived_runs/_failed/,
# and starts a second run_lane.py for just that cell.
set -u
declare -A SPEC CELL
SPEC[box80]=sop_v4_o5_alpha_72h; CELL[box80]=share_sop2_a033_s1
SPEC[box81]=sop_v4_o5_noown_72h; CELL[box81]=share_sop2_noown_a045_s2
SPEC[box82]=sop_v4_o5_alpha_72h; CELL[box82]=share_sop2_a040_s1
for h in box80 box81 box82; do
  echo "######## $h: ${SPEC[$h]} / ${CELL[$h]} ########"
  ssh -o BatchMode=yes $h "cd ~/monerosim || exit 1
    spec=${SPEC[$h]}; cell=${CELL[$h]}
    echo '--- snapshot cache ---'; ls ~/.monerosim/chain_snapshots/ 2>/dev/null; n=\$(ls ~/.monerosim/chain_snapshots/ 2>/dev/null | wc -l)
    [ \"\$n\" -ge 1 ] || { echo 'cache still cold; not relaunching'; exit 1; }
    echo '--- HALT ---'; cat .claude/campaign9/HALT 2>/dev/null | head -1 | cut -c1-80; rm -f .claude/campaign9/HALT
    echo '--- failed marker ---'; m=matrix_runs/\$spec/cells/\$cell.json; if [ -f \"\$m\" ]; then python3 -c \"import json;d=json.load(open('\$m'));print({k:d.get(k) for k in ('returncode','run_dir','error')})\" | cut -c1-120; rm -f \"\$m\"; echo removed; else echo none; fi
    echo '--- park failed run dir(s) ---'; mkdir -p archived_runs/_failed
    for d in archived_runs/*__\$cell; do [ -d \"\$d\" ] || continue; if [ -d \"\$d/shadow.data\" ]; then echo \"\$d has shadow.data; leaving\"; else du -sh \"\$d\" | cut -f1 | tr '\n' ' '; mv \"\$d\" archived_runs/_failed/ && echo \"parked \$d\"; fi; done
    MONEROSIM_SHADOW_CPU_PINNING=0 setsid nohup venv/bin/python .claude/campaign9/run_lane.py \$spec \$cell >> .claude/campaign9/\$spec.out 2>&1 < /dev/null &
    sleep 5; echo '--- drivers ---'; pgrep -af '[r]un_lane[.]py' | cut -c1-120; tail -1 .claude/campaign9/queue.log"
done
echo "######## waiting 120 s ########"
sleep 120
for h in box80 box81 box82; do
  echo "######## $h ########"
  ssh -o BatchMode=yes $h 'cd ~/monerosim; tail -2 .claude/campaign9/queue.log; ls .claude/campaign9/HALT 2>/dev/null; for d in archived_runs/2*/; do printf "%s: " "$(basename $d)"; grep -oE "Progress: .*" $d/shadow_run.log 2>/dev/null | tail -1 || echo "(no progress line yet)"; done; free -g | awk "/Mem:/{print \"ram used \"\$3\" / \"\$2\" GiB, avail \"\$7}"'
done
