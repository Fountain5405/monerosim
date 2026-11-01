#!/bin/bash
# Runs ON a lane box: rebuild ONLY monerod-sim (setup.sh's install_sim_monerod steps) without
# touching the monerod / monero-wallet-rpc binaries running lanes use. Reuses the existing
# worktree ~/.monerosim/build/monero-sim and its build/ dir (incremental), applies the six
# patches on the pinned ref, make -j${BUILD_JOBS:-3} daemon, then installs by rename (running
# daemons keep the old inode) and writes the provenance file like setup.sh. Log: ~/simbin_build.log
set -eu
R=~/monerosim; W=~/.monerosim/build/monero-sim; BIN=~/.monerosim/bin
PIN=$(cat $R/monero.pin)
PATCHES="monero-fakechain-hardforks monero-sim-mining monero-sim-selfish-relay monero-sim-peerlist-dump monero-sim-pop monero-sim-tail-emission"
cd $W
git checkout -q -- . ; git clean -qfd -e build
git checkout -q --detach "$PIN"
for p in $PATCHES; do git apply --check $R/patches/$p.patch; git apply $R/patches/$p.patch; echo "applied $p"; done
cd build/release
nice -n10 make -j${BUILD_JOBS:-3} daemon 2>&1 | tail -n 3
install -m 755 bin/monerod $BIN/monerod-sim.new
mv -f $BIN/monerod-sim.new $BIN/monerod-sim
{ echo "binary: $BIN/monerod-sim"; echo "base: $PIN (monero.pin)"
  for p in $PATCHES; do echo "patch: patches/$p.patch"; echo "patch_sha256: $(sha256sum $R/patches/$p.patch | cut -d' ' -f1)"; done
  echo "built: $(date -u +%FT%TZ)"; echo "builder: simbin_build.sh (setup.sh steps, sim binary only)"; } > $BIN/monerod-sim.provenance
for f in sim-no-drop-score sim-sop-seen-at-notify; do $BIN/monerod-sim --help 2>/dev/null | grep -q -- "--$f" && echo "flag $f: present" || echo "flag $f: MISSING"; done
echo SIMBIN_EXIT=0
