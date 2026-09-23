# Difficulty preload for native mining — design

**Date:** 2026-09-23 · **Branch:** `feat/mainnet-replica` · **Status:** spec only, nothing built
**Parent:** `docs/superpowers/specs/2026-09-23-mainnet-replica-design.md` (the replica
runs native mining, so it needs this)
**Background:** `docs/NATIVE_MINING.md` §"What the run taught" and the 300-node DAA gate.

## 1. Problem

Native mining uses real RandomX (`--sim-hash-interval-ms`) and monerod's real
difficulty algorithm. Every run starts from an empty regtest chain, so difficulty
starts at 1 and only reaches its equilibrium `D ≈ 120 s × H` after the algorithm's
window fills: about **720 blocks, roughly 24 simulated hours**. Until then blocks
come far too fast, and orphan, propagation and DAA behaviour are not representative.
A 16 h replica run would be entirely warm-up.

The **response** to a later hashrate change also takes ~720 blocks. That part is
real mainnet behaviour and must stay. Only the genesis warm-up is an artefact.

## 2. Facts the design rests on (monerod v0.18.5.1, read-only)

| Fact | Where |
|---|---|
| `DIFFICULTY_WINDOW 720`, `LAG 15`, `CUT 60`, target 120 s; `D = work × 120 / time_span` over the sorted, cut window. Below 600 blocks the whole chain is the window. | `cryptonote_config.h`, `difficulty.cpp:120-215` |
| PoW is verified on every block, **fake chain included**; there is no regtest exemption. | `blockchain.cpp:1962, 4158` (`check_hash`) |
| `--fixed-difficulty N` replaces the algorithm with a constant (no DAA at all). | `cryptonote_core.cpp:677`, `blockchain.cpp:857-859` |
| Shadow's simulated clock starts at **2000-01-01 00:00 UTC (946,684,800)** and monerosim assumes it. | `src/lib.rs`, `src/analysis/types/core.rs` |
| A block is rejected if `timestamp > now + 7200` or `timestamp < median(last 60)`. | `blockchain.cpp:3940-3988` |
| Every daemon starts `--regtest --keep-fakechain` on a data dir wiped per run; no snapshot/import support exists. | `node_impl.rs`, `main.rs` cleanup |
| Both the main chain and alternative chains compute difficulty through `next_difficulty(timestamps, cumulative_difficulties, target)`. | `blockchain.cpp` `get_difficulty_for_next_block`, `get_next_difficulty_for_alternative_chain` |
| Native mining already ships as `patches/monero-sim-mining.patch` (112 lines) in `monerod-sim`. | `patches/` |

## 3. Options

### A. Real preloaded chain (snapshot)

Generate, once per target difficulty, a chain of ≥735 blocks with **real PoW** at
`D0 = 120 × H_target` and 120 s spacing. Ship it as a data-dir snapshot; every node
starts from it, already synced to the tip. The real DAA then sees a full window at
`D0` from block one.

- **+ No daemon patch.** Works for every node implementation, cuprate included, because
  it is just a valid chain.
- **+ More realistic joining.** Nodes join a chain with history, as on mainnet, instead
  of all watching genesis.
- **+ Bonus:** the snapshot's coinbase outputs (to a known miner wallet) can shortcut
  the wallet-funding warm-up if we want them to.
- **− One-time generation costs the same hashing as the warm-up** (~86,400 × H hashes),
  parallelisable across cores, cached and keyed by (D0, monero version, HF schedule,
  network id).
- **− Timestamps.** The snapshot's blocks must be stamped *before* the run's sim clock,
  or every new block fails the median-of-60 rule until sim time catches up (~24 h).
  See §5.
- **− Logistics:** copy the snapshot into ~1,000 data dirs at generation time (LMDB of
  735 empty blocks is small, tens of MB at most), and the orchestrator's per-run wipe
  must know about it.

### B. Virtual DAA history (`--sim-daa-prefill <D0>`)

A small addition to `monerod-sim`: when the chain is shorter than the window, prepend
a synthetic history of blocks at difficulty `D0` and 120 s spacing to the vectors
handed to `next_difficulty`, in *both* the main-chain and alt-chain paths. Block 1 is
then mined at `D0`, and the real algorithm runs unchanged from there.

- **+ Tiny, deterministic, no snapshot logistics**, no timestamp problem, no extra
  hashing.
- **+ DAA response to hashrate changes is untouched.**
- **− Every implementation on the network must carry the same rule**, or it will
  compute a different difficulty and reject blocks. Fine for the monerod-only replica;
  a blocker for mixed cuprate runs unless cuprate gets the same patch.
- **− Fresh chain: all nodes still start at genesis**, so early network behaviour stays
  less mainnet-like.

### C. Longer runs

Run 40 h and discard the first 24 h. No code, but it more than doubles every
replica run (S10: ~50 h wall for 16 h simulated before spies).

### D. `--fixed-difficulty` (rejected)

Removes the DAA entirely, so hashrate changes have no effect. Not a model.

## 4. Recommendation (revised 2026-09-23, user confirmed)

**Build A. B is not needed.**

The first draft of this spec recommended B because A's timestamp problem looked
hard. It is not:
- Monero's timestamp rules only check **order** (≥ median of the last 60) and
  **not-in-the-future** (≤ now + 2 h); the DAA only uses **spacing**. A constant
  shift of every timestamp in a snapshot is therefore harmless.
