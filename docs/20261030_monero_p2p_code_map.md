# monerod p2p code map (v0.18.5.1, tag `v0.18.5.1` @ 4f92268d)

Written 2026-10-30 from a source dive (two read-only scouts over the pinned tree, key lines
re-verified by hand) ahead of the defense-candidate designs. Line numbers are the tag's blobs.
The lab's sim patches (`patches/monero-sim-*.patch`) overlay this stock behavior; the flags
each patch adds are listed inline where they hook.

## 1. How an address spreads (gossip)

- No dedicated peer-gossip message exists. The peer list travels only in the `COMMAND_HANDSHAKE`
  response and the `COMMAND_TIMED_SYNC` response (every ~5 min per connection), each carrying
  `local_peerlist_new` (`src/p2p/p2p_protocol_defs.h:210-271`).
- The gossip payload is a **random sample of the whole white list**, truncated to 250
  (`P2P_DEFAULT_PEERS_IN_HANDSHAKE`, `cryptonote_config.h:142`), with `last_seen` zeroed
  ("anonymize") before sending (`peerlist_manager::get_peerlist_head`, `net_peerlist.h:278-316`).
  The random-sampling comment cites Cao, Tong et al., "Exploring the Monero Peer-to-Peer
  Network" (eprint 2019/411): a fixed-order head would leak recency to a prober.
- Entries are keyed by full address (ip:port): the peerlist's unique index `by_addr` is on the
  whole `adr` (`net_peerlist.h:164-172`). **An IP exposing k ports holds k entries in every
  list that carries it.** Every gossiped entry carries the peer's 64-bit `id`.
- Receive side (`handle_remote_peerlist`, `net_node.inl:2223-2285`): sanitize (drops loopback/
  local/0.0.0.0/rpc-port/bad seeds, forces `last_seen = 0`), then merge **into gray only**.
  Gossiped entries never enter white directly, and remote `last_seen` never overwrites a
  trusted one (`net_peerlist.h:370-371,412`).

## 2. Storage, promotion, trimming

- White 1000 / gray 5000 caps (`P2P_LOCAL_{WHITE,GRAY}_PEERLIST_LIMIT`, `cryptonote_config.h:136-137`),
  enforced by `trim_{white,gray}_peerlist`: erase oldest by `last_seen` (`net_peerlist.h:200-216`).
- Gray -> white only on own contact: successful outgoing handshake (`set_peer_just_seen`,
  `net_node.inl:1208`), incoming handshake + successful ping-back (`:2682`), the gray
  housekeeping probe (`gray_peerlist_housekeeping`, one random gray peer at a time, `:2997`),
  or outgoing timed_sync (`:1273`). `last_seen` refreshes only on such contact.
- Anchor list: `first_seen`-ordered, added on every successful outgoing connect, removed when
  that connection closes; up to `P2P_DEFAULT_ANCHOR_CONNECTIONS_COUNT` = 2 anchor connections
  (`net_node.inl:1450,1928,2760`; `cryptonote_config.h:150`).

## 3. The outbound pick (`make_new_connection_from_peerlist`, `net_node.inl:1562-1821`)

1. Iterate the white list newest-first (`by_time`), **one candidate per IP regardless of port**
   ("avoid ... advertising on a large number of ports", `:1582-1584`).
