# Spy (proxy) nodes: proposed defenses, an evaluation, and a monerosim test plan

*2026-10-18. Research note. It reviews MRL #126, surveys the other MRL threads and
the related monero PRs, evaluates what has been proposed, adds new ideas, and
proposes monerosim experiments. Nothing here has been implemented or run.*

Claims are marked **measured** (by the cited source), **code** (read in the
monerod-sim tree, which is monerod v0.18.5.1 plus simulator patches; references
are to functions, since the sim patches shift line numbers) or **derived** (my
reasoning, which the experiments in §5 would test).

## 1. Summary

- **The adversary** is one entity running proxy fleets. Today that is about 2,006
  machines with about 8 monerod ports each in AS401476 (Spruce Creek), plus a
  tail of single IPs at hosting providers. The fleet fronts a few unreachable
  backends, waits for honest nodes to dial it, and fills peer lists with its own
  addresses. Its target is the Dandelion++ stem. monerod stems only to outbound
  peers, so the prize is honest nodes' outbound slots.
- **Users behind unreachable nodes are the least protected** (derived). Most nodes
  are unreachable. Nobody can dial them, so they never receive a stem
  transaction, and every stem transaction they send is their own. A spy that
  holds the stem slot gets the origin with certainty. These users' only
  protection is keeping spies out of their two stem slots.
  - #126's estimate of 0.035 mean precision uses D++'s p² bound. That bound
    assumes the sender might have been relaying, which is false here.
- **What is deployed:**
  - an opt-in signed ban list, distributed by DNS since January 2026 and enabled
    by about half of honest reachable nodes;
  - /24 subnet deduplication of outbound peers (v0.18.4.3).

  Both work against the dense core. The spy has answered by spreading across
  many /24s and running several ports per IP.
- **The best MRL proposal is tevador's variant of #160:** PoW-gated "stemmable"
  inbound connections, deduplicated by subnet, with local transactions kept on an
  outbound-only edge. tevador asked for simulations of the adversary's best
  strategy, which monerosim can run. Its gain is limited by how much stem traffic
  actually gets relayed (§3.2).
- **Rejected proposals:**
  - proof of storage is impractical;
  - latency tricks catch only one proxy class;
  - deterministic fingerprints get patched out by the spy.