- The generator does not need B either: mine ~1,450 blocks from genesis in a tiny
  native-mining sim. The first ~720 are warm-up, but they become deep history; the
  window at the tip is 735 settled blocks at `D0`, which is all a run ever reads.

So A is: **one generation-only miner flag (a few lines) + snapshot copying in the
orchestrator + one cached generation run per hashrate target.** No DAA patch, no
per-implementation rule, cuprate-safe, and nodes join a chain with history as on
mainnet. B stays documented below only as the fallback if A's plumbing proves
worse than expected.

## 5. Design details

### A: chain snapshot

**Generator run** (`test_configs/preload_chain.scenario.yaml`, a normal native
run, kept tiny so it simulates fast):
- 1–5 miners whose **total** hashrate equals the target run's, e.g. 5 × 100 h/s,
  so the settled difficulty is `D0 = 120 × 500`. No users, no relays.
- `--sim-hash-interval-ms` throttling as usual (real RandomX, sim-time spacing).
- Run until height ≥ `735 + 720 = 1,455` (~48 h simulated; small network, so a
  few hours wall).
- Miner flag **`--sim-timestamp-offset <s>`** (generation only, added to
  `patches/monero-sim-mining.patch` next to `--sim-hash-interval-ms`): the miner
  stamps blocks `now − offset`. Offset = `expected chain span + 10 min`, computed by
  the orchestrator from `height × 120 s`, so the snapshot's tip lands a few minutes
  **before** the 2000-01-01 sim epoch. Rules satisfied at generation: timestamps
  are monotone (≥ median) and in the past (≤ now + 7,200).
- Coinbase goes to a dedicated `genesis-miner` wallet whose seed is stored with the
  snapshot.

**Snapshot** = the miner's data dir after the run (LMDB, `--keep-fakechain`),
stored under `~/.monerosim/chain_snapshots/<key>/` with a `manifest.json`:
`{height, D0, total_hashrate, monero_pin, hf_schedule, network_id, tip_timestamp,
tip_hash, genesis_miner_seed}`. Cache key = hash of `(D0, monero pin, HF schedule,
network id, height)`.

**Consumer side:**
- `general.mining.chain_snapshot: auto | <path> | off` (native mode only; default
  `auto` = look up the cache by key, error with the generator command if missing).
- Orchestrator copies the snapshot into every daemon's data dir at generation
  time (`cp --sparse=always`; 1,455 empty blocks is tens of MB). `--keep-fakechain`
  already prevents daemons wiping it. Cuprate nodes get the same chain via their
  own data-dir format only if a converter exists; until then, cuprate nodes start
  empty and **sync** the 1,455 blocks from monerod peers at startup, which is the
  mainnet-like path anyway.
- Preflight checks the manifest's `monero_pin`/HF schedule against the run's, and
  that `tip_timestamp < epoch`.
- **Gap check at run start:** the first real block is stamped at
  `epoch + t`, a few minutes after the tip; the DAA window then holds 734 snapshot
  spacings and one small gap. Fine. What must be avoided is a gap of hours or more,
  which the cut window would eventually expose and crash difficulty for ~720
  blocks. Preflight enforces `epoch − tip_timestamp ≤ 30 min`.

**Tests:** manifest round-trip; orchestrator copies to N data dirs and rejects a
mismatched pin; the offset flag stamps `now − offset` (unit test in the patch);
gate run (later, when a box is available): median block interval over the first
100 blocks ≈ 120 s, difficulty at height 1,456 within ±10% of `D0`, no
rejections, all nodes at the same height.

**Funding:** `miner_distributor` may optionally fund users from the
`genesis-miner` wallet (coinbase already unlocked), shortening the funding
warm-up. Off by default; the real miners keep funding as today.

### B (fallback only): `--sim-daa-prefill`

- **Flag:** `--sim-daa-prefill <difficulty>` in `monerod-sim` (extend
  `patches/monero-sim-mining.patch` or add a fifth patch). `0`/absent = stock.
- **Semantics:** in the wrapper that both `get_difficulty_for_next_block` and
  `get_next_difficulty_for_alternative_chain` use before calling `next_difficulty`:
  if the collected history has fewer than `DIFFICULTY_WINDOW + DIFFICULTY_LAG` entries,
  prepend `k` synthetic entries so the total equals that count, with timestamps
  `t_genesis − (k−i)·120` and cumulative difficulties stepping by `D0`. The real
  entries' cumulative difficulties are offset by `k·D0` so differences stay
  consistent. The prefix is a pure function of `(D0, genesis timestamp)`, so every
  node computes the same value.
- **Orchestrator:** `general.mining.difficulty_preload: auto | <u64> | off`
  (native mode only; default `auto`). `auto` = `120 × Σ hashrate` over miners, since
  native hashrate is literal h/s. Injected into **every** daemon's options, not only
  miners, so validators agree. Preflight refuses `auto`/a value when any node is not
  `monerod-sim` (cuprate) with a message pointing at option A.
- **Tests:** unit test in the patch (a 3-block chain with prefill reports `D0` at
  every height and converges to `D0` when blocks arrive every 120 s); orchestrator
  test that `auto` computes `120 × Σ hashrate` and injects the flag on relays too;
  gate run (later): first 50 blocks arrive at ~120 s median, no rejections, height
  matches across a monerod-only network.

## 6. Out of scope

Modelling the DAA's 720-block response to hashrate changes as anything other than
what monerod does. That is real and stays.
