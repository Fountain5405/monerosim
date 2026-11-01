#!/bin/bash
# remote_launch.sh <spec> <cell>...: run on a lane box from the repo root's
# .claude/campaign9/. Refuses if a lane driver is already running (this
# script's own command line never contains the driver name, so pgrep cannot
# match itself), clears a stale HALT, starts run_lane.py detached and unpinned.
set -u
cd "$(dirname "$0")/../.." || exit 1
add=0; if [ "${1:-}" = "--add" ]; then add=1; shift; fi   # --add: a second driver beside a running one (another spec)
spec=$1; shift
running=$(pgrep -f '[r]un_lane[.]py' || true)
if [ -n "$running" ] && [ $add = 0 ]; then echo "lane driver already running (pid $running); use --add for a second spec"; exit 1; fi
[ $add = 1 ] || rm -f .claude/campaign9/HALT
MONEROSIM_SHADOW_CPU_PINNING=0 setsid nohup venv/bin/python .claude/campaign9/run_lane.py "$spec" "$@" \
  >> ".claude/campaign9/$spec.out" 2>&1 < /dev/null &
sleep 4
echo "driver pid: $(pgrep -f '[r]un_lane[.]py' | tr '\n' ' ')"
pgrep -af 'selfish_matrix' | grep -v pgrep | cut -c1-110
tail -2 .claude/campaign9/queue.log
