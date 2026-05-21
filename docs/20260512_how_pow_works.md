# How block production works in monerosim

Captured 2026-05-12 from a code walkthrough during analysis of the
20260511_164600_20260511_200u_800r 1k-node validation run.

## TL;DR

Every block produced in a monerosim run is a fully valid Monero block. The
PoW hash is computed for real by stock `monerod` code, and every receiving
node runs full normal block validation including the PoW check. The only
thing we modify is the *cost* of finding a valid nonce — by running the
entire network in `--regtest` / `FAKECHAIN` mode, difficulty stays at ~1–2
so PoW is trivial to find. The *rate* at which blocks arrive is controlled
in Python by the miner agent, not by the hashing loop.

## The PoW path, step by step

Every monerod is launched with `--regtest --keep-fakechain` (see any
`shadow_agents.yaml` from a run). `--regtest` puts the daemon in
`FAKECHAIN` nettype, which:

- Pins difficulty at a very low baseline (~1–2). LWMA still runs on top of
  it, but never has anything significant to multiply.
- Enables the `generateblocks` RPC (gated at `core_rpc_server.cpp:2347`).
- Otherwise leaves all block format, validation, P2P, and consensus code
  identical to mainnet.

The miner agent (`agents/autonomous_miner.py`) calls
`MoneroRPC.ensure_mining()`, which tries `start_mining` first and falls
back to `generateblocks`. In practice `start_mining` is unavailable in
this setup, so every block comes from `generateblocks`. The path inside
stock Monero (`src/rpc/core_rpc_server.cpp:2339-2410`, unmodified vs
upstream `monero-project/monero`):

1. **`getblocktemplate`** — builds a real candidate block: pulls
   transactions from the mempool, builds the coinbase tx, computes the
   merkle root, fills the header. Identical to mainnet block construction.
2. **`miner::find_nonce_for_given_block`** — loops over nonces, computing
   `cryptonote::get_block_longhash(...)` (the **RandomX** hash) for each,
   until the result satisfies the difficulty target. This is the real PoW
   computation; the hash gets computed for real every block. At
   difficulty 1–2 the first nonce typically wins.
3. **`submitblock`** — validates the constructed block (including PoW
   hash against target) and adds it to the chain.

The new block then propagates to peers (relays, users, other miners) via
the normal P2P path. Each receiving daemon runs **full normal block
validation**, including re-computing the RandomX PoW hash and checking
it against the target. There is no special "trust this block" path —
peers accept the block only because it really does have a valid (just
trivial) PoW.

## Why we need an agent-side rate limiter

Because difficulty is regtest-low, monerod could happily produce
thousands of blocks per second if let loose. That's useless for a
simulator. So the rate-limiting lives in Python.

`agents/autonomous_miner.py:_calculate_next_block_time()` (line 261)
draws a Poisson interarrival time before each `generateblocks` call:

```
base_expected_time = 120s / (hashrate_pct / 100)   # 600s for a 20%-weight miner
difficulty_factor  = current_difficulty / baseline_difficulty
expected_time      = base_expected_time × difficulty_factor
time_to_next_block = -ln(1 - U) / (1 / expected_time)
```

A miner with `hashrate: 20`:

- Targets 600 s mean between its own blocks. With 5 such miners, the
  network gets a block every 120 s on average — matching mainnet.
- Draws an exponentially-distributed wait → realistic Poisson arrivals.
- Calls `generateblocks` for exactly **one** block when the timer fires.
- Re-queries `difficulty` each iteration, so if a new miner joins, LWMA
  pushes difficulty up, the factor rises, and waits get longer —
  recreating mainnet's hashrate-vs-difficulty feedback loop.

This is why the `hashrate` parameter in the scenario YAML is interpreted
as a weight that must sum to 100 across the initial miners: it's
literally each agent's share of total expected block production.

## What's real vs. modeled

| Component | Real / Modeled |
|---|---|
| Block header, tx body, signatures, ring sigs | **Real** (stock Monero code) |
| Coinbase / reward / emission curve | **Real** |
| RandomX PoW hash computation | **Real** (computed every block, on both producer and receivers) |
| Difficulty target | **Low** (regtest baseline) — PoW work is cheap |
| Full block validation on receive (incl. PoW check) | **Real** (stock validation path) |
| Hashrate competition between miners | **Modeled** by per-agent Poisson timer keyed on `hashrate_pct` |
| Block interarrival rate | **Targeted** at mainnet 120 s, adjusted by live LWMA difficulty |
| `start_mining` continuous-miner loop | **Unused** — agents call `generateblocks` per block instead |

