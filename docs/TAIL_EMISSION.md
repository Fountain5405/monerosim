# Tail emission

Mainnet Monero has been in tail emission since 2022: every block pays a
flat **0.6 XMR** base reward (0.3 XMR/min × 2-min target), forever. A fresh
simulated chain instead starts at the top of the emission curve (~35 XMR per
block). `general.emission` lets a run use mainnet's regime.

```yaml
general:
  emission:
    mode: tail          # default: stock
    from_height: auto   # or a block height; absent = auto
```

## What changes

The switch lives in monerod's `get_block_reward`, which drives:

- **the coinbase** each miner builds and every node validates;
- **the dynamic minimum fee** (`check_fee`, `get_fee_estimate`), which is
  proportional to the base reward, so fees drop to mainnet levels (~58×
  lower than a fresh chain's);
- **block template filling**: how far past the median block weight a miner
  goes is decided by fees vs the size penalty, which scales with the reward.

Because the minimum fee scales with the reward too, the break-even overshoot
past the median is about the same as before at minimum fees. Blocks grow
faster only when wallets pay above-minimum fees, as on mainnet. See
`docs/20261012_3k_slowdown_decomposition.md` for why that matters.

## Funding and `from_height`

At 0.6 XMR per block a whole network mints about 18 XMR per sim-hour, far too
little to fund hundreds of users at 10 XMR each. So the chain uses stock
emission until `from_height`, then tail:

- `auto` (default) = enough ~35 XMR blocks to mint every user's funding with
  a 1.5× margin: `ceil(users × 10 × 1.5 / 35.18)`, at least 60. For 600 users
  that is height 256. Coins minted before the switch stay spendable after it,
  so funding can happen whenever the distributor gets to it.
- A literal height, e.g. `from_height: 0` for pure tail emission from genesis
  (only sensible for runs that fund few users).

The generator logs the chosen height:
`Tail emission: 0.6 XMR base reward from height 256 (600 funded user(s); ...)`.

## Consensus: every daemon, same height

The switch is a consensus rule. A node without it, or with a different height,
rejects the first tail block (`has incorrect miner transaction`) and splits
off. monerosim therefore:

- injects `--sim-tail-emission-height=<H>` into **every** daemon, from the one
  `general.emission` setting;
- runs every daemon on `monerod-sim` in tail mode (agents with `daemon:
  monerod` or no daemon set are switched automatically; an explicit other
  binary must support the flag or generation fails);
- refuses the flag in per-agent `daemon_options` / `daemon_args`;
- refuses tail emission together with `general.node_implementations`
  (cuprate computes rewards itself; patching sim-cuprate is a follow-up).

## Binary

`patches/monero-sim-tail-emission.patch`, built into `monerod-sim` (alias
`monerod-hf`) by `./setup.sh --sim-binary`. Off by default: without the flag
the daemon behaves exactly like stock.

## Validation (2026-10-12)

- monero unit test `sim_tail_emission.switches_at_height_and_keeps_penalty`
  (stock below H, 0.6 XMR from H, size penalty and the 2× median cap still
  apply).
- Two local regtest daemons: the flagged one paid 35.18 XMR up to height 4
  and 0.6 XMR from height 5; the unflagged one accepted 1–4 and rejected
  block 5 with `has incorrect miner transaction`.
- `test_configs/tail_emission_smoke.yaml` (quickstart + tail, auto height =
  60 for 3 users; run `archived_runs/20261012_102940_tail_emission_smoke`):
  all 15 daemons on monerod-sim and armed, all at height 179, zero
  `incorrect miner transaction`, all success checks pass (180/180 txs mined).
  Base reward 35.18 XMR at height 59, 0.6 XMR from 60. Median fee 20
  nanoXMR/byte vs 1,200 in a stock quickstart run (60× lower); mainnet's
  minimum fee is ~20,000 atomic units (20 nanoXMR) per byte.
