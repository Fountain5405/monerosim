#!/bin/bash
# watch_mdpcheck.sh [hours=12]: exit when both solver cross-check queues on lithium
# (~/mdpcheck/run_{sop,btc}.log) say "done", or a run exits non-zero, or after <hours>.
end=$((SECONDS + ${1:-12}*3600))
while [ $SECONDS -lt $end ]; do
  sleep 300
  s=$(timeout 40 ssh -o BatchMode=yes lithium 'cd ~/mdpcheck; echo "done=$(cat run_btc2.log run_btc_bigT.log 2>/dev/null | grep -c "queue .* done") bad=$(cat run_btc2.log run_btc_bigT.log 2>/dev/null | grep -E "exit [1-9]" | wc -l) lines=$(cat results_*.jsonl 2>/dev/null | wc -l)"') || continue
  case $s in *bad=[1-9]*) echo "$(date -u +%FT%TZ) a run failed: $s"; exit 0 ;; esac
  case $s in *done=2*) echo "$(date -u +%FT%TZ) both queues done: $s"; exit 0 ;; esac
done
echo "watch_mdpcheck timed out"
