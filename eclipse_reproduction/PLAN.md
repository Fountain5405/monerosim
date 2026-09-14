# Reproducing "Are Unreachable Nodes Truly Safe? Fully Eclipsing Monero's P2P Network" with Monerosim

Paper: Shi, Zeng, Lan, Zhang, Han, Luo, Jin, Du, Wang. ACM CCS 2026. arXiv:2609.10260v1.
HackerOne report #3702913. Monero v0.18.4.3 in paper; monerosim pins v0.18.5.1 (next patch).

## What the paper found (the claims we reproduce)

The paper presents the first eclipse attack on **unreachable** (NAT'd/firewalled) Monero
nodes, which accept NO inbound connections. The attacker never touches the target directly.
Two attacks:

- **Nyx** (existing unreachable nodes) — evaluated in *emulation* (SEED Emulator, 1,200 nodes).
- **Moros** (newborn unreachable nodes) — evaluated on *mainnet* (out of scope for us; we do
  not attack the live network. We instead reproduce the Moros *mechanism* in-sim if time allows.)

We reproduce **Nyx**, the simulation-based result. Three phases:

- **N-I**  network-wide poisoning of *reachable* nodes' whitelists (+ graylists via trash).
- **N-II** the protocol's own timed-sync carries the poison into the *unreachable target's* graylist.
- **N-III** the protocol's own `update_sync_search()` connection refresh rotates the target's
  12 outgoing connections onto attacker peers. No inbound to the target is ever used.

### Paper's headline numbers (Nyx, 1,200-node emulation)
| Metric | Paper result |
|---|---|
| Reachable-node whitelist occupation (OR), median @ T+10min | 98.5% (theory bound 98.8%) |
| Reachable nodes reaching >=95% OR | 99.5% (1193/1199) |
| Target graylist benign count B (pre -> post) | 717 -> ~2 |
| Connection Takeover Rate (CTR) | 12/12 = 100% |
| Time-to-Eclipse (TTE) | ~27 min |
| update_sync_search rounds to full takeover | 17 rounds, 16 malicious (94.1% hit) |
| Eclipse stability | 17h47m, CTR held 12/12 |

Pre-attack state (paper Table 1):
- Reachable node: 12 outgoing, whitelist 847/1000, graylist 353/5000
- Unreachable node: 12 outgoing, whitelist 483/1000, graylist 717/5000

### Key protocol constants the attack exploits (monerod)
- whitelist cap 1000 (sorted by last_seen desc); graylist cap 5000 (FIFO)
- 12 outgoing connections; up to 250 peer records per timed-sync response
- timed sync every 60s (refreshes last_seen for *outgoing* peers only)
- gray_peerlist_housekeeping() every 60s: promotes 1 graylist entry -> whitelist
- update_sync_search() releases 1 outgoing slot ~every 101s; when 12->11 (>=8) it uses the
  graylist-first path -> replacement drawn from the (poisoned) graylist
- graylist-first triggers only when node is *synchronized* (height == tip) -> we must mine
- /24 subnet filtering on outbound selection (paper disabled it; we instead spread attacker
  IPs across many /24s so it passes naturally, keeping monerod stock)

## Why monerosim can reproduce this
Monerosim runs **real monerod v0.18.5.1** binaries inside Shadow. The exploited logic
(whitelist/graylist/update_sync_search/timed-sync) is the genuine Monero code, not a model.
Monerosim provides the exact levers we need:
- `general.reachable_fraction` -> physically firewalls a fraction of nodes (Shadow drops
  inbound TCP to P2P port 18080). This makes a real unreachable/NAT target. Seeds+miners
  always reachable.
- `daemon_options` per node -> set out-peers/in-peers/max-connections-per-ip/hide-my-port etc.
- Python agents with RPC (`get_peer_list` -> OR; `get_connections` -> CTR). We know each
  agent's IP, so we label attacker-controlled peers to compute OR/CTR/TTE.

## Reproduction strategy (faithful, real-protocol)

We do NOT reimplement the paper's py-levin filler. Instead we exploit the *same* real
protocol paths using real monerod nodes, which is faithful to monerosim's design:

- Attacker = a fleet of **reachable** monerod nodes ("malicious peers") spread across many
  /24s. When an attacker node opens a connection to a benign reachable node, after PING/PONG
  it is inserted into that node's **whitelist** (paper's insertion path i). Attacker nodes
  also gossip each other via timed sync, so benign whitelists/graylists become
  attacker-dominated (N-I). Benign reachable nodes then relay attacker records to the
  unreachable target via timed sync (N-II). The target's update_sync_search() rotates its
  outgoing connections onto attacker peers (N-III). Nothing ever connects inbound to the target.

- The paper's 1,000-IP/port-diversity trick is a *scaling optimization* to saturate a
  1000-slot whitelist cheaply. The observable effect (attacker-dominated peerlists ->
  eclipse) is what we reproduce. We scale the attacker:benign ratio so the reachable-node
  peerlists are attacker-dominated, then measure the emergent eclipse of the target.

### Measurement (metrics = paper's)
A monitor agent samples over sim time:
- OR_white(r), OR_gray(r) for each benign reachable node r (from get_peer_list; attacker set known)
- B(target) = benign graylist count on the target
- CTR(target) = fraction of the target's 12 outgoing connections whose peer IP is attacker-owned
- TTE = first sim time CTR == 12/12; stability = duration CTR stays 12/12

### Staged execution (iterate small -> large)
1. **Setup/validation** [DONE-ish]: build monerosim v0.3.1 (worktree, detached tag), venv,
   confirm binaries+pins, run a tiny smoke sim end-to-end.
2. **Baseline (pre-attack, reproduce Table 1)**: benign network + 1 firewalled target; confirm
   target has 12 outgoing + populated peerlist; no attacker. Establishes the control.
3. **Attack (Nyx)**: add attacker fleet; measure OR -> ~high, B(target) -> ~0, CTR -> 12/12,
   TTE, and stability. Compare qualitatively+quantitatively to paper.
4. **Scale up** as CPU/time allow (toward the paper's order of magnitude), report trend.

## Environment / constraints
- Box: 256 cores, ~980 GiB free RAM. Shadow sims are heavy (real monerod per node) but viable.
- Shared user-global binaries in ~/.monerosim/bin (v0.18.5.1 monerod-sim, shadow v0.2.4).
  Another agent works in a SEPARATE workspace (~/monerosim_scale); only CPU/RAM + these
  read-only binaries are shared. Be considerate on scale.
- Artifacts live in ~/monerosim_work/eclipse_reproduction/ (durable, outside the repo).
  Custom agent modules must live under the worktree's agents/ package to be importable.
- We do NOT modify tracked monerosim source (concurrent development). Additive scenario +
  agent files only.

## Status log
- [x] Read paper, extracted claims + constants
- [x] Mapped monerosim, extracted config/agent/RPC API
- [x] Worktree at v0.3.1; cargo build (exit 0); venv + requirements installed; pins match binaries
- [ ] Smoke sim
- [ ] Baseline scenario + Table 1 reproduction
- [ ] Attack scenario + metrics
- [ ] Report
