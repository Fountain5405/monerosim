#!/bin/bash
# Stop the campaign-8 queue the moment stage B2 starts (B1 done by then).
LOG=.claude/campaign8/queue.log
until grep -q "== stage B2" "$LOG"; do
  kill -0 946551 2>/dev/null || { echo "queue gone before B2"; exit 1; }
  sleep 2
done
date -u; echo "B2 started; killing queue group 946551"
kill -TERM -- -946551
sleep 15
pkill -TERM -f "shadow .*(long_depth__share_sop2_a033_d5|long_depth_rep__)" && echo "killed stray B2 shadow"
sleep 5
ps -eo pid,pgid,args | grep -E "run_queue|selfish_matrix|run_sim.sh|bin/shadow " | grep -v grep
echo "watcher done"
