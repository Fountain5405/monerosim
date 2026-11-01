#!/bin/bash
# Daily pull of the Monero P2P Observatory's aggregate feeds (observer.monerodevs.org,
# a Grafana dashboard on three hardcoded mainnet seeds; owner flagged it 2026-10-28).
# The feed host is discovered from the dashboard definition at run time, so no address is
# written here. Snapshots go to $DEST/YYYYMMDD/ (default ~/monerosim_local/observer), outside
# the repo. Only aggregate feeds are pulled: geo_points / fp8 (address-bearing) are left out.
# Read with studies/antiproxy/docs/spy_journal/adhoc/observer_seed_ratio.py. Cron: 0 6 * * * (UTC) on the control box.
set -u
DASH=${OBSERVER_DASH:-https://observer.monerodevs.org/api/dashboards/uid/p2pobs}
DEST=${1:-$HOME/monerosim_local/observer}
FEEDS="seed_fleet_hist seed_fleet_now outbound_share_hist white_share_hist estimates_history
daily_stats fp8_hist fleet_split_hist fpentities_hist diversity_hist asn_shares lists_fig
surveillance timeseries fp_headline gray_share_hist poison_history poison_gf_history
unreach_top_hist ff_parity ff_hist height_history serve_health_hist rpc_access_hist"
day=$(date -u +%Y%m%d); out="$DEST/$day"; mkdir -p "$out" || exit 1
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$DEST/pull.log"; }
base=$(curl -s --max-time 30 "$DASH" | grep -oE 'http://[^"]+:[0-9]+/[a-z0-9_]+\.json' | head -1 | sed 's#/[a-z0-9_]*\.json$##')
[ -z "$base" ] && { log "FAIL: no feed base found in the dashboard definition"; exit 1; }
fail=0
for f in $FEEDS; do
  code=$(curl -s --max-time 60 -o "$out/$f.json" -w '%{http_code}' "$base/$f.json")
  if [ "$code" != 200 ] || ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$out/$f.json" 2>/dev/null; then
    rm -f "$out/$f.json"; fail=$((fail + 1)); log "miss $f http=$code"
  fi
done
log "pulled $(ls "$out" | wc -l) feeds into $out, $fail missing"
[ "$fail" -eq 0 ]
