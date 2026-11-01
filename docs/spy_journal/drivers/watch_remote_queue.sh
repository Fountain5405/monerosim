#!/bin/bash
# Exit when a remote box's X0 queue logs a new terminal event (DONE, TRIP, FAIL, STOPPING, EMPTY).
# Usage: watch_remote_queue.sh <ssh-host> <terminal-event-count-at-launch>. An unreachable box is retried, not reported.
pat=' (DONE|TRIP|FAIL|STOPPING|STOPPED|QUEUE EMPTY)'
host=$1; base=$2
cnt() { ssh -n -o ConnectTimeout=10 "$host" "grep -cE '$pat' ~/queue/x0_queue.events" 2>/dev/null; }
while :; do
  n=$(cnt) && [ -n "$n" ] && [ "$n" -gt "$base" ] && break
  sleep 120
done
ssh -n "$host" "grep -E '$pat' ~/queue/x0_queue.events | tail -n +$((base+1)) | head -3"
