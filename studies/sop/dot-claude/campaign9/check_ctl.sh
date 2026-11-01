#!/bin/bash
# check_ctl.sh [--wait S] <box> <cell>: early check of a sop_v4_control_72h cell: progress,
# daemons, SoP armed lines, the third miner's daemon connected (no --offline) and its agent
# on the honest strategy without errors, natural forks so far at honest-001.
[ "${1:-}" = "--wait" ] && { sleep "${2:-1700}"; shift 2; }
box=$1; cell=$2
timeout 240 ssh -o BatchMode=yes $box "cd ~/monerosim; d=\$(ls -dt archived_runs/2*_sop_v4_control_72h__$cell/ 2>/dev/null | head -1)
[ -n \"\$d\" ] || { echo 'no run dir'; exit 0; }
echo \"run: \$(basename \$d)\"; grep -oE 'Progress: [0-9]+%.*realtime: [0-9:]+' \$d/shadow_run.log | tail -1
echo \"daemons: monerod-sim \$(pgrep -u \$(id -un) -c monerod-sim), all monerod-like \$(pgrep -u \$(id -un) -c monerod)  avail GiB: \$(free -g | awk '/Mem:/{print \$7}')\"
echo \"SoP armed: \$(for h in \$d/shadow.data/hosts/*/; do grep -rhoam1 --include='*.stdout' -E 'SIM-SoP: weight table armed \([^)]*\)' \$h 2>/dev/null | head -1; done | sort | uniq -c | tr '\n' ' ')\"
echo \"third miner daemon offline flag: \$(pgrep -u \$(id -un) -a -x monerod-sim | grep 'monero-attacker-miner' | grep -c -- '--offline')\"
a=\$(ls -S \$d/shadow.data/hosts/attacker-miner/bash.*.stdout 2>/dev/null | head -1)
echo \"third miner agent: \$(grep -am1 -oE 'strategy[^,]{0,40}' \$a)  errors: \$(grep -acE 'Traceback|Error' \$a)\"
echo \"honest-001 fork decisions so far: \$(grep -ac 'SIM-SoP-DEC' \$d/shadow.data/hosts/honest-001/monerod-sim.*.stdout 2>/dev/null)\""
