#!/bin/bash
# Fix-up: restore the local patch from git, regenerate from the lithium worktree against the
# pre-pop COMMIT HASH (committed "pop" + working-tree edits), dry-run the full series in a
# throwaway worktree, fetch the patch here, report lithium's lane state.
set -u
cd /home/selfishmining/monerosim && git checkout -- patches/monero-sim-pop.patch && echo "local patch restored: $(wc -l < patches/monero-sim-pop.patch) lines"
timeout 600 ssh -o BatchMode=yes lithium 'set -e
cd ~/.monerosim/build/monero-knob
echo "worktree status:"; git status --short | head -6
PRE=$(git log --format=%H --grep=^pre-pop$ -n 1); echo "pre-pop commit: ${PRE:0:9}"
git diff $PRE > ~/monerosim/patches/monero-sim-pop.patch
echo "new patch: $(wc -l < ~/monerosim/patches/monero-sim-pop.patch) lines, $(grep -c "^diff --git" ~/monerosim/patches/monero-sim-pop.patch) files"
grep -c "sim_sop_seen_at_notify\|sim-sop-seen-at-notify" ~/monerosim/patches/monero-sim-pop.patch | sed "s/^/knob mentions in patch: /"
# dry-run the whole series on a clean throwaway worktree at the pin, as setup.sh will
M=~/monerosim/sibling_repos/monero; T=~/.monerosim/build/monero-knob-check
rm -rf $T; git -C $M worktree prune; git -C $M worktree add --detach $T $(cat ~/monerosim/monero.pin) >/dev/null 2>&1
cd $T
for p in monero-fakechain-hardforks monero-sim-mining monero-sim-selfish-relay monero-sim-peerlist-dump monero-sim-pop monero-sim-tail-emission; do git apply --check ~/monerosim/patches/$p.patch && git apply ~/monerosim/patches/$p.patch && echo "series: $p ok"; done
cd ~; git -C $M worktree remove --force $T
me=$(id -un)
echo "lithium: shadow $(pgrep -u $me -c -x shadow) lane $(pgrep -u $me -f "[r]un_lane.py" | wc -l) avail GiB $(free -g | awk "/Mem:/{print \$7}")"
tail -n 1 ~/monerosim/.claude/campaign9/queue.log | cut -c1-120'
scp -q lithium:monerosim/patches/monero-sim-pop.patch /home/selfishmining/monerosim/patches/monero-sim-pop.patch && echo "patch fetched to control box"
cd /home/selfishmining/monerosim && git diff --stat patches/ | tail -n 1
