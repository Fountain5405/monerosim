#!/bin/bash
# Runs ON a stressnet box: read the testnet monerod logs read-only (sudo -n, oldest first) and
# parse block events into /tmp/stressnet_<host>.tsv (owned by me). Usage: stressnet_run.sh <logdir>
D=$1; H=$(hostname)
echo "host $H tz $(date +%Z) logdir $D"
sudo -n ls -1tr "$D" | grep -E '^bitmonero' > /tmp/stressnet_files_$H.txt
echo "log files: $(wc -l < /tmp/stressnet_files_$H.txt) ($(head -1 /tmp/stressnet_files_$H.txt) .. $(tail -1 /tmp/stressnet_files_$H.txt))"
sudo -n du -ch $(sed "s#^#$D/#" /tmp/stressnet_files_$H.txt) 2>/dev/null | tail -1
while read f; do sudo -n nice -n19 ionice -c3 cat "$D/$f"; done < /tmp/stressnet_files_$H.txt \
  | nice -n19 python3 /tmp/stressnet_parse.py /tmp/stressnet_$H.tsv
awk -F'\t' '{c[$1]++} END {for (k in c) printf "%s=%d ", k, c[k]; print ""}' /tmp/stressnet_$H.tsv
awk -F'\t' '$1=="main"{print $4}' /tmp/stressnet_$H.tsv | sort -n | sed -n '1p;$p' | while read t; do date -u -d @$((t/1000)) +%FT%TZ; done | paste -sd' ' | sed 's/^/main blocks span: /'
