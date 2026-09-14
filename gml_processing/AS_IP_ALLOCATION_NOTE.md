# GML / IP-allocation limit — note for whoever fixes GML production

**Date:** 2026-09-14  ·  **Context:** trying to run a ~2,200-host eclipse
simulation (1,199 benign + 1,000 distinct-/24 attackers + 1 target). Blocked by
an IP-allocator limit. This note records exactly what the limit is, so the fix
can target the right place.

## Symptom
A run on `gml_processing/test_5000_nodes_caida_undirected_selfloops.gml` aborts
at Shadow init — no nodes start, no metrics:
```
Failed to register a host ... addr='127.227.0.10' ... name='relay-124' in the DNS module
loopback address '127.227.0.10' is invalid in DNS
Failed to run the simulation
```
Two hosts were assigned loopback IPs (relay-124 → 127.227.0.10,
relay-2002 → 127.228.0.10). Shadow's DNS rejects loopback, so the whole sim dies.

**GOTCHA:** `run_sim.sh` still exits **0** in this case. Do NOT trust its exit
code — check `<run>/shadow_run.log` for `Failed to run` / `processes failed`.

## Root cause (verified in source)
`src/ip/as_manager.rs` derives each host's IP from its GML node's **`AS`** value:

- **AS 0–1199 → SAFE.** Mapped by region (AS 0-199 NA, 200-499 EU, 500-799 Asia,
  800-999 SA, 1000-1099 Africa, 1100-1199 Oceania) through hardcoded first-octet
  tables (`NA_OCTETS`, `EU_OCTETS`, … at `as_manager.rs:139-162`) that contain
  only non-reserved octets. `get_subnet_base()` (`as_manager.rs:258-329`) walks
  distinct (o1,o2,o3) triples as the AS increases, so **each distinct safe AS
  yields a distinct /24**. Multiple hosts may share one AS (host octet 10–254 →
  same /24, different host) — fine for hosts that don't need /24 diversity.
- **AS ≥ 1200 → UNSAFE fallback** (`as_manager.rs:316-325`):
  `first = 100 + (AS % 50)` → range **100–149**, which INCLUDES:
    - **127** (loopback) whenever `AS % 50 == 27` (e.g. AS 1227, 1277, 1327, …),
    - **100.64–100.127** (CGNAT / RFC 6598) for some second-octet values.
  These get rejected (127.x) or are otherwise reserved.

## Why this bites GML production
`gml_processing/create_caida_connected_with_loops.py` **renumbers `AS`
sequentially to the node id (0…N-1)** (`:338`, `:377`). So any generated GML with
**more than 1,200 nodes** assigns AS 1200…N-1 → hits the unsafe fallback → some
nodes get 127.x → Shadow init fails. **Regenerating a bigger GML the current way
does NOT work.** (The existing 1200-node GML works precisely because its AS
values are 0–1199.)

## Net limit
The allocator can currently produce at most **~1,200 distinct safe /24 subnets**
(AS 0–1199). Total *hosts* can exceed 1,200 (hosts may share a /24), but the
number of **distinct-/24 endpoints** — which the eclipse attack needs for its
attacker fleet (the Monero /24 outbound-diversity filter forces the victim's 12
outbound peers into 12 distinct /24s) — is capped at ~1,200.

## What a fix needs (pick one)
1. **Fix the fallback in `as_manager.rs`** so AS ≥ 1200 also map to distinct,
   non-reserved /24s: extend the safe octet tables and/or make the fallback skip
   every reserved block — 0/8, 10/8, 100.64/10, 127/8, 169.254/16, 172.16/12,
   192.168/16, 224/4, 240/4. Goal: raise the distinct-safe-/24 ceiling well past
   1,200 (need ≥ ~2,300 for the target run).
2. **Or fix the generator** so it assigns `AS` from a known-safe scheme for
   N > 1200 rather than raw sequential ids (still requires the allocator to have
   >1,200 safe /24s, so usually needs (1) too).

## How to verify a fix
- Generate an N>1200 GML, run the small smoke below, and confirm:
  - `grep -E "Assigned .*(127|0|10|169\.254|172\.(1[6-9]|2[0-9]|3[01])|192\.168|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])|22[4-9]|23[0-9]|24[0-9])\." <run>/monerosim.log` returns **nothing**.
  - `<run>/shadow_run.log` shows **no** "Failed to run" and `processes failed: 0`.
- Smoke config that reproduces the failure today (drop it in `test_configs/`,
  expand with `scripts.scenario_parser`, run with `run_sim.sh --no-build
  --no-monitor --no-clean --no-archive`): ~50 agents on the 5,000-node GML,
  `reachable_fraction: 0.0`, a few `relay-{101..140}` + `relay-{2001..2006}` +
  `relay-4000`. It aborts now; it should start cleanly after the fix.

## Where the eclipse work stands (paused)
- Committed configs that DEPEND on this fix:
  `test_configs/eclipse_nyx_full.scenario.yaml` (2,211 hosts, points at the 5k
  GML — will not run until the allocator/GML is fixed, OR until a hand-built GML
  pins the 1,000 attackers to AS 0–999 and shares AS 1000–1199 across benign).
- Configs that already WORK on the 1,200-node GML (no fix needed):
  `eclipse_birth_stability` (963 hosts) and `eclipse_nyx_ceiling` (1,193 hosts,
  ~999 distinct-/24 attackers — captures the Nyx mechanism at attacker scale).
- Nothing is scheduled/armed. The detached launcher
  (`~/monerosim_work/eclipse_reproduction/scheduled/run_both.sh`) was stopped.
