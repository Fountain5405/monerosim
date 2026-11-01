#!/usr/bin/env bash
# Pull monitor outputs (poll_node.py directories) from the owner nodes.
# Monitor outputs hold mainnet addresses and live under ~/monerosim_local
# only, never in the repo.
#
# Usage: collect_monitors.sh <hosts-file> [dest-root]
#   hosts-file: one monitor per line: <name> <ssh-target> <remote-dir>
#               (blank lines and # comments skipped)
#   dest-root:  default $HOME/monerosim_local/monitors
set -u

if [ $# -lt 1 ]; then
    echo "usage: $0 <hosts-file> [dest-root]" >&2
    exit 2
fi
hosts=$1
root=${2:-$HOME/monerosim_local/monitors}
fail=0

while read -r name target remote _; do
    case "$name" in ''|'#'*) continue ;; esac
    dest="$root/$name"
    mkdir -p "$dest"
    rsync -az --partial -e ssh "$target:$remote/" "$dest/"
    rc=$?
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $name rsync exit=$rc"
    [ "$rc" -ne 0 ] && fail=1
done < "$hosts"

exit "$fail"
