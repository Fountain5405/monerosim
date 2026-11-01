#!/bin/bash
# Early check of the window cells (and the stock d2 cell): progress, the SoP settings every
# daemon armed (expect w=16 k=2 / k=6 on 12 daemons), the attacker's window, reveal/publish
# counts (from the attacker AGENT log, a bash.*.stdout), live daemon count and memory.
[ "${1:-}" = "--wait" ] && sleep "${2:-1700}"
check() {  # box spec cell
  timeout 240 ssh -o BatchMode=yes $1 "cd ~/monerosim; d=\$(ls -dt archived_runs/2*_$2__$3/ 2>/dev/null | head -1)
[ -n \"\$d\" ] || { echo 'no run dir yet'; exit 0; }
echo \"run: \$(basename \$d)\"
grep -oE 'Progress: [0-9]+%.*realtime: [0-9:]+' \$d/shadow_run.log 2>/dev/null | tail -1
echo 'SoP armed lines (count x line):'
for h in \$d/shadow.data/hosts/*/; do
  l=\$(grep -rhoam1 --include='*.stdout' --include='*.log' -E 'SIM-SoP: weight table armed \([^)]*\)' \$h 2>/dev/null | head -1)
  [ -n \"\$l\" ] && echo \"\$l\" || echo \"(none on \$(basename \$h))\"
done | sort | uniq -c | sed 's/^/  /'
a=\$(grep -la 'SelfishMinerAgent' \$d/shadow.data/hosts/attacker-miner/bash.*.stdout 2>/dev/null | head -1)
echo 'attacker window settings:'; grep -m3 -oaE '.{0,30}(window_objects|window=)[^ ,)]*.{0,80}' \"\$a\" | cut -c1-200 | sed 's/^/  /'
echo \"reveals=\$(grep -a ' - attacker-miner - ' \"\$a\" | grep -cE ': reveal fork=') publishes=\$(grep -a ' - attacker-miner - ' \"\$a\" | grep -cE ': publish fork=') suppressed_lines=\$(grep -ac 'suppress' \"\$a\")\"
echo \"monerod-sim procs: \$(pgrep -u \$(id -un) -c monerod-sim)  avail GiB: \$(free -g | awk '/Mem:/{print \$7}')  load: \$(cut -d' ' -f1 /proc/loadavg)\""
}
for x in "box80 sop_v4_window_72h share_k2_a047_s1" "box81 sop_v4_window_72h share_k2_a047_s2" \
         "box82 sop_v4_window_72h share_k6_a047_s1" "phantom sop_v4_window_72h share_k6_a047_s2" \
         "lithium sop_v4_stock_d2_72h share_stockd2_a038_s1"; do
  set -- $x; echo "######## $1 $3"; check $1 $2 $3
done
