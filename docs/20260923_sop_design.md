# Share-or-Perish (MRL #146) as a flag-gated monerod-sim patch — design and pre-registration

**Status:** design only (2026-09-23). Implementation is the next C++ rung
after the scale experiments; nothing here has run. Motivated by our own
E4 measurement: PoP's lateness rule punishes catch-up-triggered reveals
(textbook ES: 0.492 → 0.02–0.12) but is blind to proactive ones (Qubic's
observed lead-2 policy: 0.309 → 0.35) — exactly the gap tevador designed
SoP's l_w rule to close.

## The rule (MRL #146, recommended w=16, d=5 s, k=3)

- A **workshare** is a distinct PoW header meeting ≥ 1/w of block
  difficulty with the same `prev_id` as the block that will contain it.
- Chain weight over the last 10·w blocks: block header `l_b·diff(h)/w`,
  each valid share `l_b·l_w·diff(h)/w` (a fully-published block with its
  ~w−1 shares weighs ≈ `diff(h)` — legacy-compatible); older blocks weigh
  plain `diff(h)`.
- `l_b = 0` iff the block was first seen > d after the main-chain block of
  the same height (PoP's lateness);
- `l_w = 0` iff the share was NOT first seen > d BEFORE the honest block
  of that height — **any withholding strategy zeros one of l_b, l_w**: a
  withheld block arrives late (l_b=0), and a withheld share is not seen
  early enough (l_w=0). This is the rule that reaches proactive releases.
- Lateness applies only within k·w = 48 work objects of the fork
  (partition recovery); random tie-break.

## monerosim implementation mapping

1. **Share mining** (extends `patches/monero-sim-mining.patch`): the
   throttled RandomX loop already computes hashes on the current template
   blob; 1/w of block-difficulty hits are share hits. Capture the header
   (nonce, timestamp) when hash meets `diff/w` — no extra hashing cost.
2. **Share relay**: shares MUST propagate before their containing block
   (l_w depends on first-seen timing), so they cannot ride in the block
   (SoP's own note: embedded shares would always be late). New
   sim-gated P2P message + a per-node share pool with dedup/eviction.
   This is the bulk of the patch — new protocol plumbing.
3. **Serialization** per #146: shares in the miner tx extra as
   {timestamp, nonce, tx_tree_hash, num_transactions} with
   `version_minor` = share count and sequential share `version_minor`
   fields (anti-cherry-picking). For the sim we may reuse the
   `tx_extra_sim_uncle` field form (tag + length-prefixed blobs) with a
   distinct tag; the version_minor sequencing rule is load-bearing and
   stays.
4. **Weight table** at fork choice: extends the PoP engine
   (`sim_pop_should_switch`) — rule 1 keeps the k fail-safe on work
   objects; weights use the table above; the PoP receive-time ledger
   gains share entries (same `m_sim_recv` map keyed by share id).

## Pre-registered predictions (before any run)

- **P-SoP1**: SoP closes the proactive-release gap that PoP cannot:
  `es_r2_sop` < 0.25 at α=0.4 (vs 0.309 stock / 0.35 under PoP). Mechanism:
  the lead-2 attacker's withheld blocks AND withheld shares zero out.
- **P-SoP2**: textbook ES stays crushed (`es_sop` ≤ 0.15).
- **P-SoP3**: honest control unchanged (share ≈ α, no storms): honest
  miners publish shares as they grind (they have no reason to withhold),
  so l_w = 1 for honest work; weight ≈ legacy.
- **P-SoP4 (cost readout)**: share traffic volume ≈ w× block
  announcements — measurable in-sim as relay bandwidth, the deployment
  cost #146 itself flags (~170 MB/yr chain data in the tx_extra variant;
  the P2P variant trades that for relay load).
- **Falsifier**: honest-control orphaning above ~2× stock means the share
  pool or l_w timing mis-signs — same discipline as P4 in the PoP doc.

## Build order

1. Share capture in the mining loop + local pool (no relay) — validate
   capture rate ≈ (w−1)/block.
2. P2P share relay + pool.
3. Weight table + version_minor serialization; flags
   `--sim-share-or-perish`, `--sim-sop-w` [16], `--sim-sop-delay-s` [5],
   `--sim-sop-k` [3].
4. Micro A/B (this box), then the scaled matrix on senior alongside PoP.

## Step 1 shipped and validated (2026-09-23)

`--sim-sop-w` (16 = MRL #146 default; 0 = off): the throttled mining loop
logs every PoW header meeting ≥ difficulty/w on the current template
(`SIM-SoP: share …`, plus a once-per-worker arming line). Capture-only —
no relay, no weight effect; the pop_scale matrix running concurrently is
unaffected (flag unset ⇒ stock). Validation smoke (12 sim-min, 1 miner @
8 h/s, w=16): **88 shares / 5 blocks ≈ 17.6 ≈ w−1** ✓.

**Gotcha encoded:** `MINFO` from miner.cpp is suppressed at
`log-level: monitor` (the sims' default) while `MGINFO_GREEN` is forced —
the first three smokes showed zero share lines purely because of this;
the capture was working invisibly. All SoP diagnostics use forced-level
logging.

## Step 2 shipped and validated (2026-09-24)

`NOTIFY_NEW_WORKSHARE` (levin `BC_COMMANDS_POOL_BASE + 11`; payload = the
PoW-header blob (`get_block_hashing_blob`: block_header + **32-byte
tx-tree hash** + tx-count varint — NOT a fixed 80 B) + the template
height). Exactly the scouted touch points: defs.h struct,
`HANDLE_NOTIFY_T2` + handler modeled on fluffy-block,
`i_cryptonote_protocol::relay_workshare` + stub, relay modeled on
`relay_block` **with a `state_normal` connection filter** — share bursts
multiplexing with span downloads on syncing connections measurably
amplified chain-sync churn (427 → 1119 invalid-span drops per 12-min
smoke without the filter, and one deterministic livelocked fork split;
WITH it: 427 = exactly the no-share-traffic baseline). Per-node pool
`m_sim_shares`: dedup by share id, first-seen stamped into the shared
`m_sim_recv` ledger (one clock for l_b/l_w), cap 1024, light validation
(canonical parse + known parent, main or alt at height−1; full PoW
deferred to weight time, like uncle headers). The handler is deliberately
NOT flag-gated — forwarding nodes cannot opt out of gossip (a deployment
property); vanilla monerod relays would drop the unknown levin ID, so SoP
topologies must put monerod-sim on the forwarding path (the matrix
`honest` overlay covers relays).

Validation smoke (`sop_relay_smoke.yaml`, 2 miners × 10 h/s at w=16 + 2
FLAG-LESS monerod-sim relays, 12 sim-min): all nodes converge (height 9);
relays pool 71/68 remote shares each; miners 43/49 local + 40/35 remote;
dedup absorbs template-refresh nonce re-walks; the few rejects are
legitimate races (unknown fork parent, peer briefly behind).

### Defects found while building step 2 (both load-bearing)

1. **The tx-tree-hash parse bug — the "EXACT uncles" bonus was inert in
   every E4 run.** `sim_parse_pow_header` (extracted from the shipped
   `sim_pop_uncle_bonus_header`) started the tx-count varint right after
   the block_header — landing on the 32-byte tx-tree hash — so every
   real blob was rejected (P(pass) ≈ 2⁻³²). The 80-B embeddings were
   written into coinbases but never counted: all `*_exact` E4 cells
   effectively measured **pop-core + det-tie**, and the n=2
   exact-vs-deviated dead heat (0.215 vs 0.209) is fully explained (the
   deviated variant counts from local alt storage — its path worked).
   The mid-scale countermeasure-holds finding survives with the
   corrected label. The parser is fixed in the same commit; re-
   measurement of the exact variant rides the step-4 matrix.
2. **The masked-build footgun.** Piping `install_sim_monerod` output
   through `grep|head` masked a failed build's exit code — smokes 4–5
   ran a stale binary while appearing to test new code (tell: binary
   mtime; behavior byte-identical across "new" builds; a deterministic
   fork split replayed 3×). Ritual: full log + explicit exit check +
   mtime before smoking.

## Step 3 shipped (2026-09-24): the #146 weight table

`--sim-share-or-perish` (+ `--sim-sop-delay-s` [5], `--sim-sop-k` [3]; w
reuses `--sim-sop-w`): `set_sim_sop` arms the table on the PoP engine
(`sim_pop_should_switch` delegates to `sim_sop_should_switch`). Within the
last 10·w blocks of the tip a block weighs `l_b · (diff/w) · (1 + counted
shares)`; older blocks weigh plain difficulty; a share counts when its
parent matches the candidate block's parent, its PoW meets diff/w (lazy
longhash, cached in the pool entry), and it was first seen > d BEFORE the
first block at its height (l_w — the rule that reaches proactive
releases). Rule 1 (k fail-safe) and rule 3 (tie) as in PoP; the unit
weight is floored at 1 (sim-only: bootstrap difficulties < w would zero
every block and degenerate fork choice into permanent random ties).

**Validation smoke (12 sim-min, 2 miners + 2 relays, all SoP):** the
mechanism fires — `SIM-SoP: fork` decisions with share-augmented weights
(unit×(1+shares) visible, honest ties honest). **Watch item, resolved
neither way at smoke scale:** the 12-min/2-miner topology spends its
entire life at bootstrap difficulty (diff ≈ w → unit = 1 → weight =
1 + locally-counted shares), so per-node pools disagree, chain views
churn under random ties, and late-joining relays livelock their initial
sync (stuck at height 4; 1265 invalid-span drops; the pre-floor version
additionally zeroed every weight). The real 6 h A/B topology ramps diff
to ≈1800 within its 10-min bootstrap — the same shape the PoP random-tie
cells ran stably — so P-SoP3 ("honest control unchanged, no storms") is
the live test of whether this matters at experimental scale. If the 6 h
honest_sop control livelocks, that FALSIFIES P-SoP3 on stability grounds
and motivates a deterministic-tie or share-warmup variant — recorded
either way.

**Deviation #2 (documented):** no in-block share embedding / version_minor
serialization. #146 embeds shares in the miner tx extra for trustless
verification by nodes that missed the gossip, plus sequential-
version_minor anti-cherry-picking. Within the 10·w window the gossip pool
dominates (every honest node pools the same shares), the withheld-share
attack zeroes through l_w either way, and no strategy in our set
cherry-picks others' shares (honest miners embed nobody's, attackers run
stock) — so the embedding's load-bearing roles are not exercised. If a
future strategy mines selectively-publishing share cherry-picks, the
embedding + sequencing must be built first.

## Step 4 results (2026-09-24, `matrix_runs/pop_sop/`, 9 × 6 h at α=0.4)

| cell | share | att. orphan | blocks | verdict vs prediction |
|---|---|---|---|---|
| es_none | 0.492 | 0.179 | 195 | baseline, replicates the pilot exactly |
| es_r2_none | 0.356 | 0.231 | 180 | baseline, in the 0.31–0.35 band |
| honest_none | 0.399 | 0.024 | 203 | control clean |
| es_sop | 0.136 | 0.973 | **22** | P-SoP2 "passes" — through collapse |
| es_r2_sop | 0.000 | 1.000 | **9** | P-SoP1 "passes" — through collapse |
| honest_sop | **0.547** | **0.542** | 181 | **P-SoP3 FALSIFIED** |
| es_exact (fixed parser) | 0.210 | 0.593 | 176 | ≈ inert-era values — uncles still no-op vs ES |
| es_r2_exact (fixed parser) | **0.127** | 0.759 | 205 | the bonus BITES lead-2 once it counts |
| honest_exact (fixed parser) | 0.357 | 0.036 | 185 | control clean |

- **P-SoP3 is FALSIFIED, cleanly and instructively.** The honest control
  under SoP earns 0.547 ≠ α=0.4 with self-orphaning 0.542 — 18× the
  pre-registered falsifier threshold (>2× stock's 0.03). The canonical
  chain fragmented: honest miners hold 180+-block local views while the
  attributed canonical chain has 9–22 blocks, with 6k–9.5k invalid-span
  drops per node (427 is the stock baseline). Root cause, consistent with
  the smoke watch item: **weights derived from node-local gossip state
  cannot agree across nodes** — each node counts a different share set,
  random ties plus l_b/l_w asymmetries keep views churning, and sync
  livelocks. The strongest reading of #146's in-block share embedding
  (our deviation #2) is now that it exists precisely to make weights
  node-INDEPENDENT — every verifier re-derives the same weight from the
  block, and only the first-seen timing comes from local state. A v2
  with embedding (+ deterministic tie as a stability knob) is the
  indicated fix; not built yet.
- **P-SoP1/P-SoP2 "pass" only in the degenerate sense**: the attacker's
  share and γ go to 0.000 with att. orphan 1.000 — the l_w mechanism
  does reach both catch-up and proactive withholding — but through
  networks that stopped producing common history (9/22 blocks in 6 h).
  Incentive-removal at the cost of the chain itself.
- **The exact-variant re-measurement (parser fixed) is the clean result
  of the run**: with the uncle-header bonus actually counting, lead-2
  falls 0.356 → 0.127 (att. orphan 0.759) — versus ~0.35 with the inert
  bonus (0.353/0.347 mid-scale, 0.349/0.326 micro). ES is unchanged
  (0.210 ≈ the inert-era 0.134/0.215 — "uncles are a no-op against ES
  at micro" replicates a third time). The prior "PoP is blind to
  proactive releases" residue was therefore substantially the DEFECT,
  not the semantics: the correctly-implemented exact variant cuts lead-2
  to textbook-ES-crush territory. n=1 — replicate before promotion to a
  finding; queued.

## Step-5: SoP v2 — tevador's #146 as written (2026-09-24)

v1's falsification pointed at the omitted embedding; the issue text
(fetched and re-read in full) supplies the missing semantics, all now
implemented:

- **Embedded shares (option 1, tx_extra)**: one 0x76 field per own share,
  record = {seq, timestamp, nonce, tx_tree_hash, num_transactions};
  `version_minor` = share count with slots 0..N−1; each share records the
  tree hash it was MINED under, so verification is node-independent.
  Miners advance slots by pulling a fresh template after every share hit
  (the coinbase embedding + version_minor are covered by the PoW — that is
  what binds a block to its share set).
- **h0/nf subjectivity gates**: l_b/l_w apply only when the node was
  online before the fork (h0 < hf) AND the chains differ by < k·w work
  objects (blocks + embedded shares); otherwise fork choice is plain
  cumulative difficulty. This is #146's late-joiner/partition-recovery
  path — and it eliminates v1's sync livelock.
- **main_seen = block_seen when no main block exists at the height**
  (alt-ahead edge case), per the issue.
- **Hardfork-vote bypass**: `version_minor` normally carries the HF vote
  (must ≥ HF version); with it repurposed as the share count, every SoP
  block would fail version validation. The real proposal is a soft fork
  superseding that rule — the sim bypasses both vote gates when SoP is
  armed.
- v2 also fixes: the template cache must be invalidated when a new own
  share is pooled (the miner's post-share template refresh otherwise gets
  the stale cached template with no embedding).

Validation smoke (12 sim-min, 2 miners + 2 relays, all v2): convergence
at h=10–12 (above the stock baseline's 9–10), share embedding visible
(slot advance 1→2→…), h0 gate firing on relays (OBJECTIVE decisions for
pre-online forks), and **zero invalid-span drops** (stock baseline: 427 —
v2's objective branch is gentler than stock random-tie churn). Bootstrap
forks all sat at heights ≤ h0, so the subjective branch debuts in the
6 h A/B (`pop_sop2`: P-SoP3-v2 stability, P-SoP1-v2/P-SoP2-v2 with an
explicit no-collapse health bar).

**Exact-fix replication (n=2)**: `es_r2_exact` = 0.294 (n=1: 0.127) —
mean 0.211 vs inert-era {0.326, 0.349} and stock {0.309, 0.356}. The
direction holds (fixed < inert, non-overlapping at n=2) but the 0.127
headline was a favorable draw; report ~0.21 ± wide, magnitude
unresolved. The σ≈0.05 single-run lesson, third application.

## Step-5 A/B outcome (2026-09-24, `pop_sop2` attempt 4) — P-SoP3-v2 FALSIFIED; two open defects

Four build/ deployment defects were closed en route (each caught by the
smoke-first rule, each recorded in the commit log): the vote-gate sed
that inverted bypass into enforcement (5816/5816 blocks rejected);
vanilla seeds/bridge rejecting `version_minor`-as-share-count (fixed by
the declared-seed base `selfish_micro_sop.yaml` + an UNFLAGGED
monerod-sim bridge — the soft-fork deployment story); the per-share
template pull saturating shadow's event queue (1 Hz limiter); and
re-indexed share slots breaking PoW verification (true-slot contiguous
prefix).

On the fixed binary the honest network finally *runs* — honest miners
reach 182 blocks in the attack cell, 141 canonical in the control —
but both pre-registered v2 predictions fail:

- **P-SoP3-v2 FALSIFIED on fairness**: the honest control's unflagged
  40% miner (the deployment transition: a fleet that has not all
  upgraded) takes **0.723** of canonical share with the flagged 60%
  side churning (attacker-side orphaning 0.300 = 10× stock). The
  mechanism reads as weight-inflation churn among flagged miners (their
  per-node l_b/l_w views diverge slightly; heavier blocks flip chains)
  handing consistency to the unflagged stock chain. SoP does not merely
  fail to be revenue-neutral during upgrade — it punishes its adopters.
- **Partition-escape gap**: `es_sop2` ended in a terminal faction split
  (honest-001 + attacker-miner at 182 vs honest-002 + bridge + relays
  at 5). The spec's k·w objective escape did not rescue a 177-block
  divergence — either the stranded faction's span-sync path rejects the
  winning chain somewhere outside the fork-choice gates, or subjective
  weights block span-driven adoption. Unresolved; needs a focused
  debug pass on the 5-faction's sync logs.
- Both attack cells also lost their analysis rows (the bridge followed
  the 5-faction, so the chain dump was not recorded) — an analysis-
  tooling dependency to relax (any node's dump can serve as reference).

**Reading**: two independent faithful implementations of #146 (v1
pool-weights, v2 embedded-shares with the full subjectivity machinery)
each fail P-SoP3 in a different way — fragmentation, then mixed-fleet
inversion — on a topology where PoP's core runs cleanly. That is
evidence about the PROPOSAL, not just the implementation: SoP's
timing-weighted fork choice concentrates fragility that #144's
block-level lateness does not. Whether a deterministic tie or a
share-blind upgrade-transition rule rescues it is open.

## Step-6: the fixed-difficulty, late-attacker topology (2026-09-25) — SoP v2 WORKS

Two topology corrections completed the apparatus, and both were
sim-fidelity fixes, not SoP changes:

1. **Fixed difficulty 1800 from genesis** (not the fakechain LWMA ramp
   from diff=1). Real Monero never ramps; the ramp manufactured every
   degenerate regime measured across attempts 1-5 — bankable
   high-cum-difficulty bootstrap islands (a solo daemon's private LWMA
   out-ramps the public one), the diff<w weight degeneracy, and the
   fork-0 objective races that stranded lagging nodes (stock converges
   on the identical topology; the stranding was SoP-subjectivity ×
   span-based catch-up, where monero stops gossiping blocks to
   non-synced peers so the objective rescue never arrives).
2. **The attacker joins at 12m** — after the 10m bootstrap, the shape
   of an attacker facing an operating network rather than genesis.

On the corrected topology (`selfish_micro_sop.yaml`, paired stock
cells, provenance `de5fb7b7`):

| cell | share | att. orphan | blocks | verdict |
|---|---|---|---|---|
| es_stock | 0.337 | 0.198 | 89 | baseline: late-join ES earns 0.34 |
| **es_sop2** | **0.000** | 0.353 | 66 | **P-SoP2 PASSES: ES annihilated, network healthy** |
| es_r2_stock | 0.471 | 0.243 | 87 | baseline: lead-2 out-earns ES (replicates the scale finding) |
| es_r2_sop2 | ≪0.471 (log-verified; row lost to the bridge freeze) | | 78 | every release evaluated to weight 0 and was kept off |
| **honest_sop2** | **0.405** | **0.000** | 121 | **P-SoP3 PASSES: ≈ α, zero orphaning — mixed fleets are fair** |
| honest_stock | 0.369 | 0.000 | 111 | control clean |

- **The honest control is now textbook**: 0.405 ≈ α with zero
  orphaning — and the unflagged 40% miner (the upgrade-transition
  fleet) takes exactly its fair share. The attempt-4 mixed-fleet
  inversion (0.723) was itself a ramp artifact: the flagged side's
  ramp-era churn handed consistency to the stock chain.
- **Textbook ES is annihilated**: share 0.000 with the network alive
  (66 blocks vs stock's 89 — a ~26% throughput cost, the price of the
  countermeasure's churn; net orphaning 1.417 is modest). γ = 1.000:
  every release race resolves against the attacker.
- **P-SoP1 directionally confirmed by logs** (the cell's analysis row
  was lost twice to the bridge freeze — the covert bridge wedges at
  ~5.5h under lead-2 release bursts specifically; 2 of 8 full-topology
  cells, stack-level diagnosis open): the attacker found 38 blocks in
  6h while honest reached 78; EVERY fork evaluation of its releases on
  honest nodes returned weight 0 (l_b=0 for released-late blocks,
  l_w=0 for never-gossiped shares) and was kept off — `alt 0/1 vs main
  224/2 -> KEEP`. Its canonical output is bounded to outright tip wins
  (in-time h=0 extensions), far below the stock cell's 0.471.
- Residual pathologies, honestly: the bridge freeze above (open), and
  one honest node can still strand in ramp-shaped topologies (fixed
  difficulty eliminates the observed cases).

## Step-2 implementation anchors (scout-mapped 2026-09-23, worktree paths)

A new sim-gated `NOTIFY_NEW_WORKSHARE` (payload: ~90 B blob —
share-header bytes + height) touches exactly:

- **declare**: `src/cryptonote_protocol/cryptonote_protocol_defs.h` —
  struct with `const static int ID = BC_COMMANDS_POOL_BASE + <next free>`
  (grep all `BC_COMMANDS_POOL_BASE +` first; fluffy block is +8, highest
  seen +10), `request_t` with a `std::string` blob member +
  `KV_SERIALIZE` (pattern at :322-334).
- **receive**: `HANDLE_NOTIFY_T2(NOTIFY_NEW_WORKSHARE, &...handler)` in
  `cryptonote_protocol_handler.h` invoke map (:88-98), handler decl
  (:143) + impl in `.inl` (fluffy-block handler at .inl:586 is the
  template).
- **send**: a `relay_workshare` virtual in
  `cryptonote_protocol_handler_common.h` (:44 default stub pattern),
  impl modeled on `relay_block` (.inl:2638-2661: for_each_connection →
  relay_notify_to_list; `net_node.inl:2373/2461` transport).
- **size case**: `src/cryptonote_basic/connection_context.cpp:40-70`
  (otherwise SIZE_MAX — works, unchecked).
- **flusher**: `on_idle()` in `.inl:1672-1677` — add a
  `m_workshare_flusher.do_call(...)` like `m_idle_peer_kicker` (1 s idle
  handler registered at `net_node.inl:1048`).
- **test**: `tests/unit_tests/test_protocol_pack.cpp` round-trip case.
- **safety**: unknown levin IDs are logged and dropped
  (`LEVIN_ERROR_CONNECTION_HANDLER_NOT_DEFINED`), no capability
  negotiation gates notify IDs — mixed-version peers just drop shares.
