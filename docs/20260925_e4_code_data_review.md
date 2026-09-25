# E4 countermeasure campaign — code and data review (2026-09-25)

**Status:** review record. Scope: every E4 artifact produced 2026-09-22 →
2026-09-25 (PoP core / det-tie / uncles / EXACT uncles / mid-scale
replication / SoP steps 1–6), audited against the committed patch
`patches/monero-sim-pop.patch` (sha `9a996089…`, the binary built
2026-09-24T21:08:58Z), the archived run directories, the matrix cell
records, and tevador's MRL #146 text (re-fetched). E1–E3 were not
re-audited. Python suite at review time: 603 passed, 2 skipped.

**Verdict in one line:** the "SoP v2 works" result (finding 10) and the
whole SoP v1/v2 arc (finding 8) are invalid — the SoP binary could not
reorganize; the MRL #144 EXACT-uncle variant has never been measured —
every `*_exact` cell is pop-core + det-tie; the PoP-core, det-tie,
deviated-uncle and mid-scale results are sound.

## 1. Findings (each verified in source AND in archived logs)

### F1 — the SoP v2 binary cannot reorganize (fatal for every SoP cell)

`monero-sim-pop.patch` removed the two hard-fork vote gates in
`Blockchain` (`handle_block_to_main_chain`: `m_hardfork->check(bl)`;
`handle_alternative_block`: `check_for_height`). But `HardFork::add()`
runs the same `do_check()` internally, and `BlockchainDB::add_block`
calls `m_hardfork->add(blk, prev_height)` **ignoring the return value**
(`blockchain_db.cpp:303`). A block whose vote fails is stored WITHOUT an
`hf_versions` row. The next `pop_block_from_blockchain()` →
`HardFork::on_block_popped()` → `db.get_hard_fork_version(height)`
throws `MDB_NOTFOUND`, the exception propagates out of
`switch_to_alternative_blockchain`, and the reorg aborts ("Exception at
[add_new_block] … hard fork version", "mined block failed verification").
Every SoP-mined block has `version_minor` = share count (0–15) < the
fakechain fork version, so every SoP block is affected.

Archived evidence (`grep -c '###### REORGANIZE'` vs `'REORGANIZE
SUCCESS'` per node):

| run | node | reorgs started | succeeded | hf exceptions |
|---|---|---|---|---|
| `20260925_034724_pop_sop2__es_sop2` | attacker-bridge | 9 | **0** | 9 |
| `20260925_055045_pop_sop2__es_r2_sop2` | attacker-bridge | 11 | **0** | 11 |
| `20260924_213345_pop_sop2__honest_sop2` (ramp era) | honest-001 | 7 | **0** | 42 lines |
| `20260924_211242_pop_sop2__es_sop2` (ramp era) | seeds/relays/honest-002 | 2 each | **0** | 1 each |
| `20260924_180323_sop_v2_smoke3` (the validation smoke) | all four nodes | 1–2 | **0** | 1 each |
| `20260925_034724_pop_sop2__es_stock` (vanilla bridge) | every node | 14 | 14 | 0 |

Consequences: in `es_sop2` the covert bridge (unflagged monerod-sim)
could never switch to the attacker's chain, so the attacker's blocks
were never relayed — **honest-001 logged 0 alternative blocks and 0
reorgs in six hours**. "ES annihilated (0.000)" is the bridge failing,
not Share-or-Perish. The attacker-miner daemon (also monerod-sim) hit
the same exception when abandoning honest blocks it had been fed
(`es_r2_sop2` attempt of 04:28: attacker stuck at height 51 while
honest reached 88). The ramp-era "terminal 182-vs-5 split" and the
"mixed-fleet inversion 0.723" are nodes that could not reorg. The
finding-10 methods lesson ("the LWMA ramp manufactures SoP failures")
is therefore unsupported: fixed difficulty merely removed the forks
that exposed the bug. The bridge freeze (2 of 8 cells) correlates with
the exception (only cells with failed bridge reorgs froze) but was not
root-caused here.

### F2 — embedded workshares never verify (SoP weight term inert)

`Blockchain::sim_sop_weight` rebuilds a `block ub` from the share record
and calls `get_block_longhash(this, ub, …)`, which goes through
`get_block_hashing_blob(ub)` — that RECOMPUTES the tx-tree hash from
`ub.miner_tx` (empty) and appends `tx_hashes.size()+1` (wrong count).
The reconstructed header also never receives the share's slot
(`sh.minor_version` is left unset, so slot ≥ 1 ids never match the
gossiped share ids either). At difficulty 1800 the share PoW check fails
for essentially every share; the first failure sets `seq_ok = false`
and the block's weight collapses to `l_b · unit` (unit = 1800/16 = 112).

Evidence: every subjective `SIM-SoP: fork` weight in every archived v2
run is a multiple of 112 (`alt 0/1 vs main 224/2`, ×20 in
`es_r2_sop2`); no archived run contains a fork decision where a share
counted; the "alt 80/5 vs main 48/5" line cited in the handoff does not
occur in any archived log. The share term was never observed working.

### F3 — longer alt chains throw (SoP v1 fragmentation explained)

`sim_sop_weight`/`sim_sop_should_switch` read
`m_db->get_block_difficulty(height)` for alt-chain heights ABOVE the
main top → "Attempt to get cumulative difficulty from height N failed —
difficulty not in db" → the alt block fails verification. So a
subjective node could never adopt an alt chain longer than its own.
Present in every SoP v1 cell (`pop_sop__es_sop` 11, `honest_sop` 14
exceptions) and every ramp-era v2 cell (8, 8, 16, 35). The v1
"pool-derived weights fragment the network" reading (finding 8) is this
bug.

### F4 — the MRL #144 EXACT uncle bonus is STILL inert after the parser fix

`sim_pop_uncle_bonus_header` parses the header (now correctly), then
rebuilds `ub` and requires `get_block_hashing_blob(ub) == blob`. That
can never hold (tree hash and count varint differ, F2), so the loop
`continue`s before the PoW/sibling/lateness checks. Evidence: in four
"fixed-parser" exact runs (`pop_sop__es_r2_exact` 123 fork lines,
`pop_exact_fix_rep__es_r2_exact` 233, `pop_sop__es_exact` 191,
`pop_scale__es_exact` 713) **zero** fork decisions carry a weight above
the chain length. Every cell ever labeled `exact` measured pop-core +
det-tie. Finding 9 ("the correctly-implemented exact variant punishes
lead-2, 0.127/0.294") is a det-tie draw pair; the "non-overlapping
direction" claim vs the inert era compares the same mechanism with
itself.

### F5 — both fixed-difficulty honest controls had zero forks

`honest_sop2` and `honest_stock` (2026-09-25): 0 reorgs and 0
alternative blocks on every node. "P-SoP3 passes — 0.405 ≈ α with zero
orphaning, mixed fleets are fair" is vacuous: fork choice was never
invoked.

### F6 — the matrix table renderer drops a column

`scripts/selfish_matrix.py::render_table` writes `len(axes)` axis
headers but one `cell` column, so with two axes every value in
`table.md` sits one column LEFT of its header. Numbers transcribed from
`table.md` into the design doc's step-6 table and finding 10 are
mis-attributed: "γ = 1.000" is `attacker_orphan_rate` (γ is 0.000 in
the cell JSON), the "att. orphan" column is `network_orphan_rate`
(0.198/0.353/0.243), and "net orphaning 1.417 is modest" is `msb_max_z`.

### F7 — smaller items

- `es_stock` on the fixed-difficulty base (0.337) FAILS all three of
  its own pre-registered verdicts (theory 0.484) and is presented as a
  baseline. The attacker found 32–43 % of all blocks across the six
  cells (σ ≈ 4.5 % at n ≈ 110), so n=1 noise is plausible, but it is not
  a baseline until replicated.
- The "~26 % throughput cost" is misattributed: the honest controls
  show no cost (121 vs 111 blocks); 66 vs 89 is the attacker's 40 %
  hashrate leaving the canonical chain — the intended effect.
- Spec deviation (minor): #146 measures `l_b`/`l_w` against
  `main_seen` = the MAIN-CHAIN block at the height; the code uses the
  earliest block seen at that height (main or alt).
- `nf` (work objects in the alt chain) matches the spec.
- No archived run records which binary it ran; provenance is
  reconstructed from timestamps only.

## 2. What stands

- PoP-core pilot (0.492 → 0.022/0.123), the det-tie axis
  (0.244/0.296), the deviated-uncle variant, and the mid-scale
  replication: no exceptions in any of those runs, reorgs succeed,
  mechanism logs match. Findings 1–8 (PoP parts) survive.
- Relabel: every `exact` cell = **pop-core + det-tie**. Micro vs ES the
  det-tie set becomes n=5: 0.244, 0.296, 0.134, 0.215, 0.210 (mean
  0.22). Mid-scale "exact holds" → "det-tie holds" ({0.170, 0.285} vs
  stock {0.387, 0.463}); finding 7's partial blind spot → det-tie.
- SoP step 1 (share capture ≈ w−1/block) and step 2 (relay + pool)
  validations stand.

## 3. Re-run plan (ordered)

1. **Fix first** (this doc's §5 tracks the fixes): neutralize the vote
   comparison inside `HardFork::do_check`/`do_check_for_height` (and
   restore the two `Blockchain` gates, which then enforce only
   `major_version`); verify shares and uncle headers by hashing the
   ORIGINAL blob with the blobdata `get_block_longhash` overload and set
   the share's slot in the rebuilt header; never look up alt heights
   above the tip in the main DB; fix the renderer.
2. **Fork-forcing regression smoke** asserting, per node: reorgs started
   == reorgs succeeded, zero `add_new_block` exceptions, honest nodes
   saw ≥ 1 alternative block, and ≥ 1 SoP decision whose weight is not
   a multiple of the unit. The first v2 smoke already contained F1;
   nobody grepped for it.
3. **All SoP cells**: v1 rows of `pop_sop`, both `pop_sop2` attempts —
   9 cells at n=2 on the fixed-difficulty base with stock pairs.
4. **All `exact` cells** if the manuscript needs #144-exact: micro +
   mid, n=2 (~10 cells); otherwise relabel as det-tie and retract
   finding 9.
5. **Fixed-difficulty stock baselines** to n ≥ 2 before any "lead-2
   out-earns ES" claim on that base; PoP-core on the same base if
   countermeasures are compared across it.
6. **Docs**: retract/rewrite finding 10, the v1/v2 arc in finding 8,
   finding 9, the E4 "parser fixed" correction block, design-doc steps
   4–6, the handoff, and the ledger rows for those cells (notices
   added 2026-09-25 pointing here).

## 4. Process changes

- Archive `~/.monerosim/bin/monerod-sim.provenance` + the binary sha256
  into every run directory.
- Per-cell health check (reorg started/succeeded, `add_new_block`
  exceptions, per-node alt-block counts, fork-free-control flag) as a
  hard gate in the matrix runner and in every smoke.

## 5. Fix log

**Status 2026-09-25 (end of session): F1–F5b fixed and validated; selfish
work PAUSED at this checkpoint** (user decision) to finish the chain-snapshot
preload on `feat/mainnet-replica` first, so the SoP re-run campaign can run
once, on a chain with an established difficulty. Resume plan: §3.

- **F1 (2026-09-25)**: the vote comparison is dropped where it is
  enforced — `HardFork::do_check` / `do_check_for_height` now check
  `major_version` only (fork activation on the simulated chains is
  height-scheduled with threshold 0, so votes move no fork height) — and
  the two `Blockchain` gates are RESTORED (they now enforce major_version
  through the same functions). `HardFork::add` therefore always writes the
  `hf_versions` row; pops cannot throw. Unconditional, like the vote
  removal it replaces: an unflagged monerod-sim must be able to reorganize
  onto SoP blocks (the covert bridge, the offline attacker daemon).
- **F2**: `sim_sop_weight` hashes the share's ORIGINAL blob (header with
  `minor_version = seq`, the recorded tree hash, the count varint) through
  the blobdata `get_block_longhash` overload; the share id is the keccak of
  that same blob, i.e. what the pool stamped. Share target floored at 1.
- **F3**: `sim_sop_weight(height, block, diff)` takes the block's own
  difficulty from the caller — alt blocks from the alt chain's
  cumulative-difficulty deltas, main blocks from the DB; the subjectivity
  gate uses the first alt block's delta; `sim_block_difficulty_at()` clamps
  any remaining by-height lookup to the tip.
- **F4**: `sim_pop_uncle_bonus_header` hashes the embedded blob itself
  (blobdata overload) and derives the uncle's block id as
  keccak(varint(len) ‖ blob) — what `calculate_block_hash` computes — so
  the receive-time lookup can match a received uncle. The reconstructed-
  block comparison is gone.
- **F6**: `render_table` emits one column per axis plus a `health`
  column; a test pins header/row alignment.
- **Process**: `scripts/sop_health_check.py` (per-node reorg
  started/succeeded, exceptions, alternative blocks, fork decisions,
  share-weighted decisions; hard gate in `run_cell`), `binary_provenance.txt`
  archived by `run_sim.sh` into every run, `test_configs/sop_fork_smoke.yaml`
  (fixed difficulty 300, ES attacker at 6 m through an unflagged
  monerod-sim bridge, SoP on honest/relays/seeds, 45 sim-min).
- **Validation (2026-09-25, `archived_runs/20260925_111038_sop_fork_smoke`,
  binary sha `8b58dfed…`, patch sha `d7ed710c…`)**: the fork-forcing SoP
  smoke passes the health gate — bridge reorgs 20/20, attacker daemon 5/5,
  zero `add_new_block` exceptions on any node, 281 alternative blocks
  accepted by non-attacker nodes, 261 fork decisions with share-augmented
  weights (e.g. `alt 54/7 vs main 1098/6 -> KEEP`: a SEVEN-block attacker
  chain evaluated without throwing (F3), honest blocks weighing ~10 units
  each from counted shares (F2), the network converged at height 51 on
  every node (F1)). Honest nodes never needed to reorganize (they KEEP
  every time); the unflagged bridge follows the attacker's longer chain
  and back, as stock should.
- **F5b (found by the exact-uncle smoke `20260925_112151_pop_exact_fork_smoke`,
  2026-09-25)**: with F4 fixed, that smoke still counted **0** bonuses over
  990 accepted alternative blocks and 5 embedded headers (reorgs 26/26 on
  every node, 0 exceptions). Cause: `sim_pop_should_switch`'s main-chain
  loop guarded the uncle bonus with `if (m_sim_pop_uncles)` — the DEVIATED
  flag — so under `--sim-pop-uncles-header` only ALT blocks could ever earn
  a header bonus and the honest main chain never did (the inner ternary's
  header branch was unreachable). Pre-existing since rung 3. Fixed: either
  flag scores the main chain; the verifier now logs every embedded header
  as COUNTED / REJECTED (reason), and `add_new_block` logs every received
  block that carries headers. **Re-validated** on the race-heavy smoke
  `archived_runs/20260925_113930_pop_exact_fork_smoke_fast` (fixed
  difficulty 40, 60 sim-min, binary built 2026-09-25T11:39Z): 21 template
  embeddings, 22 received blocks carrying headers, 0 unparsable, **14
  headers COUNTED**, 6 fork decisions with a bonus-bearing chain
  (`alt 0/2 vs main 3/2 -> KEEP`: the honest MAIN chain scoring its uncle),
  reorgs 82/82 on the bridge and 37–40/37–40 on the honest miners, 0
  exceptions, 3206 alternative blocks accepted. The two earlier
  zero-count smokes (difficulty 120, 4–5 embeddings) simply had no
  header-carrying block inside any evaluated fork suffix — the receive
  diagnostics show that directly.
- Patch regenerated per the H0/H1 ritual (`/tmp/h0wt` = base + 4 non-pop
  patches); NOTE the build wrapper trap hit on the way: `install_sim_monerod`
  reads `MONEROSIM_BIN` as the bin DIRECTORY (`~/.monerosim/bin`), and its
  `cp` is unchecked — with the wrong value the build "succeeded" and the
  old binary stayed installed. The mtime/provenance check caught it.
