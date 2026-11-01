#!/bin/bash
# mdp_solve_lithium.sh <alpha> <a_max> <h_max> <d_max> <p_max> <deficit> [own-pending]
# Owner (2026-10-24): run the ~1e8-state exact solve on lithium (31 GB) once its
# round-2 cells are done. Refuses while a sim runs there. Installs numpy in
# lithium's venv if missing, pulls sop-research, runs `sop_mdp.py solve`
# detached with the policy dumped to ~/monerosim/mdp_out/, log alongside.
set -u
alpha=$1; a=$2; h=$3; d=$4; p=$5; dfc=$6; own=${7:-ignore}
ssh -o BatchMode=yes lithium "export FORCE_BESIDE_SIMS=${FORCE_BESIDE_SIMS:-};
  cd ~/monerosim || exit 1
  if [ -z \"\${FORCE_BESIDE_SIMS:-}\" ] && pgrep -f '[s]hadow --parallelism|[s]elfish_matrix' >/dev/null; then echo 'sim running on lithium; not starting the solve (FORCE_BESIDE_SIMS=1 to allow; run memguard_solve_lithium.sh then)'; exit 1; fi
  git pull -q --ff-only && git log --oneline -1
  venv/bin/python -c 'import numpy' 2>/dev/null || venv/bin/pip install -q numpy
  mkdir -p mdp_out
  tag=a${alpha}_${own}_c${a}_${h}_${d}_${p}_${dfc}
  setsid nohup venv/bin/python scripts/sop_mdp.py solve --alpha $alpha --own-pending $own \
    --a-max $a --h-max $h --d-max $d --p-max $p --deficit $dfc --rho-lo 0.05 --rho-hi 0.50 --rho-tol 1e-4 --verbose --out mdp_out/policy_\$tag.json \
    > mdp_out/solve_\$tag.log 2>&1 < /dev/null &
  sleep 5; pgrep -af '[s]op_mdp.py solve' | cut -c1-120; echo \"log: ~/monerosim/mdp_out/solve_\$tag.log\"; free -g | awk '/Mem:/{print \"ram avail \"\$7\" GiB\"}'"
