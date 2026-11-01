#!/bin/bash
# check_gamma.sh [--wait S] <box> <cell>: early check of a sop_v4_gamma_72h cell: progress, daemons,
# the bridges' placement (honest-002 + attacker-bridge on 1200/1201, attacker-bridge-2 + honest-001 on 0),
# the attacker's bridge switches ("read bridge -> bridge N"), its releases, and honest-002's blocks so far.
[ "${1:-}" = "--wait" ] && { sleep "${2:-1700}"; shift 2; }
box=$1; cell=$2
timeout 240 ssh -o BatchMode=yes $box "cd ~/monerosim; d=\$(ls -dt archived_runs/2*_sop_v4_gamma_72h__$cell/ 2>/dev/null | head -1)
[ -n \"\$d\" ] || { echo 'no run dir'; exit 0; }
echo \"run: \$(basename \$d)\"; grep -oE 'Progress: [0-9]+%.*realtime: [0-9:]+' \$d/shadow_run.log | tail -1
echo \"monerod-sim: \$(pgrep -u \$(id -un) -c monerod-sim)  avail GiB: \$(free -g | awk '/Mem:/{print \$7}')\"
venv/bin/python - \$d/shadow_agents.yaml <<'PY'
import sys,yaml
h=yaml.safe_load(open(sys.argv[1]))['hosts']
print('placement:', {k: h[k].get('network_node_id') for k in ('honest-001','honest-002','attacker-miner','attacker-bridge','attacker-bridge-2','relay-slow')})
PY
a=\$(grep -la SelfishMinerAgent \$d/shadow.data/hosts/attacker-miner/bash.*.stdout 2>/dev/null | head -1)
[ -n \"\$a\" ] && echo \"attacker: bridge switches=\$(grep -ac 'read bridge ->' \$a) reveals=\$(grep -a ' - attacker-miner - ' \$a | grep -cE ': reveal fork=') publishes=\$(grep -a ' - attacker-miner - ' \$a | grep -cE ': publish fork=') errors=\$(grep -acE 'Traceback|Error' \$a)\"
for h in honest-001 honest-002; do f=\$(ls -S \$d/shadow.data/hosts/\$h/bash.*.stdout 2>/dev/null | head -1); echo \"\$h blocks found: \$(grep -ac 'Block generated\|block found\|Found block' \"\$f\" 2>/dev/null)  errors: \$(grep -acE 'Traceback|Error' \"\$f\" 2>/dev/null)\"; done
echo \"SoP armed: \$(for h in \$d/shadow.data/hosts/*/; do grep -rhoam1 --include='*.stdout' -E 'SIM-SoP: weight table armed \([^)]*\)' \$h 2>/dev/null | head -1; done | sort | uniq -c | tr '\n' ' ')\""
