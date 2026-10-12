# Plan: simulate mainnet tail emission (2026-10-12)

**Status: D1–D5 implemented with the recommended answers to all four open
questions (tail-only switch; full-then-tail at H; cuprate guarded; default
stays stock). D4.5 (capacity re-derivation) and D6 still open. Usage:
docs/TAIL_EMISSION.md.** Deviation from D1: instead of adding a height
parameter to `get_block_reward`, the patch adds `get_block_reward_at_height`
and moves all six consensus/template/fee call sites to it (the stock function
stays unchanged, so upstream tests compile); the switch works by treating the
supply as exhausted, so the stock tail floor and size penalty do the rest.

Goal: let a simulation run under mainnet's current emission regime — a
flat 0.6 XMR base reward per block (tail emission, 0.3 XMR/min × 2-min
target) — instead of the ~35 XMR early-chain reward our fresh regtest
chains pay today.

## Why it matters beyond the coinbase amount

`get_block_reward()` (src/cryptonote_basic/cryptonote_basic_impl.cpp:83)
is a single choke point used by every consensus-relevant path:

| caller | effect of the base reward |
|---|---|
| cryptonote_tx_utils.cpp:95 (construct_miner_tx) | coinbase amount |
| blockchain.cpp:1408 (validate_miner_transaction) | consensus check on coinbase |
| tx_pool.cpp:1578/1632 (fill_block_template) | which txs a miner adds past the median (penalty vs fees) |
| blockchain.cpp:3572 / 3663 (check_fee, dynamic fee estimate) | **minimum relay fee and the wallet's fee** |

So the reward drives three behaviours we care about:

1. **Fees.** The dynamic fee scales with the base reward. At ~35 XMR our
   sim fees are ~58× mainnet's; at 0.6 they become mainnet-like.
2. **Block-size growth.** A miner exceeds the median only while fees beat
   the penalty `reward × ((W−M)/M)²`. The 2026-10-12 analysis found a
   ~1.5 kB break-even overshoot at 35 XMR; at 0.6 XMR (and correspondingly
   lower fees) the balance does not obviously shift: the dynamic minimum fee
   is itself proportional to the reward, so at minimum fees the break-even
   overshoot `fee × M² / (2 × reward × tx_weight)` is roughly unchanged.
   Growth needs fees *above* the minimum (wallet priority), as on mainnet.
   To be **measured**, not assumed. This directly changes the "~4,500 tx per
   sim-hour" capacity rule in PERFORMANCE_AND_SCALE.md.
3. **Miner income / funding.** At 0.6 XMR/block the whole network mints
   ~18 XMR per sim-hour. The current funding flow (distributor pays users
   from ~35 XMR coinbases) cannot fund hundreds of users from tail rewards.

Patching only the coinbase amount would be wrong: fees and template
filling must follow, or the sim would combine a mainnet reward with
early-chain fee economics.

## Design

### D1. Daemon patch: `--sim-tail-emission-height=<H>`

New patch `patches/monero-sim-tail-emission.patch`, built into
monerod-sim (and therefore monerod-hf, which is a symlink to it):

- A process-global `sim_tail_emission_height` in cryptonote_basic (default
  `UINT64_MAX` = off), set from a core command-line arg at init, like the
  existing `--sim-*` flags.
- In `get_block_reward`, if the block being rewarded is at height ≥ H,
  `base_reward = FINAL_SUBSIDY_PER_MINUTE × target_minutes` (0.6 XMR),
  then apply the normal size penalty unchanged.
- `get_block_reward` has no height parameter today. Options: (a) add a
  height argument and update the ~6 callers, or (b) set a thread-local
  "current height" before each call. (a) is cleaner and compiler-checked;
  recommend (a).

Why a height and not "always on": the users still need funding (see D3).
H = 0 gives pure tail emission from genesis for runs that don't need it.

