#!/bin/bash
# Runs ON lithium (ssh lithium bash -s < this): prints the pid of the
# sop_rl.py train run to sacrifice first when memory runs out: the
# one-step runs least likely to inform (a045, a048, the one-step a050),
# then the newest run. Prints nothing if no train run exists.
for o in policy_noown_a045.json.gz policy_noown_a048.json.gz policy_noown_a050.json.gz policy_noown_a050_race_bin2.json.gz policy_noown_a050_dbin2.json.gz policy_noown_a050_step.json.gz policy_noown_a050_race.json.gz; do
  p=$(pgrep -f "[s]op_rl.py train.*$o" | head -1)
  [ -n "$p" ] && { echo "$p"; exit 0; }
done
pgrep --newest -f "[s]op_rl.py train"
