#!/bin/bash
# setup_pool_keys.sh: let each lane box rsync to the archive pool on tr as lever65.
# For each box: make an ed25519 key if absent, add `Host tr` to its ssh config,
# trust tr's host key, append its public key to lever65@tr's authorized_keys
# (once), then test a BatchMode login and a write into <pool>/<hostname>/.
set -u
POOL=/spinny/readfrom/20261024_monerosim_research_effort
TR_IP=<tr-lan-ip>
S=/home/selfishmining/monerosim/.claude/campaign9
for h in "${@:-box80 box81 box82}"; do
  echo "######## $h ########"
  pub=$(ssh -o BatchMode=yes $h "
    [ -f ~/.ssh/id_ed25519 ] || ssh-keygen -q -t ed25519 -N '' -f ~/.ssh/id_ed25519 -C \"\$(whoami)@\$(hostname) pool-sync\"
    grep -q '^Host tr\$' ~/.ssh/config 2>/dev/null || printf 'Host tr\n    HostName $TR_IP\n    User lever65\n    IdentityFile ~/.ssh/id_ed25519\n' >> ~/.ssh/config
    chmod 600 ~/.ssh/config
    ssh-keygen -F $TR_IP >/dev/null 2>&1 || ssh-keyscan -t ed25519 $TR_IP >> ~/.ssh/known_hosts 2>/dev/null
    cat ~/.ssh/id_ed25519.pub") || { echo "key step failed on $h"; continue; }
  echo "pubkey: ${pub:0:30}... ${pub##* }"
  ssh -o BatchMode=yes tr "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && (grep -qF '$pub' ~/.ssh/authorized_keys || echo '$pub' >> ~/.ssh/authorized_keys) && echo authorized-on-tr" || { echo "authorize step failed for $h"; continue; }
  ssh -o BatchMode=yes $h "H=\$(hostname); timeout 25 ssh -o BatchMode=yes tr \"mkdir -p $POOL/\$H && touch $POOL/\$H/.sync_test && rm $POOL/\$H/.sync_test && echo pool-write-ok-from-\$H\" || echo pool-write-FAILED-from-\$H"
done
echo "######## driver syntax ########"
python3 -m py_compile $S/run_lane.py && echo "run_lane.py compiles"
echo "######## pool as seen from the control box (ro NFS) ########"
ls -la /mnt/remote_spinny/20261024_monerosim_research_effort/
