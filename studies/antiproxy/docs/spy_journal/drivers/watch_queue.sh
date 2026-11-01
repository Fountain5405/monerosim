#!/bin/bash
# Exit when the local X0 queue logs its next terminal event (DONE, TRIP, FAIL, STOPPING, EMPTY).
EV=/tmp/claude-1002/-home-lever65-monerosim/df57b8d8-00c1-4e9b-8f85-c70f598c44e3/scratchpad/x0_queue.events
pat=' (DONE|TRIP|FAIL|STOPPING|STOPPED|QUEUE EMPTY)'
base=$(grep -cE "$pat" "$EV")
while [ "$(grep -cE "$pat" "$EV")" -le "$base" ]; do sleep 60; done
tail -n +"$((base+1))" <(grep -E "$pat" "$EV") | head -3
