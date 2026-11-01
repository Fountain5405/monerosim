#!/bin/bash
# deploy_lane.sh <box>: push specs + campaign9 drivers + campaign8 dep to a lane
# box, enable KSM like tr, verify the install, dry-run the specs. No sims started.
set -u
h=$1
S=/home/selfishmining/monerosim/.claude/campaign9
R=/home/selfishmining/monerosim
echo "######## $h ########"
ssh -o BatchMode=yes $h 'mkdir -p ~/monerosim/.claude/campaign9 ~/monerosim/.claude/campaign8' || exit 1
scp -q $R/test_configs/matrix/sop_v4_o5_alpha_72h.yaml $R/test_configs/matrix/sop_v4_o5_noown_72h.yaml $h:monerosim/test_configs/matrix/ || exit 1
scp -q $S/run_lane.py $S/check_run.py $S/status.py $h:monerosim/.claude/campaign9/ || exit 1
scp -q /home/selfishmining/monerosim/.claude/campaign8/embed_check.py $h:monerosim/.claude/campaign8/ || exit 1
ssh -o BatchMode=yes $h '
cd ~/monerosim || exit 1
echo "--- KSM (repo ksm_check recommendation; persisted via tmpfiles) ---"
printf "w /sys/kernel/mm/ksm/pages_to_scan - - - - 20000\nw /sys/kernel/mm/ksm/sleep_millisecs - - - - 20\nw /sys/kernel/mm/ksm/run - - - - 1\n" | sudo -n tee /etc/tmpfiles.d/monerosim-ksm.conf >/dev/null && sudo -n systemd-tmpfiles --create /etc/tmpfiles.d/monerosim-ksm.conf
bash scripts/ksm_check.sh 2>&1 | tail -2; echo "ksm_check rc=${PIPESTATUS[0]}"
echo "--- fs ---"; echo "/tmp on: $(findmnt -no FSTYPE,SOURCE -T /tmp)"; df -h / | tail -1
echo "--- install ---"; ls ~/.monerosim/bin/ | tr "\n" " "; echo
~/.monerosim/bin/shadow --version 2>&1 | head -1; cat ~/.monerosim/SHADOWFORMONERO_VERSION 2>/dev/null
~/.monerosim/bin/monerod-sim --version 2>&1 | head -1; head -3 ~/.monerosim/bin/monerod-sim.provenance 2>/dev/null
venv/bin/python --version; ls -la target/release/monerosim | cut -c1-60; ls ~/.monerosim/calibration.json
echo "--- warm the chain-snapshot cache (two cold lanes race on it) ---"
venv/bin/python scripts/chain_snapshot.py build-template --preset chain_snapshots/h10 2>&1 | tail -1; ls ~/.monerosim/chain_snapshots/
echo "--- dry-runs ---"
venv/bin/python scripts/selfish_matrix.py test_configs/matrix/sop_v4_smoke.yaml --dry-run 2>&1 | tail -1
venv/bin/python scripts/selfish_matrix.py test_configs/matrix/sop_v4_o5_alpha_72h.yaml --dry-run 2>&1 | tail -1
venv/bin/python scripts/selfish_matrix.py test_configs/matrix/sop_v4_o5_noown_72h.yaml --dry-run 2>&1 | tail -1
echo "--- tests ---"; venv/bin/python -m pytest -q scripts/test_selfish_matrix.py 2>&1 | tail -1
'