- **The open asmap PR (#11474) is contested.** Two questions decide it: what ASN
  grouping does to honest connectivity when one cloud provider hosts about 45% of
  honest reachable nodes, and how a stale map fares against new ASNs. Both are
  empirical, and monerosim can answer them with the PR's own code.
- **New ideas (§4):**
  - make the 2 stem slots much pickier than the 12 connection slots;
  - bucket the address book by source, as Bitcoin does;
  - use a sticky, vetted stem for local transactions;
  - check whether fluff epochs expose the originator;
  - close the RPC stem-pool probe from #9496, which is still open in the
    0.18.5.1 code;
  - measure exposure locally and react to it.
- **monerosim already has most of the lab:** `agents/spy_proxy.py`, py-Levin
  eclipse agents, the mainnet-replica profile with spy presets, and stem-path
  analysis.
  - **Missing pieces:** the stem/fluff flag in relay logs, spy-side estimators
    scored against ground truth, forwarding proxies, and the defense flags.
  - **The plan:** §5 proposes eight experiments, starting with a calibration
    against measured mainnet exposure.

## 2. The adversary and what monerod lets it learn

### 2.1 Timeline (measured)

| When | What | Source |
|---|---|---|
| Mar 2023 | **LinkingLion on Bitcoin:** 812 addresses announced by AS54098 (LionLink) opened ~200,000 connections to one node in 5 days. It listens for `inv` and never requests data. The same ranges connect to Monero nodes | b10c |
| Oct 2024 | ~1,900 proxy IPs, mostly in 6 /24s that overlap LinkingLion: "~40% of the IPs running Monero nodes are not real nodes" and ~75% of crawled ip:port peers | #126 |
| Nov 2024 | **Rucknium's log analysis (data Apr-May 2024):** banned IPs almost never dial in; their /24s are saturated (240-254 of 254 used). Honest logging nodes had a time-weighted 15% of outbound connections to them | #126 |
| Dec 2024 | MRL recommends an opt-in ban list, signed by five people | meta#1124 |
| Feb 2025 | 14.74% of IPs are anomalous; one entity has ≥1,582 nodes in 7 /24s. Spies hold 20.37% of honest inbound and 15.26% of outbound connections, or 7.13% outbound with the ban list | Kopyciok et al. |
| Jun-Jul 2025 | The peer-ID mismatch test goes public; the daily moneronet.info scan starts; ~8% of honest nodes use the ban list | meta#1124 |
| Oct 2025 | **v0.18.4.3 ships /24 subnet deduplication (PR #9939):** 70% fewer spy connections in simulation; one operator's spy share fell from 22% to 1.5% | meta#1124, #9939 |
| late 2025 | Spies at DigitalOcean and Hetzner stop showing the fingerprint | meta#1318 |
| Dec 2025 | The LionLink fleet shuts down and a similar fleet appears in AS401476, Spruce Creek (registered Nov 2024) | meta#1124 |
| Jan 2026 | **Ban list v2:** 4,001 addresses, 14 dense /24s plus 322 /24s with 1-3 IPs each. The DNS blocklist follows, enabled by ~50% of honest reachable nodes | meta#1124 |
| Feb 2026 | 81.6% of handshaking nodes (13,420 of 16,454) are spies, all in Spruce Creek | ProbeLab |
| May 2026 | "the spy is still around and has reacted by changing IPs and diversifying across subnets" | #160 |
| Sep 2026 | ~2,006 machines × ~8 ports: 75% of reachable node instances, 27% of reachable machines, in 9 /24s | xmrnetscan, via `docs/20260923_mainnet_topology_literature.md` |

The 81.6% (ProbeLab) and the 27% (xmrnetscan) don't conflict: one counts node
instances and the other machines, and port multiplexing is the difference.

### 2.2 How the proxies work (measured)

`Boog900/p2p-proxy-checker` compares the peer_id a node gives in its handshake
with the one it returns to a ping. The two classes are:

- **Class A:** single IPs that answer the handshake themselves and forward
  everything else to *someone else's* public node. Their ping returns that node's
  peer_id.
- **Class B:** the dense subnets. Each proxy gives a constant "outer" peer_id in
  the handshake. Pings return "inner" ids that many proxies share. These are the
  backends: unreachable nodes under the spy's control. Class-B handshakes return
  peer lists that contain only other class-B proxies.

Other observed behaviour:

- **They don't dial out.** In Rucknium's 2024 data only one banned IP ever
  appeared as an inbound peer. The fleet waits for honest outbound connections,
  which is exactly the connection type that D++'s threat model assumes spies
  cannot force.
- **Their fingerprints don't last:**
  - REQUEST_SUPPORT_FLAGS (#126);
  - the peer-id mismatch;
  - poor peer-list diversity, with fewer than 10 subnets among 250 entries
    (Kopyciok et al.);
  - oversized peer lists;
  - port multiplexing.

  Each fingerprint has been dodged after it was published, as selsta predicted
  in meta#1124.

### 2.3 What monerod 0.18.5.1 gives a spy

**Code:**

- **Stem selection.** Stems go only to outbound peers. Each epoch, of 10 min
  plus U(0, 30 s), a node picks 2 stem peers at random from its outbound
  connections. Each inbound source is mapped to one of the two
  (`levin_notify.cpp` `start_epoch`, `net/dandelionpp.cpp`). The node's own
  transactions also go to one of the two.
- **Fluff decision.** The stem-or-fluff decision is made per node per epoch.
  With probability 20% a node fluffs every stem transaction it relays for the
  whole epoch, but it still stems its own (`levin_notify.cpp`, `fluffing =
  rand_idx(100) < 20`, and the `relay_method::local` exception).
- **Embargo, originator included.** Every node that sends or relays a stem
  transaction sets an embargo timer, Poisson with mean 39 s. If the transaction
  hasn't been fluffed when the timer fires, that node fluffs it. The originator
  is covered too: sending its own transaction through the stem calls
  `on_transactions_relayed(..., relay_method::stem)`, which upgrades the pool
  entry from `local` to `stem` and arms the same timer (`levin_notify.cpp`
  `dandelionpp_notify`; `tx_pool.cpp` `set_relayed`,
  `get_relayable_transactions`; `cryptonote_core.cpp`
  `relay_txpool_transactions`).
- **No stem peer.** With no stem peer available, the node fluffs instead.
- **Fluff delays.** Fluffs go to every connection after a per-connection
  Poisson delay, with mean 2.5 s for outbound and 5 s for inbound connections.
- **Outbound selection** (`net_node.inl` `connections_maker`,
  `make_new_connection_from_peerlist`):
  - 12 outbound peers: 2 anchors, then about 70% from the white list and the
    rest from the gray list;
  - candidates are collapsed per IP, so ports don't count twice;
  - on the first pass, one candidate is kept per /24, skipping any /24 already
    among the node's current connections, *inbound included* (`connected_subnets`
    is built with `foreach_connection` and no direction check); if that pass
    finds nothing, all candidates are used;
  - white picks are skewed toward recently seen entries; gray picks are uniform.
- **Peer lists.** Each handshake or timed sync carries up to 250 random
  white-list entries, with `last_seen` zeroed. Received entries go into the gray
  list (limit 5,000) with no per-source or per-subnet cap. The white list is
  limited to 1,000 (`net_peerlist.h`, `handle_remote_peerlist`).
- **Inbound peers.** An inbound peer that advertises a port and answers a
  ping-back is white-listed. Inbound is limited to one connection per IP, with
  no per-subnet limit.
- **Banning.** There is a ban-list file (`--ban-list`) and an opt-in DNS
  blocklist (`--enable-dns-blocklist`).
- **Pool lookups.** A fluffy block that arrives over P2P is reassembled by
  checking the pool with `relay_category::legacy`, which excludes stem
  transactions (`pool_has_tx`). A block submitted over RPC is assembled with
  `relay_category::all`, which includes them (`handle_block_found` →
  `get_block_complete_entry`). `submitblock` has no restricted-mode gate
  (`core_rpc_server.h`, `on_submitblock`).

**Derived:**

1. **Unreachable nodes get no plausible deniability.**
   - **Why the spy can be certain.** Nobody dials them, so nobody stems to
     them, and every stem transaction they send is their own. A spy can confirm
     the node is unreachable because its ping-back fails or the node advertises
     no port. A spy holding the stem slot then knows the origin.
   - **How often it happens.** The chance per transaction is about p_X, the
     share of X's outbound slots that spies hold. Over n epochs with
     transactions it is 1−(1−p_X)^n. At the 2024 level (p = 0.15), 10
     transacting epochs give 80%.
2. **D++'s bounds don't cover them.** The bounds are recall ≥ p and precision
   near p². They assume the spy can't tell an originator from a relay. That
   holds for reachable senders but not unreachable ones, so #126's figure of
   0.035 applies to reachable senders only.
3. **Reachable nodes' cover is relayed stem traffic, which is thin at mainnet
   rates.**
   - **Supply.** Mainnet carries roughly 25,000 transactions a day, about 17 a
     minute. Each stem has about 5 relay hops, because each relay fluffs with
     probability 0.2. Spread over the 3,000-5,000 honest reachable relays, that
     is about 0.2 relayed stem transactions per relay per 10-minute epoch.
   - **What the spy sees.** A spy stem peer of a reachable home node sees about
     0.1 relayed transactions per epoch next to the user's own (a few per day,
     about 0.02 per epoch). That gives modest precision for occasional users and
     high precision for busy nodes.
4. **Fluff epochs narrow the cover further.** In a fluff epoch a node stems only
   its own transactions. A spy that sees the node fluff a transaction nobody else
   has fluffed yet knows it is in fluff mode, and can then attribute every stem
   transaction the node sends that epoch. At mainnet rates that evidence is rare,
   so the leak is probably small; it is measurable from logs alone.
5. **Dropping a stem transaction tells the spy little.** If a spy stem peer
   drops a transaction, every upstream holder still has a 39-second timer, the
   originator included. The first timer to fire triggers the fluff, and which
   holder that is is roughly uniform, because hop delays are tiny next to 39 s.
   The delay before the fluff hints at how many holders there were: one timer
   versus the minimum of several. That signal is weak, and dropping costs the
   spy a delayed transaction, so this is the behaviour D++ intends. X4 measures
   it.

## 3. The proposals, evaluated

### 3.1 MRL #126, "preventing P2P proxy nodes" (Boog900, Oct 2024)

**Proposed:**

- ban the IPs;
- harden the address book: limit entries per subnet as Bitcoin does, and stop
  storing one IP under several ports or as both IPv4 and IPv4-mapped IPv6;
- proof of storage.

**Comments:**

- SyntheticBird45 has further fingerprints, kept private.
- RB90909 points to the asmap PR, #7935.
- Rucknium's analysis is summarized in §2.1. He estimates a mean precision of
  0.035 and suggests hard-coding the list for outbound connections only.
- yanmaani proposes shared-secret latency windows to expose a middleman.
  Boog900 replies that this only catches class A.

**Assessment:**

- **The diagnosis was right and still holds.** Outbound capture is the attack.
  The issue's data led to the ban list, PR #9939, the proxy checker and the
  scanners.
- **Banning works only while the fleet stays put.** The fleet moved within about
  14 months of the first list (December 2025), and v2's tail of sparse /24s shows
  it spreading thin. Opt-in also caps coverage at whoever enables it.
- **Address-book hardening is only half done.**
  - **What 0.18.4.3 added:** it collapses ports and deduplicates /24s, but only
    when choosing peers.
  - **What's still open:** storage. The gray list still accepts 250 entries per
    message with no cap per source or per subnet, so one class-B handshake can
    insert 250 fleet addresses. Bitcoin's address manager, with buckets keyed by
    source group and address group, is the tested way to bound this.
  - **Verdict:** it costs honest nodes nothing measurable and should be finished
    (§4 N2, §5 X2). Whether IPv4-mapped duplicates are still stored was not
    checked.
- **Proof of storage should be dropped.** tevador's figures in #160 for the
  cited scheme:
  - about 10 s per MB to encode, so days for the chain;
  - proofs around 1 MB, taking 1 s to verify;
  - no guarantee of one key per physical copy.

  fluffypony's point in #162 also applies: proxies that forward to real nodes
  game any "proof of node".
- **Rucknium's precision figure measures the right thing for the wrong group.**
  Precision and recall are the right metrics, but by §2.3 the figure holds for
  reachable senders. Unreachable senders, the majority, face precision near 1.
  The figure also uses the share of all outbound connections, while the attack
  needs the stem slot. The two are equal on average, but differ for one user
  over time.
- **Latency windows (yanmaani) are low priority.** They catch class A only;
  class B has its own backend.
- **An outbound-only hard-coded list is a sound compromise.** MRL declined
  default-on blocking because it would set a precedent for semi-centralized
  blocking (meta#1124, FAQ 6). §4 N1 narrows the idea further, to the two stem
  slots.

### 3.2 MRL #160, inbound peers as stems (Boog900, May 2026)

**Goal:** let inbound peers serve as stems. Unreachable nodes then get cover and
the stem graph grows, without every spy IP getting onto every reachable node's
stem.

**Boog900's version:**

- each node has a PoW-bound identity per IP;
- each node broadcasts a signed Merkle root of its ≤16 outbound addresses;
- a peer that can't prove it is in a node's tree is never stemmed to;
- of the two stems, one is outbound-only and one is mixed;
- local transactions use outbound stems only.

**tevador's objections:**

- invalidating a node's PoW is public, so stems from that IP while it is
  invalid identify the node;
- several nodes behind one NAT invalidate each other.

**tevador's alternative (2026-05-28):**

- **The PoW.** An inbound connection becomes stemmable by sustaining a PoW rate,
  for example 0.5 MH/s of HashWX. That is calibrated to cost about as much as the
  IPv4 addresses it stands in for.
- **The deduplication.** Stemmable connections are deduplicated like outbound
  selection: group by /16, pick one /24 per group, pick one connection. The
  survivors become at most 12 "virtual outgoing" connections.
- **The stems.** The first stem is drawn from real outbound connections only.
  The second is drawn from real and virtual connections together, deduplicated
  by /16. Local transactions always take the first.
- **His summary:** PoW throttles globally, subnet deduplication throttles
  locally, and there is no global state. He asked for simulations of the
  adversary's best strategy.

**Boog900's counterpoints:**

- CPU is easy to rent, as mainnet mining has shown;
- proof of storage would bind one key to one copy of the chain. tevador
  answered that no practical scheme exists, and that an attacker would then need
  only one IP and some disks.
- trusted IP-attestation nodes are a fallback.

**Assessment:**

- **tevador's version is the deployable one.**
  - It keeps state per connection, which vtnerd agrees is simpler.
  - It doesn't broadcast IP-to-key bindings network-wide, which would be a gift
    to crawlers.
  - When it fails, it falls back to today's behaviour.
- **The gain is limited by relay volume** (derived, §2.3).
  - **Where an unreachable node's cover comes from:** only relayed stem
    transactions routed to it through its stemmable connections.
  - **How much that could buy:** if every node took part, the network would
    approach D++'s homogeneous model, with precision near p + q − pq (about 0.3
    at p = 0.15, q = 0.2).
  - **The likely result:** with partial take-up and mainnet traffic, the
    precision for unreachable senders will land somewhere between that and 1.
    Where it lands is the main question for simulation.
- **Recall doesn't change.** Local transactions still go to a real outbound peer,
  so p_X still decides how exposed a user is. The proposal therefore needs
  partners that lower p_X (§3.4, §4 N1-N3).
- **Adversary strategies to model:**
  - many IPs with little CPU, giving few stemmable connections each;
  - few IPs with much CPU, giving at most one virtual slot per /16 per honest
    node;
  - black-holing stems on its stemmable edges;
  - staying a passive outbound target, which is today's behaviour.
- **Verdict:** this is the best-founded proposal so far. Simulate it before
  choosing PoW parameters (§5 X3).
- **Plumbing to share.** PoWER (#133) adds a nonce and a difficulty to the
  handshake, and tevador (2026-10-15) recommends HashWX for it too. #160 could
  use the same mechanism.

### 3.3 Ban lists (meta#1124, PR #10595)

- **What exists.** The list is opt-in, signed by five people, and distributed
  over DNS since January 2026. About 50% of honest reachable nodes enable it.
  PR #10595 proposes a hash plus a download URL instead of DNS TXT records.
- **What it achieves.**
  - It works while the fleet stays put: in Kopyciok et al. it cut outbound
    exposure from 15.26% to 7.13%, and the repo's own LAN node had 0 spies in its
    slots.
  - It is reactive. The fleet moved in December 2025, and single tail IPs are
    cheap to rotate.
- **Adopters indirectly protect everyone else (derived).** Adopters gossip
  peer-list samples free of spies, so non-adopters see fewer spy addresses.
  Rucknium uses the same effect to detect adoption. X7 can measure it.
- **Verdict.** Banning on fingerprints was rejected (selsta: the spies patch them
  before a release ships). That holds for deterministic fingerprints; statistical
  ones cost the spy more to dodge (§4 N7). Keep the list as a stopgap.

### 3.4 Subnet deduplication (#9939) and asmap (#7935, now #11474)

- **/24 deduplication.**
  - **Results:** it shipped in v0.18.4.3. Rucknium's simulation showed 70% fewer
    spy connections, and jeffro256 saw his spy share fall from 22% to 1.5%.
  - **The paper behind it** (Rucknium, draft v0.3, June 2025):
    - **Simulation.** It used a May 2025 scan with 4,607 reachable nodes and
      assumed 80-90% of nodes are unreachable. The spies' mean share of outbound
      slots fell from 3.7 of 12 (30.8%) to 1.06 (8.8%).
    - **Honest load.** Median inbound connections at honest reachable nodes rose
      from 63 to 86 (80% unreachable).
    - **Game model.** Deduplication beats the old /16 rule whenever IPs in
      distinct /24s cost at least 4% more than IPs in whole /24s.
    - **The catch.** At the assumed budget ($1,313 a month, $1 per distinct-/24
      IP), the adversary's best response is to lease distinct-/24 IPs, and it
      still holds about a third of honest connections (32.5% at equilibrium).
      The ban list's v2 tail of 322 sparse /24s looks like that response
      beginning.
  - **The spy's answer:** many /24s, as in the v2 tail, and many ports per IP
    (ports are already collapsed). Under deduplication what matters is the spy's
    share of distinct /24s among candidates. Our crawl found about 3,700 honest
    /24s, against 9 dense spy /24s, or 331 if the sparse tail is the spy's.
- **asmap (#11474: plowsof, 2026-10-03; outbound only, opt-in, bring your own
  map).**
  - **In favour:**
    - The Spruce Creek core would collapse into one group.
    - plowsof's data on #7935 shows the top operator's share falling to 3% with
      ASN buckets, while /16 grouping makes it worse.
  - **Against:**
    - Rucknium (meta#1318): ASNs differ in size and can be created, and the
      spy's ASN is only a year old, so a stale map is exploitable. His game
      model favours subnets because subnets have a known size.
    - vtnerd: the map is hard to review.
    - iamamyth (2026-10-08): the feature's value "seems highly dubious".
  - **Unmeasured cost:** honest reachable nodes are concentrated (DigitalOcean
    44.6%, OVH 6.5%, Hetzner 3.6%), so ASN grouping cuts honest diversity too.
    Nobody has measured what that does to propagation or to partition
    resilience.
- **Verdict.** This is an empirical question. Answer it with the PR's code and an
  asmap built from the simulation's own IP-to-AS allocation (§5 X2). Include a
  hierarchical rule (ASN first, then /24 within it) as a middle ground.

### 3.5 Other MRL threads

- **#133 PoWER (j-berman, 2025).** Requires PoW on a connection before it may
  relay high-input transactions; it is anti-DoS for FCMP++. Not a spy defense,
  but it supplies the PoW plumbing #160 needs.
- **#119 (black marble).** Gingeropolous proposes per-peer adaptive relay PoW.
  tevador notes the relay fee already equals about 12M RandomX hashes, roughly
  20 minutes on a PC. It is anti-spam, not anti-spy.
- **#82 WURDUIP (Gingeropolous, 2021).** A repeater chain that hides wallets'
  decoy-output requests from remote nodes; UkoeHB suggested prefetching instead.
  It addresses a different leak: remote-node operators see wallet IPs (ProbeLab
  counts 883 public RPC providers). It is not about P2P.
- **#162 (node incentives, 2026).** fluffypony: a "proof of node" is either gamed
  by proxies forwarding to real nodes, or centralized. That argues for pricing
  identities in IP diversity and PoW rather than in proofs of node-ness.
- **#45 (bootstrapping), #39 (a network-simulation library) and #24 (a Sybil
  research request).** Background only. #39 asked for what monerosim is.
- **#118, #149, #164 and #94.** Nothing applicable. #164's body is empty.
- **Outside MRL, #9496.** Boog900 found that restricted-RPC `submitblock`
  assembles the block from the whole pool, stem transactions included. A block
  with an unknown transaction fails 50-100× faster. A spy can therefore probe
  whether a public node holds a given stem transaction, and walk the stem
  backwards. The 0.18.5.1 code still does this, and `submitblock` is open on a
  restricted RPC server (§2.3, §4 N5).
- **Tor/I2P for local transactions** (`--tx-proxy`, or a wallet using Tor) is
  the only complete fix for one user. Making Tor mandatory, as suggested in
  meta#1124, costs setup effort and latency.

### 3.6 Scorecard

| Measure | Against today's fleet | Against an adapting spy | Honest cost or risk | Status | Verdict | Test |
|---|---|---|---|---|---|---|
| Ban list (opt-in, DNS) | strong for adopters | weak (rotation) | centralization, lag | deployed | keep | X2, X7 |
| /24 deduplication | strong against the dense core | medium (needs many /24s) | low | deployed | keep | X0, X2 |
| Address-book caps and buckets | medium | medium | low | not done | do it | X2 |
| asmap (#11474) | strong against a 1-ASN core | unclear (new ASNs, stale map) | honest diversity (45% in one AS) | open PR | simulate first | X2 |
| Proof of storage | — | — | very high | impractical | drop | — |
| Latency windows | class A only | — | latency | idea | low | — |
| Banning on fingerprints | short-lived | none | false positives | rejected | use for stem choice only (N1, N7) | X6 |
| #160, Boog900's version | — | medium | global state, NAT, leak on invalidation | idea | superseded | — |
| #160, tevador's version | better precision for unreachable senders | medium (CPU rental) | continuous PoW | idea | simulate | X3 |
| Tor/I2P for local transactions | complete for that user | complete | setup, latency | opt-in today | encourage (N6) | X8 |
| RPC stem-pool probe fix (#9496) | closes a walk back along the stem through public RPC nodes | — | none | open in the 0.18.5.1 code | do it | X5 |

## 4. New ideas

**N1. Make the stem slots pickier than the connection slots.**

- **Mechanism.** Keep the 12 outbound connections as they are. Choose the two
  stems, which carry local transactions too, under stricter rules:
  1. the two stems are in different /16s, or different ASN groups if a map is
     loaded;
  2. neither comes from a /24 that is saturated in the node's own address book,
     meaning more than T distinct IPs seen. The largest honest /24 Rucknium saw
     had about 30 IPs and spy /24s had 240-254, so T ≈ 64 separates them today;
  3. each has been connected for at least one full epoch. In #126, spy
     connections were about 25% shorter;
  4. each passes a peer-id consistency check over a separate ping connection.
     This catches naive class-B proxies and fails open;
  5. optionally, neither is on a loaded ban list, even if the operator didn't
     enable full banning. The list then steers only the most privacy-sensitive
     choice, a narrower form of Rucknium's outbound-only suggestion.
- **Why it helps.** Blocks and fluffs still use all 12 peers. Connectivity and
  eclipse resistance don't change; only the choice of 2 out of 12 does.
- **Adversary response.** Spreading across /24s defeats rule 2, longer
  connections defeat rule 3, and consistent ping answers defeat rule 4. Each
  costs the spy something.
- **Cost.** None to speak of. If the rules exclude everyone, fall back to today's
  choice.
- **Test.** X4.

**N2. Bucket the address book by source and cap entries per /24.**

- **Mechanism:**
  - a gray entry goes into a bucket chosen by hash(source /16, address /16);
  - a white entry goes into a bucket chosen by its own group;
  - buckets have a fixed size;
  - each list holds at most k entries per /24;
  - ports and IPv4-mapped forms are collapsed when an entry is inserted.
- **Why it helps.** Today one class-B handshake adds 250 fleet entries.
  Bucketing caps the share of the table any one source group can fill.
  Poisoning then scales with how many groups the spy controls, not with how many
  addresses it advertises.
- **Cost.** Implementation only; Bitcoin has run this design for years.
- **Test.** X2.

**N3. Use a sticky, vetted stem for local transactions.**

- **Mechanism.** Send local transactions through one long-lived peer: an anchor
  that passes N1. Keep it across epochs and restarts, and re-draw only if it
  disconnects or after a long period, such as days.
- **Why it helps.** Today the local stem is re-drawn every ~10 minutes, so a
  user transacting over n epochs is exposed with probability 1−(1−p)^n. A sticky
  stem keeps it near p for the period. Fewer users are ever exposed; the unlucky
  ones stay exposed longer; the expected number of exposed transactions is
  unchanged.
- **Risks.**
  - An attacker able to force a disconnection, as connection-reset eclipse
    attacks do, can force a re-draw. On a re-draw, prefer the other anchor.
  - D++ rotates stems every epoch to resist graph learning. That still applies
    to relayed traffic, which N3 doesn't touch.
- **Test.** X4.

**N4. Check whether fluff epochs expose the originator.**

- **Mechanism.** Measure the leak first (§2.3 point 4); X1's logs are enough. If
  it matters, either hold local transactions until the next stem epoch (20% of
  them would wait up to 10 minutes), or keep stemming a random share of relayed
  transactions during fluff epochs.
- **No embargo change is needed.** The originator already arms the same embargo
  timer as relays (§2.3), so dropping a transaction leaks only the weak timing
  signal in point 5.
- **Test.** X4, including a black-hole adversary to measure point 5.

**N5. Close the RPC stem-pool probe.**

- **Status (code, 0.18.5.1).** The P2P path is already safe: fluffy-block
  reassembly ignores stem transactions. The RPC path isn't. `submitblock` is open
  on restricted RPC, assembles the block from the whole pool, and fails fast when
  a transaction is missing. That is the 50-100× timing gap Boog900 measured in
  #9496.
- **What it gives a spy.** A spy holding a stem transaction can ask every public
  RPC node (ProbeLab counts 883) whether it holds it. That finds the upstream
  relays that expose RPC, and the originator when the originator is a public
  remote node.
- **Fix.** Assemble RPC-submitted blocks from broadcast transactions only
  (`relay_category::broadcasted`), as Boog900 suggested, or check PoW before
  assembling. Check whether this landed upstream after 0.18.5.1.
- **Test.** X5.

**N6. Measure exposure locally and react.**

- **Mechanism.** A node estimates its own exposure: the share of its outbound
  peers that are on a loaded list, sit in saturated /24s, or fail N1's checks.
  It then warns the operator, or sends local transactions over `--tx-proxy` when
  Tor or I2P is configured.
- **Unreachable nodes in particular** should be told that D++ gives them no
  cover.
- **Cost.** Cheap, with no protocol change.

**N7. Shared-backend fingerprints that cost the spy something to dodge.**

- **Mechanism.** Use statistical tests on behaviour a backend can't easily vary
  per proxy:
  - block announcements from two peers that share a backend arrive with a nearly
    constant offset, whereas independent nodes' offsets vary with where each
    block came from;
  - tx-pool complements are identical;
  - peer lists overlap far beyond chance.

  Matches feed N1, so they affect stem choice only.
- **Adversary response.** Per-proxy delays, plus perturbed pools and peer lists.
  These are dodgeable, but cost engineering.
- **Test.** X6, offline on X1's logs.

## 5. monerosim experiments

### 5.1 What exists and what's missing

**What exists:**

- **Spy agents.**
  - `agents/spy_proxy.py` (variant P) listens on `port_base`..`+port_count`,
    dials honest peers up to `dial_budget`, gives a random outer peer_id and an
    optional mismatched ping id, and serves peer lists that mix the fleet with
    its backend's white list (`fleet_share`, default 0.5). It takes chain data
    from a backend monerod, and it neither relays nor logs transactions.
  - Variant R is a set of stock monerod spies; its logs record what the spies
    receive.
- **py-Levin tooling.** `agents/levin_lib.py` and the eclipse agents provide a
  codec, multi-port fake peers and peer-record injection. An eclipse of
  unreachable nodes has already been reproduced (`docs/eclipse_reproduction.md`).
- **The mainnet replica** (`docs/superpowers/specs/2026-09-23-mainnet-replica-design.md`):
  - a stage-1 profile with 2024, 2025 and 2026-09 spy presets on spy-only /24s;
  - honest prefix sharing of 0.31 with 3 per prefix;
  - about 15% of nodes reachable;
  - stage 3 lists "tx-origin inference" and countermeasure effectiveness as its
    planned experiments, and §5 is a concrete version of that stage.
- **IP allocation.** Per-AS /24s are drawn from real RIR ranges
  (`src/ip/as_manager.rs`), and `subnet_group` places agents in one /24.
- **Analysis.**
  - `tx-analyzer spy-node` guesses origin from the first observations across all
    nodes and reports accuracy only;
  - `tx-analyzer dandelion` walks stem paths from ground truth;
  - an upgrade-analysis mode samples random observer fractions;
  - `analysis/conn_matrix.py` builds the peer graph;
  - `analysis/mainnet/` holds the crawl, poll, ban-list and ASN tools.

**Missing:**

- **Relay logging.** Neither spies nor honest nodes log the stem/fluff flag.
  The parsed line `Received NOTIFY_NEW_TRANSACTIONS (N txes)` doesn't carry it.
  *(2026-10-19: I1 below is built on branch `feat/spy-relay-log`:
  `patches/monero-sim-txrelay-log.patch`, `docs/TXRELAY_LOG.md`.)*
- **Spy-side estimators.** No estimator uses only spy vantage points, and none
  reports precision and recall against ground truth by sender reachability.
- **Exposure over time.** There is no per-node time series of the spy share of
  outbound and stem slots, because stem peers aren't logged.
  *(2026-10-20: both are covered by I3 below, on the same branch:
  `analysis/spy/spy_estimators.py`, `docs/SPY_ESTIMATORS.md`.)*
- **Forwarding.** `spy_proxy` doesn't forward, so a backend never sees honest
  traffic the way a class-B backend does.
- **Defenses.** monerod-sim has no flags for any of the defenses above.

### 5.2 Shared infrastructure (build once)

- **I1, relay log (monerod-sim, small patch).** Behind `--sim-log-txrelay`, write
  one line per transaction received, with hash, peer, direction and fluff flag.
  Also log each stem send, and each epoch with its fluff flag and its two stem
  peers. With this on every node, the stem graph and each node's stems become
  ground truth.
- **I2, spy fleet (agents).**
  - **Splice mode for `spy_proxy`.** It answers the handshake itself, with the
    outer id and a poisoned peer list, then pipes Levin frames to a backend
    monerod and logs which honest IP maps to which backend port.
  - **Black-hole switch.** The backend gets `--sim-spy-drop-stem`.
  - **Variant R** stays for cheap cells.
- **I3, estimators (`analysis/spy/`).** It would compute:
  - the stem-predecessor estimator, alone and combined with the reachability
    test;
  - first-spy over fluffs, and a combined estimator;
  - precision and recall per sender class, with bootstrap confidence intervals;
  - per-node p_out(t) and p_stem(t);
  - P(a user has at least one exposed transaction) by transaction count.

  Ground truth comes from `transactions.json`, the agent registry and I1.
- **I4, defense flags (monerod-sim, each off by default):**
  - `--sim-subnet-dedup=none|24|16`;
  - `--asmap <file>`, cherry-picked from #11474;
  - `--sim-addrbook-buckets` (N2);
  - `--sim-stem-filter=...` (N1);
  - `--sim-sticky-local-stem` (N3);
  - `--sim-inbound-stem` (#160, tevador's version);
  - `--sim-stem-pool-private` (N5).

  Shadow doesn't advance simulated time for computation, so real PoW would cost
  nothing in a simulation. Model it instead as a per-node budget of stemmable
  connections.
- **I5, presets (configs).** Preserve the ratios that drive peer selection, not
  raw counts:
  - the spy's share of reachable machines (27%) and of reachable instances (75%,
    using `port_count` 8);
  - the spy's share of distinct /24s and ASNs among reachable addresses;
  - one AS holding about 45% of honest reachable nodes;
  - about 85% of nodes unreachable;
  - a transaction rate per node matched to mainnet (about one per node per day),
    with a 10× variant.

  A 1,000-host replica can't hold mainnet's ratio of 9 spy /24s to ~3,700 honest
  ones, so each preset must state which ratio it keeps.

### 5.3 The experiments

**X0: calibrate the lab.**

- **Question:** does the replica reproduce measured exposure?
- **Cells:** the 2024 spy preset × {pre-0.18.4.3 selection, stock /24
  deduplication} × {no ban list, ban list on 50% of honest nodes}.
- **Targets:**
  - spy share of honest outbound slots ≈ 0.15 with no deduplication and no list
    (#126; Kopyciok et al. measured 15.26%);
  - ≈ 0.07 with the list (7.13%);
  - about 70% lower with deduplication;
  - stem length near a geometric distribution with mean 5 relays;
  - the rate at which embargo timers fire.
- **Pass:** each target within 1.5×, or a written reason why not.

**X1: who is deanonymized today?**

- **Cells:** the 2026-09 preset (dense core, 8 ports per IP, passive, poisoned
  peer lists) and a tail-diversified preset, on the stock binary, with ban-list
  adoption at 0% and 50%.
- **Metrics per sender class** (unreachable, reachable, busy reachable):
  - precision and recall of the stem-predecessor estimator, with and without the
    reachability test;
  - first-spy over fluffs;
  - P(at least one exposed transaction in 24 h) by transaction count.
- **Predictions (§2.3):**
  - unreachable senders: precision ≈ 1, recall ≈ p;
  - occasional reachable senders: low precision;
  - fluff-epoch inference: small at mainnet rates, larger at 10×.

**X2: peer grouping and the address book.**

- **Factors:**
  - grouping: none, /24 (stock), /16, asmap (#11474), or asmap then /24;
  - address book: stock, or N2;
  - adversary:
    - the dense core in one AS;
    - the core plus single IPs at honest-heavy hosting ASes;
    - K new small ASNs that the map doesn't know;
    - inbound /24 squatting: IPs inside honest-heavy /24s dialing in to
      reachable nodes, which removes those /24s from the node's next outbound
      picks;
  - ban-list adoption: 0% or 50%.

  Use a sparse design, not the full factorial.
- **Metrics:**
  - p_out and p_stem distributions, split into reachable and unreachable nodes;
  - the fleet's share of gray and white lists over time;
  - honest outbound diversity (distinct ASNs);
  - block propagation delay;
  - time to a full outbound set after start;
  - connectivity after the largest honest AS is removed (an outage);
  - eclipse success with the existing eclipse agents.
- **What it answers for #11474:**
  - whether asmap beats /24 against today's fleet;
  - what asmap costs honest connectivity given the hosting concentration;
  - how a stale map fares against new ASNs.

**X3: #160 (tevador's version) against its best adversary.**

- **Cells:**
  - inbound stemming: off or on;
  - honest participation: 50% or 100% of unreachable nodes request one
    stemmable connection, and reachable nodes request two;
  - adversary budget (IPs × stemmable connections), swept along tevador's cost
    line;
  - adversary strategy: passive, as many stemmable connections as possible, or
    black-holing on stemmable edges.
- **Metrics:**
  - the headline: precision and recall for unreachable senders;
  - stem-graph size;
  - stem latency;
  - the spies' share of honest stems.
- **Prediction:**
  - for unreachable senders, precision falls well below 1 but stays above D++'s
    homogeneous figure;
  - recall stays the same.

  Report the adversary's best response at each budget.

**X4: stem rules, sticky local stem, black holes.**

- **Cells:**
  - stock;
  - N1, each rule alone and all together;
  - N3;
  - N1 with N3;

  each against a passive and a black-hole adversary, on the dense and tail
  presets.
- **Metrics:**
  - p_stem compared with p_out;
  - P(at least one exposed transaction in 24 h) for users sending 1, 5 and 20
    transactions;
  - what a black-holing spy learns from fluff timing (§2.3 point 5), and the
    delay it causes;
  - the fluff-epoch leak (N4), from the same logs;
  - time to fluff and to 90% coverage;
  - lost transactions;
  - how often N1 falls back to the stock choice.

**X5: the RPC stem-pool probe.**

- **Mechanism.** An RPC probe attached to the spy. When the spy gets a stem
  transaction, it calls `submitblock` on the public-RPC nodes with a block that
  contains it (no valid PoW needed) and times each reply. A slow reply means the
  node holds the transaction, which lets the spy walk the stem backwards.
- **Simulation caveat.** Shadow doesn't advance simulated time for computation,
  so the timing gap won't appear on its own. Add a sim-only delay on the slow
  path, or treat the probe as perfect to get an upper bound.
- **Measure.** The gain over X1, then the same run with N5.

**X6: proxy detection, ROC (offline).**

- **Scoring.** Score each pair of honest node and peer on:
  - peer-id consistency;
  - variance of block-arrival offsets;
  - tx-pool equality;
  - peer-list overlap;
  - connection length.

  Draw ROC curves against ground truth. Honest nodes in the same hosting /24s
  and ASes as the spies are the hard negatives.
- **Adapted spy.** Repeat with the spy's countermeasures turned on, such as
  per-proxy delays.
- **Cost.** Uses X1's logs, so it needs no new runs unless the adapted spy
  needs one.

**X7: ban-list dynamics (small).**

- **Cells:** adoption {8%, 50%, 100%} × list lag {0, 1 week} × the spy rotating
  its tail.
- **Also measure** the indirect effect: adopters gossip spy-free samples to
  non-adopters.
- **Cost.** Fold into X2's cells where that's cheap.

**X8 (stretch): `--tx-proxy` over a small Tor network in Shadow.**

- **Setup.** Shadow was built for Tor experiments. A share of users' nodes would
  send local transactions over Tor.
- **Measure.** Latency, and any leak that remains.
- **Cost.** A large effort; do it only if a recommendation depends on the
  number.

### 5.4 Order and constraints

**Order:**

1. Build I1 and I3, then run X0, which establishes whether the lab is credible.
2. Run X1, the baseline every other experiment is compared with.
3. Run X2. It bears on an open PR, and needs only a cherry-pick and configs.
4. Run X3 and X4, which need the most new monerod-sim code. X3 answers tevador's
   request in #160.
5. Run X5 for the RPC probe, which the 0.18.5.1 code leaves open. X6 is
   analysis only; run X7 and X8 as needed.

**Constraints:**

- **Timing.** Nothing runs before the campaign-8 queue and the follow-up SoP
  work. Patches are built after the queue, and the owner installs them
  (`./setup.sh --sim-binary`).
- **Replicates.** monerod isn't seed-deterministic, so use at least 3
  replicates per cell and compare distributions, never seed pairs.
- **CPU.** Keep each batch within the 32 physical cores. Replica-scale runs are
  large: start them one at a time and check `cpu_plan.txt`.
- **Publishing.** Posting results to MRL threads is the owner's call.

## 6. Open questions

- Whether the #9496 fix (assembling RPC-submitted blocks from broadcast
  transactions only) landed upstream after 0.18.5.1.
- Whether IPv4-mapped duplicates are still stored.
- The mainnet transaction rate and the unreachable share to use in the presets.
- The private fingerprints (SyntheticBird45, plowsof). They aren't public, and
  this note doesn't need them.

## Sources

- MRL issues, `monero-project/research-lab`:
  [#126](https://github.com/monero-project/research-lab/issues/126),
  [#160](https://github.com/monero-project/research-lab/issues/160),
  [#133](https://github.com/monero-project/research-lab/issues/133),
  [#119](https://github.com/monero-project/research-lab/issues/119),
  [#82](https://github.com/monero-project/research-lab/issues/82),
  [#162](https://github.com/monero-project/research-lab/issues/162),
  [#45](https://github.com/monero-project/research-lab/issues/45),
  [#39](https://github.com/monero-project/research-lab/issues/39),
  [#24](https://github.com/monero-project/research-lab/issues/24)
- [meta#1124](https://github.com/monero-project/meta/issues/1124) (the MRL ban-list
  recommendation and its timeline), [meta#1318](https://github.com/monero-project/meta/issues/1318)
  (MRL meeting of 2025-12-31, asmap)
- monero PRs and issues: [#9939](https://github.com/monero-project/monero/pull/9939),
  [#7935](https://github.com/monero-project/monero/pull/7935),
  [#11474](https://github.com/monero-project/monero/pull/11474),
  [#10595](https://github.com/monero-project/monero/pull/10595),
  [#9496 (stem-pool timing)](https://github.com/monero-project/monero/issues/9496#issuecomment-2395469805)
- [Boog900/p2p-proxy-checker](https://github.com/Boog900/p2p-proxy-checker),
  [Boog900/monero-ban-list](https://github.com/Boog900/monero-ban-list)
- Rucknium, [Monero peer subnet deduplication](https://github.com/Rucknium/misc-research/blob/main/Monero-Peer-Subnet-Deduplication/pdf/monero-peer-subnet-deduplication.pdf)
- 0xB10C, [LinkingLion](https://b10c.me/observations/06-linkinglion/)
- ProbeLab, [Peering into Privacy](https://probelab.io/blog/peering-into-privacy-a-deep-dive-into-the-monero-network-topology/)
- Kopyciok, Schmid, Victor, [Friend or Foe?](https://arxiv.org/abs/2509.10214)
- Fanti et al., [Dandelion++](https://arxiv.org/abs/1805.11060)
- [xmrnetscan](https://xmrnetscan.redteam.cash/), [moneronet.info](https://moneronet.info/)
- In this repo: `docs/20260923_mainnet_topology_literature.md` and
  `docs/superpowers/specs/2026-09-23-mainnet-replica-design.md`
