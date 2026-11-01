#!/bin/bash
# Regenerate patches/monero-sim-pop.patch from the lithium worktree (diff against "pre-pop"),
# install it into lithium's repo copy, fetch it here, and if no lane runs on lithium start the
# official build (yes "" | ./setup.sh --sim-binary, detached, log ~/setup.log).
set -u
timeout 300 ssh -o BatchMode=yes lithium 'set -e
cd ~/.monerosim/build/monero-knob
git diff pre-pop > ~/monerosim/patches/monero-sim-pop.patch
echo "new patch: $(wc -l < ~/monerosim/patches/monero-sim-pop.patch) lines, $(grep -c "^diff --git" ~/monerosim/patches/monero-sim-pop.patch) files"
# dry-run the whole series on a clean checkout of the pin, as setup.sh will
git reset -q --hard pre-pop; git checkout -q --detach $(cat ~/monerosim/monero.pin); git reset -q --hard; git clean -qfd
for p in monero-fakechain-hardforks monero-sim-mining monero-sim-selfish-relay monero-sim-peerlist-dump monero-sim-pop monero-sim-tail-emission; do git apply --check ~/monerosim/patches/$p.patch && git apply ~/monerosim/patches/$p.patch && echo "series: $p ok"; done
git reset -q --hard; git clean -qfd
me=$(id -un)
echo "lithium: shadow $(pgrep -u $me -c -x shadow) lane $(pgrep -u $me -f "[r]un_lane.py" | wc -l) avail GiB $(free -g | awk "/Mem:/{print \$7}")"
tail -n 1 ~/monerosim/.claude/campaign9/queue.log | cut -c1-120'
scp -q lithium:monerosim/patches/monero-sim-pop.patch /home/selfishmining/monerosim/patches/monero-sim-pop.patch && echo "patch fetched to control box"
cd /home/selfishmining/monerosim && git diff --stat patches/ | tail -n 1
