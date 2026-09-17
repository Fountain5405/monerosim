# GML / IP-allocation limit — note for whoever fixes GML production

> **RESOLVED 2026-09-14** — fix (1) below was applied in `src/ip/as_manager.rs`:
> the AS ≥ 1200 fallback now cycles the union of the six region octet tables
> (84 routable RIR first octets) with the third octet pinned to ≥ 1, so every AS
> gets a distinct, non-reserved /24 (84·256·255 ≈ 5.5M of them) that cannot
> collide with the AS 0–1199 /24s (third octet 0). Regression tests:
> `subnets_beyond_region_tables_avoid_reserved_ranges` and
> `subnets_are_distinct_across_large_as_range` (AS 0..=10000).
>
> The generator needed no change: sequential `AS` = node id is now safe for any N.
> Regenerated `gml_processing/5000_nodes_caida_with_loops.gml` (5,000 nodes,
> 72,586 edges, AS 0–4999) with it; the old
> `test_5000_nodes_caida_undirected_selfloops.gml` (raw/garbled CAIDA AS values,
> undirected) is superseded and `eclipse_nyx_full.scenario.yaml` now points at
> the new file.
>
> Verified with `test_configs/eclipse_ipalloc_5k_smoke.scenario.yaml` (51 hosts
> on the new 5k GML, 32 of them on AS ≥ 1200): every host got a distinct /24,
> the reserved-range grep below matched nothing, and Shadow started with
> `processes failed: 0`, ran its full 8 sim-min to "Shadow completed successfully"
> in 18m54s wall, and the target (relay-4000) handshaked with peers on fallback
> /24s such as 59.10.1.10 and 79.35.1.10 (run
> `archived_runs/20260914_215237_eclipse_ipalloc_5k_smoke.expanded`).
> Caveat: bootstrap on the 5k topology is slow (~1 sim-min per 10 wall-min for
> 51 light hosts) — budget accordingly for `eclipse_nyx_full`.

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

---

## FOLLOW-UP 2026-09-14 — NEW blocker found while testing the fix: memory blowup at ~2,200 hosts

The IP-allocator fix above is confirmed working at scale (a 2,211-host
`eclipse_nyx_full` run got past Shadow init: `relay-4000` = 177.13.1.10, all IPs
valid, zero reserved/loopback, no DNS abort). **But the run OOMs the box almost
immediately at Shadow startup**, distinct from the IP bug:

- `memory_samples.csv` at T+3s: `system_free_mb ~1,004,950` (≈1,005 GB free),
  `shadow_rss_mb 43`, `monerod_rss 0` — i.e. essentially idle, Shadow just
  starting, only ~20 processes up (miners+seeds+target+first wave), sim-time ~1s.
- Within **seconds** after that, available memory collapsed and the OOM guard
  killed the run. This is NOT onboarding (batched; benign don't start until 10s+
  and only the first tiny attacker wave is up at t=1s) and NOT the IP path.
- For contrast, a 963-host run on the 1,200-node GML grows memory *gradually*
  (~0.28 GB/host over the onboarding window) and never spikes at init.

**So there is a fast, large memory allocation at Shadow init that scales with
host count (963 fine, ~2,218 explodes) and/or with the 5,000-node directed
topology.** A 51-host smoke on the same 5k GML was fine, so it tracks host count,
not raw GML size. Hypotheses to check (scale/Shadow domain):
- Shadow per-host-pair or per-host init structures scaling super-linearly at
  ~2k hosts (O(hosts^2)?), possibly interacting with `process_threads: 128` and
  256 worker threads.
- Whether a right-sized topology (~2,300-node GML instead of 5,000) or fewer
  worker/process threads changes the init footprint.

**Practical ceiling right now:** ~2,200 hosts does not start on this 1 TB box.
The largest *known-good* eclipse runs remain ≤ ~1,200 hosts
(`eclipse_nyx_ceiling` at 1,193 works; the 963-host Moros paper-scale worked).
Finding the real host ceiling (binary-search between ~1,200 and ~2,200) or fixing
the init-time allocation is the next scale task.

---

## FOLLOW-UP 2 (2026-09-14, later) — the "memory blowup" does NOT reproduce; it was almost certainly a false-positive task kill

Re-tested the same 2,212-host `eclipse_nyx_full.expanded.yaml` (5k GML) with the
run confined to a systemd cgroup (`systemd-run --user --scope -p MemoryMax=300G`)
and a ~1 s sampler of `/proc/meminfo` + per-process RSS
(`archived_runs/20260914_231801_eclipse_nyx_full.expanded/probe/`):

- **Shadow alone** with 2,212 trivial `/bin/true` hosts on the 5k topology,
  `parallelism 128`: init + run in 3.7 s, peak RSS **0.9 GB**. Shortest-path
  routing at this scale is ~5M entries; nothing super-linear
  (`probe/shadow_only_n2212.log`, `probe/gen.py`, `probe/probe.sh`).
- **Real config, 15 min wall:** Shadow init passed, 43 monerods up, sim time
  2:06, `processes failed: 0`. System MemAvailable never dropped below
  **969.7 GB** (of 1,007); cgroup peak **3.4 GB** at 2 min, ~15 GB at 15 min;
  monerod RSS ≈ **0.27 GB/host**, growing linearly with onboarding exactly like
  the 963-host runs. Shadow RSS 0.79 GB. No spike at startup, no kill.
- All 2,212 hosts got IPs, 2,204 distinct /24s, zero reserved.

**What most likely killed the earlier run:** the Claude Code harness's
background-task "system is running low on memory" guard. During this very
probe it killed my own *waiter* task with that message while the box had
978 GB available and the sim's cgroup was at 3.4 GB. A run launched as (or
under) a Claude Code background task gets its process tree killed by that
guard; run_sim's memory sampler dies with it, which is exactly why the
earlier `memory_samples.csv` stopped at an idle T+3s row. The kernel OOM
killer and systemd-oomd were not involved (oomd only watches
`user@1006.service`, and sessions launched from a terminal live in
`session-*.scope`).

**Practical guidance:**
- Launch long runs detached from the agent harness (`nohup`/`setsid` from a
  shell the harness does not track, or `systemd-run --user --scope`), never as
  a Claude Code background task.
- The real memory budget is ~0.27 GB/host => ~600 GB at 2,211 hosts, as
  originally estimated. Fits in 1 TB, but leaves little headroom for anything
  else on the box.
- The real constraint at this scale is **wall-clock**: 2 sim-min took 14 wall-min
  with only 43 hosts up (~0.15x) and it slows further as hosts onboard. A
  12 h sim is likely days of wall time. Consider a shorter stop_time or
  fewer benign hosts before committing the box.