Alternative considered: an `already_generated_coins` offset (simulates
any point on the emission curve, not just the tail). More general, but it
touches overflow edges, RPC-reported supply and invites misuse; mainnet
is in tail emission forever, so the tail-only switch is the useful case.
Can be added later behind the same plumbing if historic eras are wanted.

**Consensus:** every daemon must run with the same H, or blocks after H
are rejected ("coinbase transaction spend too much money") and the
network splits. The orchestrator owns this (D2).

### D2. monerosim config + orchestration

- Config: `general.emission: { mode: tail, from_height: <H|auto> }`
  (default: absent = stock emission; byte-identical goldens).
- The orchestrator injects `--sim-tail-emission-height=H` into **every**
  monerod/monerod-hf daemon, including the selfish-miner's offline miner
  and native-mining miners — never per-agent, never overridable per node.
- Preflight guards:
  - binary must advertise the flag (`--help` grep, like existing checks);
  - **cuprate nodes + tail emission → hard error** for now (sim-cuprate
    computes rewards itself; mixing = chain split). Patching sim-cuprate is
    a follow-up (D6).
  - `from_height` lower than the funding height (D3) → warning.

### D3. Funding under tail emission

Options, in order of preference:

1. **Full emission until H, tail after (recommended).** Funding happens
   under normal ~35 XMR rewards; H is set just past the point where users
   are funded and their outputs matured. `from_height: auto` = generator
   computes H from funding needs (users × funding amount ÷ reward, plus
   60-block coinbase maturity + 10-conf margin). Runs then measure only
   the tail regime. Downside: the chain carries a fat early supply — fine,
   nothing in the sim reads total supply.
2. Pure tail from genesis + much smaller user balances. Needs ~10,000
   blocks to fund 600 users at 10 XMR; even at 1 XMR it takes ~33 sim-h.
   Only viable for small runs.
3. Preloaded chain: native mining already preloads a 720-block chain for
   the DAA; that chain could also carry the funding coinbases, with H =
   preload tip. Elegant, but couples emission to the preload path; revisit
   once mainnet-replica (other machine) settles its own genesis story.

### D4. Validation

1. Unit test in the patch (or a tiny gtest): reward = 0.6 XMR at h ≥ H,
   stock below; penalty still applied above the median.
2. Quickstart-size smoke with `from_height` low:
   - daemon log `block reward: 0.600000000000(...)` from H on;
   - `get_fee_estimate` drops by the expected factor at H;
   - all nodes stay on one chain, zero coinbase-rejection lines.
3. Negative test: one daemon without the flag → it rejects block H (proves
   the guard in D2 is necessary, and that the patch is consensus-real).
4. Wallet/agent run past H: txs still created, accepted, mined (fees now
   lower; check agents don't hard-code fee/priority assumptions).
5. Re-run the 3k-style capacity probe (or a cheaper over-capacity 1k)
   under tail emission and re-derive the block-capacity rule.

### D5. Docs

docs/TAIL_EMISSION.md (usage, consensus warning, funding height),
PERFORMANCE_AND_SCALE.md capacity section updated with the measured
tail-regime numbers, CHANGELOG.

### D6. Follow-ups (not in first cut)

- sim-cuprate patch for the same switch (Fountain5405 fork), lifting the
  cuprate guard.
- Make tail emission the **default** for mainnet-like configs once
  validated (needs a user decision; changes fee/goldens behaviour).
- Mainnet-replica branch: adopt the flag (owned on the other machine).

## Open questions for the user

1. Tail-only switch (recommended) or a general emission-curve offset?
2. Funding: full-then-tail at height H (recommended) vs pure tail +
   small balances?
3. Cuprate: guard now and patch later (recommended), or patch both
   implementations in the first cut?
4. Eventually default-on for mainnet-like scenarios?

## Rough effort

D1 patch + unit test: half a day. D2 orchestration/preflight + goldens:
half a day. D3 auto-height: a few hours. D4 smoke/negative/wallet: a few
hours of runs. D4.5 capacity re-derivation: one overnight run.
