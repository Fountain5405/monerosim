#!/bin/bash
# Exit when the release-upgrade script on simbox3 has ended (or the box is unreachable for 20 minutes).
miss=0
while :; do
  out=$(ssh -n -o ConnectTimeout=10 simbox3 'pgrep -f "[r]elup.sh|[d]o-release-upgrade|[a]pt-get|[d]pkg" | wc -l; grep -c "RELUP EXIT" ~/relupgrade.log' 2>/dev/null) && { miss=0; set -- $out; [ "$1" = "0" ] && break; } || miss=$((miss+1))
  [ $miss -ge 10 ] && break
  sleep 120
done
date +%H:%M; ssh -n simbox3 'tail -6 ~/relupgrade.log | cut -c1-180; . /etc/os-release; echo "$PRETTY_NAME"; uname -r; ls /var/run/reboot-required 2>&1 | head -1' 2>&1
