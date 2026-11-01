#!/bin/bash
# Usage: watch_crossing_simbox3.sh <run-dir-glob-fragment> [height]   e.g.  h71_k1_w18h_fx 2130
# Wait until the miner log of simbox3's running cell matching the fragment shows HEIGHT >= <height> (default 2130),
# then print the miner's HEIGHT 2112 time, the last 40 memory samples (sim_s, summed RSS, free RAM, swap) and the
# lowest free RAM the 20 s driver log saw since the crossing. Key on the chain height: block 2112 came at sim 20.4 h in one
# cell and about 21.4 h in another.
frag=$1; target=${2:-2130}
log="\$(ls /tmp/monerosim-*${frag}*/monero-miner-001/bitmonero.log | head -1)"
h() { ssh -n -o ConnectTimeout=10 simbox3 "grep -h HEIGHT $log | tail -1 | grep -oP 'HEIGHT \K[0-9]+'" 2>/dev/null; }
while :; do
  n=$(h); [ -n "$n" ] && [ "$n" -ge "$target" ] && break
  sleep 60
done
ssh -n simbox3 "grep -h 'HEIGHT 2112' $log | cut -c1-30"
ssh -n simbox3 "f=\$(ls -d ~/monerosim_archives/*${frag}*)/memory_samples.csv; awk -F, 'NR>1 {printf \"%s sim_s=%s rss_sum_mb=%s avail_mb=%s swap_mb=%s\n\", \$1,\$3,\$9,\$12,\$14}' \$f | tail -60 | awk 'NR%2==1'"
