#!/bin/bash
# Group "dropping connection"/ban/score lines per node for one run: whole run, plus the 2000-01-08 19:3x window.
R=$1
for f in $R/daemon_logs/monero-*/bitmonero.log; do
  n=$(basename $(dirname $f)); n=${n#monero-}
  grep -aE 'dropping connection|Host [0-9.]+ blocked|Claims [0-9]+, claimed|Negative score|Sent invalid chain|sent wrong block' $f \
   | awk -F'\t' '{m=$NF; gsub(/\[[0-9.]+:[0-9]+ (INC|OUT)\] /,"",m); gsub(/Host [0-9.]+/,"Host X",m); gsub(/Claims [0-9]+, claimed [0-9]+/,"Claims N, claimed M",m); gsub(/block: [0-9a-f]+/,"block: ...",m); print substr($1,1,13) "|" m}' \
   | sort | uniq -c | awk -v n=$n '{print n " " $0}'
done
