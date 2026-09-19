# Onboard-first port-diversity fake-peer Nyx — full eclipse, established victim

Run: `20260916_215526_nyx_onboardfirst` (2026-09-16/17)
monerosim v0.3.1; real monerod v0.18.5.1 under Shadow. Config:
`test_configs/eclipse_nyx_fakepeer.scenario.yaml` (onboard-first timing).
Reproduces Shi et al., "Are Unreachable Nodes Truly Safe? Fully Eclipsing
Monero's P2P Network" (ACM CCS 2026; arXiv:2609.10260).

This is the **last and strongest** run of the Nyx line, successor to
`20260915_201545_eclipse_nyx_fakepeer.expanded`. "Onboard-first" means the benign
population is brought up before the attack fleet, so the unreachable victim builds
a healthy benign peerlist **first** and is then taken over — the paper's threat
model for an *established* node, as opposed to eclipse-at-birth (Moros).

## Setup

- **2,220 hosts**: 1,199 benign monerod + 1,020 attacker endpoints + 1 target,
  plus injectors, miners and seeds, on the regenerated 5,000-node CAIDA GML
  (`gml_processing/5000_nodes_caida_with_loops.gml`, required because AS >= 1200
  previously mapped to loopback/CGNAT first octets that Shadow's DNS rejects).
- **Target `relay-4000` (191.27.1.10)** is established and unreachable:
  `reachable_fraction: 0.0` makes Shadow physically drop inbound SYNs on 18080,
  so the victim is outbound-only — the paper's threat model.
- **Port-diversity fake peers** (`agents.eclipse_fakepeer`), several ports per /24,
  putting ~5,000 connectable (IP,port) records against the victim's 5,000-slot
  graylist cap. Monero's /24 outbound-diversity filter left ON.

## Result — full eclipse reached

CTR = attacker share of the 12 outbound slots. 831 polls over 839 min sim-time.

| milestone | sim-time |
|---|---|
| all seeds + miners displaced (`out_other` -> 0) | 146.4 min |
| first attacker outbound (CTR >= 1) | 173.7 min |
| CTR >= 6/12 | 413.1 min |
| CTR >= 8/12 | 445.4 min |
| CTR >= 10/12 | 541.4 min |
| **first CTR = 12/12 (full eclipse)** | **633.3 min** |
| monitor-recorded `tte_sim_t` | 723.2 min (43,389.7 s) |

Final poll: `out_attacker 12, out_benign 0, out_other 0, n_in 0, ctr 1.0`;
graylist saturated at the 5,000 cap, whitelist 697.

## Honest characterisation of the steady state

Full eclipse is **reached, and is the end state, but it is not a hard lock.**
Across the 204 polls after first 12/12 (634-839 min):

- attacker outbound **mean 11.45**, min 10
- exactly 12/12 in **93 of 204 polls (46%)**
- benign outbound mean 0.56, max 2 — a trickle of honest peers keeps returning
- seeds/miners (`out_other`) stay at **0** throughout
- final unbroken 12/12 streak: 15 polls (~14 min of sim)

The residual oscillation is the convergence-rate-limited honest churn also seen in
the earlier run: 1,199 honest nodes keep re-advertising themselves, and
`update_sync_search` rotates roughly one peer per 101 s, so isolated slots briefly
revert to benign before being retaken.

Two caveats recorded rather than smoothed over:

1. The monitor's `tte_sim_t` (723.2 min) is **later** than the first observed 12/12
   poll (633.3 min). The two use different criteria; 633.3 min is the first
   measured full takeover.
2. `out_attacker` reads **13** in a small number of polls despite there being only
   12 outbound slots — a sampling artifact during peer rotation (an old connection
   not yet torn down), not 13 simultaneous slots.

## Versus the previous run

`20260915_201545` reached 12/12 at 508 min but held a steady-state mean of 9.9/12,
and only displaced seeds/miners at 500 min. Onboard-first holds a higher steady
state (11.45 vs 9.9) and clears seeds and miners at 146 min — a stronger
reproduction, at the cost of a later first 12/12.

## Artifacts

Only `eclipse_metrics.jsonl` (the per-poll trajectory) is tracked here. The bulky
raw artifacts — `agent_registry.json`, `shadow_run.log.gz`, `peerlist_dumps/` and
the 398 KB expanded config that reproduces this run byte-for-byte — live at
`~/basement_monerosim/20260917_eclipse_reproduction/results/20260916_215526_nyx_onboardfirst/`.
