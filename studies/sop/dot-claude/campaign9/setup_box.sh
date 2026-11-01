#!/bin/bash
# setup_box.sh <box>...: fresh clone of sop-research into ~/monerosim and a
# detached `yes "" | ./setup.sh --sim-binary` (every default: proceed, install
# Shadow, skip the test sim). Log: ~/setup.log, ends with SETUP_EXIT=<rc>
# (2 = the closing KSM advisory, not a failure).
set -u
for h in "$@"; do
  echo "=== $h ==="
  ssh -o BatchMode=yes $h '
    set -e
    if [ ! -d ~/monerosim/.git ]; then git clone -q --branch sop-research https://github.com/Fountain5405/monerosim.git ~/monerosim; fi
    cd ~/monerosim && git log -1 --format="repo at %h (%D)"
    if pgrep -f "[s]etup[.]sh --sim" | grep -vx "$$" | grep -q .; then echo "setup.sh already running"; exit 0; fi
    setsid nohup bash -c "cd ~/monerosim && yes \"\" | ./setup.sh --sim-binary; echo SETUP_EXIT=\$? >> ~/setup.log" > ~/setup.log 2>&1 < /dev/null &
    sleep 3; pgrep -f "[s]etup.sh" >/dev/null && echo "setup.sh running" || echo "NOT RUNNING"'
done
