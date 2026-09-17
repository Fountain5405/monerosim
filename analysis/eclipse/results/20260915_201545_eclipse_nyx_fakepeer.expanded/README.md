# Full-scale port-diversity fake-peer Nyx — FULL ECLIPSE reproduced

Run: `20260915_201545_eclipse_nyx_fakepeer.expanded`  (2026-09-15/16)
monerosim v0.3.1, branch `eclipse-reproduction`; real monerod v0.18.5.1 under Shadow.
Reproduces Shi et al., "Are Unreachable Nodes Truly Safe? Fully Eclipsing Monero's P2P Network".

## Setup (paper-faithful Nyx)
- **1199 benign** monerod (the honest population)
- **1 ESTABLISHED, UNREACHABLE target** (`relay-4000`, 191.27.1.10): `reachable_fraction: 0.0`
  makes monerosim firewall its inbound P2P 18080 (Shadow `blocked_inbound_ports`), so it is
  outbound-only — the paper's threat model. It bootstraps a benign peerlist first, then is eclipsed.
- **1000 distinct-/24 port-diversity fake peers** (`agents.eclipse_fakepeer`), 5 ports each
  => ~5000 connectable (IP,port) records ≈ the victim's 5000 graylist cap (the paper's
  port-diversity). Each presents the GENESIS block as top_id so the victim holds it (state_normal).
- 6 injectors (N-I graylist flooding) + 4 miners + 6 seeds + monitor. 5000-node CAIDA GML.
  /24 outbound-diversity filter left ON. stop_time 12h. Config in this dir.
- Fixes that made it work: /24 script-agent distribution (`630e3d5b`), genesis-top_id
  sync-credibility (`41023478`), dial_sample pure-listener mode for scale (`ac7b32d6`).

## Result — FULL ECLIPSE
CTR = attacker outbound / 12. Trajectory (Shadow sim-time):

| milestone | sim-time |
|---|---|
| first attacker outbound (CTR≥1) | 13 min |
| CTR ≥ 6/12 | 105 min |
| CTR ≥ 8/12 | 168 min |
| CTR ≥ 10/12 | 492 min |
| **CTR = 12/12 (FULL eclipse)** | **508 min** |
| all seeds+miners displaced (out_other→0) | 500 min |

- **Steady state (sim 477–706 min): attacker outbound mean 9.9/12, min 8, max 12.**
- The residual 2–4 slots oscillate to benign — the 1199 honest nodes constantly re-advertise
  (convergence-rate-limited honest churn), same residual seen in the real-node run.
- **Peak 12/12 matches the paper's CTR; steady ~83% eclipse with ALL infrastructure displaced.**
- vs the real-monerod baseline `eclipse_nyx_full` (7/12, graylist only ~45% attacker because
  1000 single-port /24s can't out-number 1199 benign /24s): port-diversity puts ~5000 attacker
  records against the 5000 graylist cap → graylist attacker-domination → full eclipse.
- Shadow: 100% of the 12h sim completed, **0 processes failed**, ~13h wall.

## Files
- `eclipse_metrics.jsonl` — per-poll target metrics: `out_attacker`/`out_benign`/`out_other`,
  `ctr`, and `gray_*`/`white_*`/`B_target` where the RPC didn't time out. The trajectory.
- `agent_registry.json` — every agent's `id`, `ip_addr`, `attributes.eclipse_role`. Maps IP→role.
- `relay-4000_bitmonero.log.gz` — the target monerod's full P2P log (`gunzip` to read).
- `shadow_run.log` — Shadow's run log (progress %, `processes failed` count).
- `eclipse_nyx_fakepeer.scenario.yaml` — the exact scenario.

## Caveats for analysis
- The monitor's `get_peer_list` RPC **times out** at this scale on the huge peerlist, so
  `gray_attacker`/`gray_benign`/`B_target` are `?` for many mid-run readings (`out_attacker`
  from `get_connections` is complete). Reconstruct occupation from the target log if needed.
- `sim_t` is Shadow simulation seconds; wall-clock ≠ sim (onboarding ~0.03×, steady-state faster).
