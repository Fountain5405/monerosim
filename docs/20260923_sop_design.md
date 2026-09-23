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
