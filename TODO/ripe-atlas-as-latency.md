# TODO: AS-to-AS Latency Data from RIPE Atlas

## Goal

Replace synthetic region-based latencies in our GML topology with real AS-to-AS latency measurements from RIPE Atlas. This would significantly improve simulation realism.

## Current State

We currently use hardcoded latencies based on AS relationship type:
- Peer-peer: 10ms
- Customer-provider: 50ms
- Sibling: 5ms
- Default: 20ms

This results in unrealistic inter-continental latencies (20-60ms simulated vs 100-350ms real).

## Why AS-to-AS is Better

Region-to-region latencies are a rough approximation. Real AS-to-AS latencies would capture:
- Actual peering relationships and IXP locations
- Tier-1 transit provider routing
- Geographic placement of specific networks
- Congestion and path inflation

## RIPE Atlas Data Access Options

### Option 1: RIPE Atlas REST API

```bash
# Install Python tools
pip install ripe.atlas.cousteau ripe.atlas.sagan

# Query ping/traceroute measurements
curl "https://atlas.ripe.net/api/v2/measurements/{measurement_id}/results/" \
  -H "Authorization: Key YOUR_API_KEY"
```

**Pros:** Direct access, can filter by ASN
**Cons:** Rate limited, need to iterate through many measurements

### Option 2: Google BigQuery (Recommended for Bulk)

RIPE Atlas data is available in Google BigQuery under project `ripencc-atlas`.

```sql
-- Get inter-AS latency from traceroutes
SELECT
  prb_asn_v4 as source_asn,
  dst_asn as dest_asn,
  MIN(min_rtt) as min_latency_ms,
  COUNT(*) as sample_count
FROM `ripencc-atlas.measurements.traceroute`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND prb_asn_v4 IS NOT NULL
  AND dst_asn IS NOT NULL
GROUP BY source_asn, dest_asn
HAVING sample_count > 10
```

**Pros:** Fast SQL queries over 66TB+ of data, can aggregate by ASN
**Cons:** Requires Google Cloud account, may have query costs

### Option 3: Daily Data Archives (Status Unknown)

Documented at `https://ftp.ripe.net/ripe/atlas/data/` but returned 404 as of January 2026.

File format was: `$TYPE-$IPV-$SUBTYPE-$DATE.bz2`
- TYPE: traceroute, ping, dns, ntp, http, sslcert
- IPV: v4 or v6
- SUBTYPE: builtin or udm
- Each .bz2 contains a .txt with one JSON measurement result per line
- ~25GB per day total

### Option 4: Inter-AS Latency Dataset (minRTT)

RIPE created an aggregate dataset with minimum RTT from each probe to each ASN per day.
- Available via Google Cloud Platform
- ~500MB per day uncompressed
- Aggregated by ASN and IXP peering LANs

Reference: https://labs.ripe.net/author/emileaben/latency-into-your-network-as-seen-from-ripe-atlas/

## Implementation Plan

1. **Get RIPE Atlas API Key**
   - Create account at https://atlas.ripe.net/
   - Generate API key in account settings

2. **Set up BigQuery Access**
   - Link RIPE account to Google Cloud
   - Add `ripencc-atlas` project as dataset

3. **Build AS-to-AS Latency Matrix**
   ```python
   # Query structure
   SELECT source_asn, dest_asn, percentile_cont(rtt, 0.5) as median_rtt
   FROM measurements
   GROUP BY source_asn, dest_asn
   ```

4. **Create Lookup Table**
   - Map our remapped AS numbers (0-1199) to real AS numbers
   - Or use geographic aggregation if direct mapping unavailable

5. **Update GML Generator**
   - Load latency matrix
   - Apply measured latencies to edges
   - Fall back to region-based estimates for missing pairs

## Resources

- RIPE Atlas: https://atlas.ripe.net/
- REST API Docs: https://atlas.ripe.net/docs/apis/rest-api-reference/
- BigQuery Integration: https://github.com/RIPE-NCC/ripe-atlas-bigquery
- Python Library: https://ripe-atlas-cousteau.readthedocs.io/
- Built-in Measurements: https://atlas.ripe.net/docs/built-in-measurements/

## Priority

Medium - Current region-based approach is acceptable for initial simulations, but AS-to-AS data would significantly improve realism for research publications.
