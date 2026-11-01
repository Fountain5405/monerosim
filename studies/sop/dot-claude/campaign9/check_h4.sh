#!/bin/bash
# Four-honest-miner (N=4) cell check: started? daemons up? both honest agents alive (no hashrate error)?
# SoP armed on every daemon? attacker releases; honest-002's blocks so far.
[ "${1:-}" = "--wait" ] && sleep "${2:-1700}"
box=${3:-lithium}; cell=${4:-share_k6_a047_s1}
timeout 240 ssh -o BatchMode=yes $box "cd ~/monerosim; d=\$(ls -dt archived_runs/2*_sop_v4_window_k6_h4_72h__$cell/ 2>/dev/null | head -1)
[ -n \"\$d\" ] || { echo 'no run dir'; tail -n 5 .claude/campaign9/queue.log; exit 0; }
echo \"run: \$(basename \$d)\"; grep -oE 'Progress: [0-9]+%.*realtime: [0-9:]+' \$d/shadow_run.log | tail -1
echo \"monerod-sim: \$(pgrep -u \$(id -un) -c monerod-sim)  owner monerod: \$(pgrep -u monero -c monerod)  avail GiB: \$(free -g | awk '/Mem:/{print \$7}')\"
for h in honest-001 honest-002 honest-003 honest-004; do
  f=\$(ls -S \$d/shadow.data/hosts/\$h/bash.*.stdout 2>/dev/null | head -1)
  echo \"\$h agent log: \$(basename \"\$f\")  errors: \$(grep -acE 'Traceback|Invalid hashrate|ValueError' \$d/shadow.data/hosts/\$h/*.stdout \$d/shadow.data/hosts/\$h/*.stderr 2>/dev/null | awk -F: '{s+=\$NF} END{print s}')  hashrate line: \$(grep -am1 -oE '.{0,20}hashrate.{0,60}' \"\$f\" 2>/dev/null)\"
  echo \"  \$h blocks found: \$(grep -ac 'Block generated\|block found\|Found block' \"\$f\" 2>/dev/null)\"
done
echo \"SoP armed: \$(for h in \$d/shadow.data/hosts/*/; do grep -rhoam1 --include='*.stdout' -E 'SIM-SoP: weight table armed \([^)]*\)' \$h 2>/dev/null | head -1; done | sort | uniq -c | tr '\n' ' ')\"
a=\$(grep -la SelfishMinerAgent \$d/shadow.data/hosts/attacker-miner/bash.*.stdout 2>/dev/null | head -1)
[ -n \"\$a\" ] && echo \"attacker releases: reveals=\$(grep -a ' - attacker-miner - ' \$a | grep -cE ': reveal fork=') publishes=\$(grep -a ' - attacker-miner - ' \$a | grep -cE ': publish fork=')\""
