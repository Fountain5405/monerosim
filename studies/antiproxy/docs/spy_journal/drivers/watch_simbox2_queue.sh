#!/bin/bash
# Exit when simbox2's X0 queue logs a new terminal event (DONE, TRIP, FAIL, STOPPING, EMPTY). An unreachable box is retried, not reported.
pat=' (DONE|TRIP|FAIL|STOPPING|STOPPED|QUEUE EMPTY)'
cnt() { ssh -n -o ConnectTimeout=10 simbox2 "grep -cE '$pat' ~/queue/x0_queue.events" 2>/dev/null; }
base=$1
while :; do
  n=$(cnt) && [ -n "$n" ] && [ "$n" -gt "$base" ] && break
  sleep 120
done
ssh -n simbox2 "grep -E '$pat' ~/queue/x0_queue.events | tail -n +$((base+1)) | head -3"