2. Per-/24 candidate dedup + skip /24s already connected (public zone only, mask
   `ntohl(0xffffff00)`, `:1620`; post-#9939). Fallback pass without subnet dedup if empty.
3. Cut at **20 candidates** for white (`const size_t limit = use_white_list ? 20 : SIZE_MAX`,
   `:1721`); gray is unbounded. Pruning-stripe matches front-load within the cut.
4. Draw: white uses the cubic recency bias
   (`x = rand % (16*max+1); res = x*x*x/(max*max*16*16*16)`, `get_random_index_with_fixed_probability`,
   `:1289-1299`); gray is uniform (`crypto::rand_idx`).
5. Failures: 10 fails -> 24 h host ban (`P2P_IP_FAILS_BEFORE_BLOCK`/`P2P_IP_BLOCKTIME`,
   `cryptonote_config.h:156-157`); recently failed addresses skipped 1 h
   (`P2P_FAILED_ADDR_FORGET_SECONDS`, `:1506-1524`).
- Pre-#9939 (v0.18.4.2, "legacy"): skipped /16s of *connected* peers, one candidate per host,
   no candidate-list subnet dedup. The sim preserves it verbatim
   (`--sim-subnet-dedup=legacy`, `patches/monero-sim-subnet-dedup.patch`).

Sim overlay at this hook: `--sim-subnet-dedup {24,16,none,legacy}` (24 = stock),
`--sim-whitelist-candidates N` (stock 20; 0 = uncapped), `--sim-random-whitelist-candidates`
(candidates a uniform sample, not newest), `--sim-uniform-whitelist-pick` (uniform draw, no
cubic), `--sim-white/gray-peerlist-limit` (stock 1000/5000).

## 4. Connection slots, bans

- Out default 12 (`P2P_DEFAULT_CONNECTIONS_COUNT`), checked before each connect; in default
  set at startup. **Incoming overflow refuses the newcomer; no existing connection is evicted**
  (`is_host_limit`, `net_node.inl:228-244`). The only incoming eviction is the operator
  lowering `--in-peers` at runtime, which closes random connections. Per-host inbound
  fan-in is separately capped (`has_too_many_connections`, `:2955-2977`).
- `--ban-list` file: one IP or subnet per line, permanent (`net_node.inl:506-550`); bans also
  purge the host from white/gray/anchor and close its connections (`block_host`, `:248-328`).

## 5. Dandelion++ (files in `src/net/`, `src/cryptonote_protocol/`)

- Epoch 10 min +- 30 s (`CRYPTONOTE_DANDELIONPP_MIN_EPOCH`/`EPOCH_RANGE`); **2 stem peers per
  epoch** (`CRYPTONOTE_DANDELIONPP_STEMS`); 20% fluff epochs (`FLUFF_PROBABILITY`);
  embargo 39 s Poisson (`EMBARGO_AVERAGE`) then fluff; fluff flush ~5 s Poisson
  (`cryptonote_config.h:106-111`).
- Stem eligible set: outgoing, height-synced connections only - `!context.m_is_income &&
  m_remote_blockchain_height >= height` (`get_out_connections`, `levin_notify.cpp:149-153`;
  verified). Selection: least-used of the epoch map, random tie-break
  (`select_stem`, `dandelionpp.cpp:56-85`). A node's own tx always stems, fluff epoch or not
  (`levin_notify.cpp:557-580`); fluff goes to all connections including incoming.
- **The stem/fluff distinction is visible on the wire**: `NOTIFY_NEW_TRANSACTIONS.dandelionpp_fluff`
  (stem sends false; omitted field deserializes true = fluff, `cryptonote_protocol_defs.h:192-208`).
  This is the spy's observation channel the lab's estimators model. **No hop marker exists**
  anywhere in the relay path: origin vs forwarder is never signaled.

## 6. Identity

- Own id: one random `uint64_t` per run, public zone only (`net_node.inl:143`). Presented in
  `basic_node_data.peer_id` (handshake) and carried in every gossiped `peerlist_entry.id`
  (`p2p_protocol_defs.h:72-99`). Self-detection compares the gossiped id with the handshake id
  (`net_node.inl:1211,2632`) - so a front-end presenting a different id than the backing node
  is detectable in stock, which is how the 2026-09-23 crawl flagged the fleet.

## 7. The 2026-09-23 crawl: the real fleet's shape (aggregate numbers)

From `~/monerosim_local/mainnet_pl/nodes.jsonl` (local-only; raw addresses stay out of the repo):
12,368 flagged endpoints (peer-id mismatch) of 18,026 reachable, on **1,941 distinct IPs** in
**9 full /24s** (six x ~254, one 217, one 199, one singleton), a **median 7 ports per IP**
(max 11), and the 9 /24s sit in **9 distinct /16s**. Consequences measured 2026-10-30:

- /16 outbound dedup is a no-op against the real fleet (deliberately /16-spread). The lab's
  `--sim-subnet-dedup=16` mode stays available for what-if cells; no defense rides on it.
- The fleet's list footprint is ~6.4x its address count (port multiplication). The pick path
  already dedups per host, but neither the white/gray lists nor the gossip head do - the
  per-host accounting candidate (the defense designed next) closes exactly this gap.

## 8. Where the defense candidates hook

| Candidate | Stock hook | Sim status |
|---|---|---|
| Candidate-draw fix (uncap/randomize the 20, uniform draw) | `net_node.inl:1721` cut + `:1289` cubic | measured (E36/E37; `_wc0/_rc/_up` flags) |
| Per-host list accounting | `net_peerlist.h` insert/trim + `get_peerlist_head` | to build (design 2026-10-30) |
| Age-gated stem outlets | `get_out_connections` filter, `select_stem` | to build |
| Identity binding | `basic_node_data`, `peerlist_entry.id`, self-check sites | to build |
| Attested work as cap | white/gray insert points (`append_with_peer_*`) | priced (`docs/20261028_hashrate_gating_arithmetic.md`) |
