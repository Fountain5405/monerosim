#!/bin/bash
# mdp_enum_lithium.sh <a> <h> <d> <p> <deficit> [own-pending]: state count on lithium
# (31 GB), detached, logged to ~/monerosim/mdp_out/enum_<caps>.log. Refuses while a sim runs.
set -u
a=$1; h=$2; d=$3; p=$4; dfc=$5; own=${6:-ignore}
ssh -o BatchMode=yes lithium "
  cd ~/monerosim || exit 1
  if pgrep -f '[s]hadow --parallelism|[s]elfish_matrix' >/dev/null; then echo 'sim running on lithium; not starting'; exit 1; fi
  git pull -q --ff-only && git log --oneline -1
  venv/bin/python -c 'import numpy' 2>/dev/null || venv/bin/pip install -q numpy
  mkdir -p mdp_out; tag=c${a}_${h}_${d}_${p}_${dfc}_${own}
  setsid nohup venv/bin/python scripts/sop_mdp.py enumerate --own-pending $own --a-max $a --h-max $h --d-max $d --p-max $p --deficit $dfc --verbose \
    > mdp_out/enum_\$tag.log 2>&1 < /dev/null &
  sleep 5; pgrep -af '[s]op_mdp.py enumerate' | cut -c1-110; echo \"log: ~/monerosim/mdp_out/enum_\$tag.log\"; free -g | awk '/Mem:/{print \"ram avail \"\$7\" GiB\"}'"
