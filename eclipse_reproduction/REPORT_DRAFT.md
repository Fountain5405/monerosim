# Reproducing "Are Unreachable Nodes Truly Safe? Fully Eclipsing Monero's P2P Network"

Reproduction of the **Nyx** eclipse attack (Shi et al., ACM CCS 2026; arXiv:2609.10260)
using **monerosim** (tag v0.3.1), which runs real `monerod` v0.18.5.1 daemons inside the
Shadow network simulator. Because monerosim executes the genuine Monero P2P code, the
whitelist/graylist/`update_sync_search`/timed-sync logic the attack exploits is real, not
modelled.

## The paper's claim
An **unreachable** Monero node (behind NAT/firewall, accepts no inbound connections) can be
fully eclipsed by an adversary that never contacts it directly. The attacker poisons the
peerlists of *reachable* nodes; the protocol then (i) carries the poison into the target's
graylist via timed sync, and (ii) rotates the target's 12 outbound connections onto attacker
peers via `update_sync_search`. The result is a stable eclipse with no inbound access to the
victim. Reviewer consensus (independent review provided with the paper): the core claim is
**sound**; open questions are about quantitative calibration, not the mechanism.

## What I reproduced and how
I did NOT re-implement the paper's `py-levin` multi-IP injector. Instead I used monerosim's
native design: the attacker is a **fleet of real reachable `monerod` nodes** spread across
distinct /24 subnets. Their genuine handshakes and timed-sync gossip make benign nodes'
whitelists attacker-dominated (N-I); benign nodes relay those records into the target's
graylist (N-II); the target's own `update_sync_search` then replaces its outbound peers with
attackers (N-III). No inbound connection to the target is ever used.

**Unreachable target, deterministically.** `general.reachable_fraction: 0.0` plus a per-node
`hide-my-port: false` exemption on every attacker/benign relay leaves exactly one node — the
target — physically firewalled by Shadow (`blocked_inbound_ports: [18080]`). Verified: the
generator reports "1 node(s) marked unreachable". The target is outbound-only, like a real
NAT'd node; seeds and miners are always reachable.

**Measurement.** A custom script agent (`agents/eclipse_monitor.py`) samples every node over
simulated time via RPC — `get_connections` for the target's outbound peers (CTR) and the
direct `/get_peer_list` endpoint for whitelist/graylist occupation. Each peer is classified
attacker/benign/honest by matching its IP to the agent registry, so I can compute the paper's
metrics: peerlist Occupation Rate (OR), Connection-Takeover Rate (CTR), the target's benign
graylist count B, Time-To-Eclipse (TTE), and eclipse stability.

**Metrics (paper vs this reproduction):**
| Metric | Paper (Nyx, 1200 nodes) | This reproduction |
| --- | --- | --- |
| benign whitelist OR | ~98.5% @ T+10m | _RESULTS_ |
| target CTR (final) | 12/12 (100%) | _RESULTS_ |
| target graylist benign B | 717 → ~2 | _RESULTS_ |
| Time-to-Eclipse | ~27 min | _RESULTS_ |

## Honest differences from the paper (threats to validity)
1. **Scale.** The paper ran 1,200 nodes; my runs are ~10²-node networks (Shadow runs real
   daemons; the shared box has memory/CPU limits). Absolute timings (e.g. 27 min TTE) are not
   expected to match; the *mechanism and trends* are what I reproduce.
2. **Attacker model.** Real attacker nodes contribute **one** whitelist entry each, so the
   target's emergent CTR tracks the attacker's *share of the reachable population*. The paper's
   `py-levin` injects up to 1,000 records per node cheaply, saturating whitelists far beyond an
   attacker's natural node count. To approach 12/12 I therefore make attackers a large majority
   of reachable nodes; this reproduces the *outcome* (attacker-dominated peerlists → eclipse)
   via genuine protocol behaviour.
3. **/24 diversity.** The paper had to *disable* Monero's /24 outbound-diversity filter because
   its 1,000 IPs sat in few /24s. My attacker nodes are assigned distinct /24s by monerosim
   (verified: unique /24s ≈ number of attackers), so the stock filter stays **enabled** — a
   cleaner, more conservative setting.
4. **Honest seeds.** monerosim auto-injects 6 fallback seeds with real hardcoded Monero IPs,
   always reachable. Any target outbound to a seed counts as non-attacker ("other"); displacing
   these is part of reaching a strict 12/12. This engages the reviewer's point that honest
   infrastructure and anchor connections can leave residual non-attacker peers.
5. **Version.** monerosim pins monerod v0.18.5.1; the paper measured v0.18.4.3. The reviewer
   notes the attack is, if anything, marginally *stronger* on v0.18.5.x.
6. **No mainnet.** The paper's Moros (eclipse-at-birth) was evaluated on Monero mainnet against
   controlled targets. I do not attack the live network; only the simulation-based Nyx result
   is in scope.

## Reproduction artifacts
- Scenarios: `test_configs/eclipse_{smoke,baseline,attack}.scenario.yaml` (+ expanded flat YAML)
- Measurement agent: `agents/eclipse_monitor.py`
- Analysis: `eclipse_reproduction/{analyze,analyze_run,compare_runs}.py`, per-run CSV + SVG
- All under the isolated v0.3.1 worktree; the honest network + attack use identical settings
  apart from the presence of attacker nodes.

## Results
_RESULTS_