The result: every block in a monerosim chain is protocol-valid. A real,
unmodified `monerod` fed this chain would accept and serve it normally.
The cost of producing PoW is fake; the shape of mining (rates,
interarrival distributions, LWMA response to hashrate changes) is
modeled explicitly by the agent.

## Why not just let nodes mine normally (via `start_mining`)?

If the PoW is real anyway, why bother with the agent-driven
`generateblocks` Poisson dance instead of just enabling `start_mining`
on every miner and letting `monerod`'s normal miner thread run?

### The actual blocker: Shadow's cooperative scheduling

Shadow is a discrete-event simulator. It only gets scheduling control
back from a managed process — and only advances the simulated clock —
**when that process makes a syscall**. As long as a process is sitting
in a tight CPU loop with no syscalls, Shadow has nothing to advance to:
no event is enqueued, no other host can run, and sim-time freezes.

`monerod`'s built-in miner thread (what `start_mining` activates) is
exactly the worst case for this model: a RandomX hash loop that grinds
nonces with effectively zero syscall traffic. We tried this in the
early days of development and the symptom was very clear — when miners
were started via `start_mining`, the simulation stopped advancing in
sim-time. The miner thread monopolized the Shadow worker thread, no
other host got scheduled, and the simulated clock sat at startup.

This is the same class of problem that the `native_preemption` knob
(documented in `docs/PERFORMANCE_AND_SCALE.md`) was added to mitigate
for block-validation hot paths: a signal-based ~10 ms forced yield so
CPU-bound code can't monopolize a worker. But:

- Preemption only helps relative to *competing* hosts on the same
  worker; it doesn't help if the miner thread is the only work the
  scheduler has to choose from.
- Block validation is a short burst of CPU and then done. Mining is an
  unbounded grind. Preempting a `while(true)` hash loop still leaves
  you running the hash loop — you just trade between it and other
  hosts; the loop itself never makes progress that *advances sim
  time*, because it isn't tied to a sim-time event.

So even with `native_preemption: true` (which is now the default for
large sims), `start_mining` is the wrong tool. The simulated clock
isn't a function of how much CPU the miner burns — it's a function of
when something makes a blocking syscall — and a hash grinder never
does.

`generateblocks` sidesteps the whole problem because it is a one-shot
RPC: the agent calls in, monerod finds the (trivial) nonce, submits the
block, returns. The agent then `sleep`s the Poisson interval — a
blocking syscall that *does* advance sim-time. The simulator stays
healthy because every block costs a bounded amount of CPU bracketed by
syscalls Shadow can see.

### What about trivially-low difficulty?

A natural follow-up: if the problem is the hash grinder never making
syscalls, why not just set difficulty to 1 so it finds nonces
immediately? Then `start_mining` would constantly be submitting blocks,
which *are* syscalls, and sim-time would advance.

That swaps one failure mode for another. At difficulty ~1:

- The miner thread finds a nonce in roughly one RandomX hash attempt
- It submits the block (a syscall — sim-time advances a hair)
- It immediately builds the next template and finds the next nonce
- ... at wall-clock RandomX hash speed (~1 ms per attempt → ~1000
  blocks per second of wall clock, with almost no sim-time accumulated
  between submissions)

Per simulated minute, you'd get thousands of blocks. The block rate
becomes a function of your CPU's RandomX hashing speed, which is the
worst possible input to "did this simulation match a target block rate?"

So the two failure modes bracket the usable range:

| Difficulty | What `start_mining` does | Outcome |
|---|---|---|
| Realistic (~GH range) | Hash thread spins, never finds a block | No syscalls → sim-time freezes |
| Trivial (~1) | Hash thread finds blocks instantly, submits at wall-clock pace | Block rate decouples from sim-time → runaway production |

There's no goldilocks setting between them. The underlying reason: real
Monero uses PoW expense as the *throttle* on block rate. We've
trivialized PoW (necessary for simulation speed), so the throttle is
gone, and `start_mining` has no other throttle — it just mines as fast
as it can.

`generateblocks` reinjects the throttle in user-space. The agent owns
the timing decision: each block is one explicit RPC call, and
`time.sleep()` between calls (a real syscall) is what advances sim-time
and rate-limits production. Block rate becomes a function of agent
decisions, which is what we want for modeling declared hashrate
weights, adversarial strategies, etc.

### Secondary reasons (which would still apply even if scheduling weren't an issue)

These don't dominate the decision, but they reinforce that the
agent-driven design is the right one even setting Shadow aside:

- **No real parallel race in Shadow.** Mining on mainnet is a global
  hashpower race. Shadow serializes CPU through its worker pool, so
  there is no parallel grinding happening across miners. You cannot
  enforce a 20/20/20/20/20 hashrate split by letting `start_mining`
  run — every miner would just chew its scheduled slice equally. The
  split has to be imposed in user-space.
