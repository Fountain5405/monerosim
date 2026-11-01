#!/bin/bash
# probe_newboxes.sh: add phantom/lithium to ssh config, confirm login, read the
# handover notes, spec the boxes, check KSM and the protected archive dirs.
# Read-only on the boxes.
set -u
for e in "phantom <phantom-lan-ip>" "lithium <lithium-lan-ip>"; do
  set -- $e
  grep -q "^Host $1\$" ~/.ssh/config || printf "Host %s\n    HostName %s\n    User selfishmining\n    IdentityFile ~/.ssh/id_ed25519\n" $1 $2 >> ~/.ssh/config
done
for h in phantom lithium; do
  echo "################ $h ################"
  timeout 40 ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 $h '
    echo "login: $(whoami)@$(hostname) | $(. /etc/os-release; echo $PRETTY_NAME) | $(uname -r) | sudo=$(sudo -n true 2>/dev/null && echo yes || echo no)"
    lscpu | awk -F: "/^Model name|^CPU\(s\)|^Core\(s\) per socket/{gsub(/^ +/,\"\",\$2); printf \"%s=%s; \", \$1, \$2} END{print \"\"}"
    free -g | awk "/Mem:/{print \"ram_GiB total=\"\$2\" avail=\"\$7} /Swap:/{print \"swap_GiB=\"\$2}"
    df -h / /mnt/ssdpool 2>/dev/null | tail -n +2
    echo "--- KSM ---"; for f in run pages_to_scan sleep_millisecs; do printf "%s=%s " $f $(cat /sys/kernel/mm/ksm/$f); done; echo
    echo "--- protected archive dirs ---"; ls -ld /mnt/ssdpool/monerosim_archives /home/lever65/monerosim_archives 2>&1 | cut -c1-90
    echo "--- owner services (monerod) ---"; pgrep -a monerod | cut -c1-100 | head -3; echo "shadow procs: $(pgrep -c -x shadow)"
    echo "--- tools ---"; for t in gcc cmake cargo python3 git; do printf "%s=%s " $t "$(command -v $t >/dev/null && echo y || echo -)"; done; echo
    echo "--- my home ---"; ls -la ~ | head -8
    echo "--- handover notes ---"; ls -la /srv/lab_handover/ 2>&1'
done
for h in phantom lithium; do
  echo "################ $h handover note ################"
  timeout 20 ssh -o BatchMode=yes $h 'f=$(ls /srv/lab_handover/BOX_HANDOVER_*.md 2>/dev/null | head -1); [ -n "$f" ] && { echo "== $f =="; cat "$f"; } || echo "no handover note found"'
done