- **Determinism / reproducibility.** Agent-driven Poisson timing
  derived from `simulation_seed` is exactly reproducible run to run.
  A real miner loop's nonce-hit timing depends on cache and scheduling
  effects we don't want as inputs to "did the test pass?"

### The core insight

On the real network, "mining" is the protocol's mechanism for *electing*
a block producer fairly. The election runs via global parallel hashing
because there is no central authority and no shared clock. In a
simulator, we *are* the central authority and we *do* have a shared
clock (Shadow's sim-time). So the right design is to elect the producer
in Python (sample from a weighted Poisson process keyed on hashrate
weights), then have stock `monerod` construct and PoW-sign that block
via `generateblocks`. Real PoW is preserved on every block — every
receiving node still validates the RandomX hash — but the election is
moved out of the hash grinder and into agent code, where it interacts
with Shadow's scheduler correctly.

## Validity envelope — what this faithfully reproduces and what it doesn't

The hack — a Python agent firing `generateblocks` on a Poisson schedule
— produces **network-level behavior that is statistically indistinguishable
from a real PoW network** when looked at as a sequence of block events:

- **Block interval distribution is exponential** with mean ≈ target.
  Verified empirically across 3 different runs spanning 3 months
  (2026-02-16, 2026-03-05, 2026-05-11): in all three, median interval
  sat right at 2 sim-minutes, mean was within ~50% of target (long-tail
  Poisson skew), and a chi-square-style fit to the observed exponential
  is good to within ~3 percentage points across the 0-30s / 0-60s / 0-2m
  / 0-3m / 0-5m cumulative bands.
- **Each block is fully consensus-valid.** Real RandomX hash, real
  signatures, real ring sigs, real coinbase, real propagation, real
  validation by every receiving peer using stock `monerod` code paths.
- **LWMA difficulty adjustment runs.** The orchestrator does not patch
  difficulty logic; LWMA observes actual block-interval samples and
  adjusts within its normal feedback envelope (we observe oscillation
  between 1 and 4 in regtest baseline).
- **Per-miner block share matches hashrate weights** because the agent
  timer is hashrate-weighted by design.

What you **give up** in exchange:

- **Mining-economics fidelity.** Selfish-mining strategies, fee-market
  dynamics under hashpower competition, and any phenomenon that depends
  on actual hashpower cost vs. block reward — none of these are
  modeled. The "election" of which miner produces each block is decided
  by Python (weighted Poisson) rather than by a real hashing race, so
  the strategic surface that mining economics studies operates on isn't
  exposed.
- **Reorgs / chain forks are under-represented.** Real Monero
  occasionally sees natural reorgs from network propagation delays and
  near-simultaneous discoveries on multiple continents. Our model
  elects one block producer per height deterministically; competing
  blocks at the same height don't get authored. We do see *occasional*
  reorgs in the daemon logs (from edge cases in our propagation
  ordering), but at a much lower rate than mainnet. **Any research
  premised on reorg dynamics — selfish mining, double-spend windows,
  finality analysis — should treat results from this simulator with
  skepticism.**
- **Difficulty range is regtest-shaped (1..~10).** LWMA works, but it
  has very little dynamic range above the regtest baseline. Research
  that depends on the *absolute* difficulty value, or on quantization
  effects in the adjustment formula at mainnet-scale numbers (~10^11),
  won't surface in this simulator. See the README's "Known
  limitations" for the larger context.
- **Per-block PoW cost is artificially trivial.** Real mainnet miners
  spend ~10^15 RandomX hashes per block; this simulator does 1-2 (one
  nonce loop at regtest difficulty). Doesn't affect protocol-level
  correctness, but it means *cost*-related phenomena (e.g., timing
  attacks on hashpower withholding) can't be studied here.

**Summary for the README's known-limitations list:** the simulator is
validated for **protocol-level network research** (block propagation,
sync behavior, transaction flow, peer-discovery dynamics, upgrade
scenarios, mempool dynamics). It is **not validated for mining-economics
research** (reorgs, selfish mining, fee-market behavior under
hashpower competition), and any such usage should be a separate
investigation with that limitation explicitly accepted up front.

## Sanity-check from the 1k-node run

`miner-001` log, sim 00:07:24:

```
Detected available methods: {'start_mining': False, ..., 'generateblocks': True}
Block generated successfully via generateblocks height=2 hash=0d4939…
```

271 blocks across 16 sim-hours = roughly one block every 3.5 sim-minutes
on average. That's slower than the 120 s mainnet target because miners
spent the early hours waiting for `--fixed-difficulty` ramp-up and the
chain only got to height ~21 by sim hour 2 before catching up later.
The system is rate-controlled, not work-limited.
