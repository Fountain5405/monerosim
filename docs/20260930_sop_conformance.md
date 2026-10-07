# Share-or-Perish conformance: decision log and spec oracle (2026-09-30)

Every Share-or-Perish (SoP) fork-choice evaluation in `monerod-sim` logs its
inputs and its result on one line. `scripts/sop_oracle.py` recomputes each
decision from the rules of MRL #146 below, using only the logged inputs, and
flags every disagreement. The oracle is written from this document and the
spec text. It must not be derived from `patches/monero-sim-pop.patch`: its
value is that it is an independent reading of the spec.

Why: the 2026-09-30 audit found the simulator's SoP deviating from the spec in
the fallback weights, in which shares a block carries, in the lateness
reference and in re-judging displaced blocks. Each deviation surfaced only
after campaigns had run on it. With the oracle, a deviation shows up in the
first smoke run.

## The spec's rules (MRL #146, tevador, 2025-09-25)

Source: <https://github.com/monero-project/research-lab/issues/146>.
Parameters: `w = 16` (workshare ratio), `d = 5 s` (propagation delay),
`k = 3` (partition recovery).

- **Work objects.** A block header, or a workshare: "a distinct PoW header that
  meets at least 1/w of the current block difficulty and has the same
  `prev_id` value as the containing block". Blocks include workshares; "on
  average, a block will contain w-1 workshares".
- **Chain weight (Table 3).** With `t` the chain tip height, a block at height
  `h > t - 10*w` weighs `l_b*diff(h)/w` for its header plus
  `l_b*l_w*diff(h)/w` for each workshare. A block at `h <= t - 10*w` weighs
  `diff(h)`, and its workshares weigh `0`.
- **Fork variables.** "Let there be an alt-chain that forks off the main chain
  at height `h_f` and contains `n_f` work objects that are not contained in
  the main chain." `h_0` is "the block height when the node came online".
  `block_seen` and `share_seen` are when the node first saw the evaluated
  block or share. `main_seen` is when it first saw "the main chain block of
  height h. If the main chain block of height h doesn't exist (i.e. the
  alt-chain is ahead), we set `main_seen = block_seen`."
- **Lateness (Tables 4 and 5).** `l_b = 0` if
  `h_0 < h_f && n_f < k*w && block_seen - main_seen > d`, else `1`.
  `l_w = 0` if `h_0 < h_f && n_f < k*w && main_seen - share_seen <= d`,
  else `1`. "The lateness factors can be distinct from 1 only if the node was
  online before the fork height and the two chains differ by fewer than
  `k*w` work objects."
- **Ties.** "If a node sees two chains of the exact same weight, it makes a
  random selection."

Outside the window (`n_f >= k*w`, or `h_0 >= h_f`) the lateness factors are
all 1, and Table 3 still applies: a recent block weighs `diff/w` times
`1 + (its workshares)`. That regime is called OBJECTIVE below. It is not plain
cumulative difficulty.

## Conventions where the spec is silent

Each is a choice. The oracle and the daemon must both follow it.

1. **What is compared.** The weights of the two chains' blocks above the last
   common block, the "suffixes". The common prefix is identical in both
   chains and is left out.
2. **`t` for the 10·w window** is the node's main-chain tip height `top`. For
   forks shallower than `10*w = 160` blocks, every suffix block is inside the
   window either way.
3. **`h_f`** is the height of the first alt block. `h_0 < h_f` means the node
   was online before the first diverging block.
4. **`share_seen` for a share never gossiped to the node** is the `seen` time of
   the block that contains it, since the node first sees the share inside that
   block.
5. **Unknown receive times** (`seen` null) make the factor permissive (1).
   Grafted chain-snapshot blocks have no receive time, but they are older than
   any fork.
6. **Whole branches, not parts.** When a reorg displaces blocks, monerod
   re-inserts them one at a time. In `whole_branch` mode those re-insertions
   are stored without judging (`skipped: true`). A displaced branch is judged
   again, as a whole, when a new block extends it. This is the reading that
   tevador's own security analysis assumes. `rejudge` mode judges every
   re-insertion; it is kept for the implementation-hazard measurement.
   It is the daemon flag `--sim-sop-rejudge-displaced`, off by default.
7. **One draw per tie.** The daemon caches the random draw per (alt tip, main
   tip) pair, so re-judging the same pair cannot re-roll it.
8. **Share validity.** The slot rule itself is the spec's: miners set
   `version_minor` to the number of included workshares, whose slots run
   `0..N-1`. Every share's PoW must meet `diff/w`. The spec does not say
   what follows from a violation; its "requires" suggests the block is
   invalid. Our convention is more lenient: `n_sh = 0`, and the block counts
   as its header alone, both in `n_f` and in weight. *(Relabelled
   2026-10-07: this was listed as if the whole rule were ours. No violating
   block occurred in the runs checked.)*
9. **Sim-only guard.** The regime is objective when the first alt block's
   difficulty is below `w`. Fakechain bootstrap difficulties never occur with a
   chain snapshot.
10. **Integer arithmetic.** `unit = max(1, floor(diff / w))`. A recent block
    weighs `unit * (l_b + l_b * (number of counted shares))`, and an old one
    weighs `diff`.


## Known deviation (found 2026-10-07)

- **`n_f` counts shared workshares.** The spec counts the alt chain's work
  objects "that are not contained in the main chain". The daemon and the
  oracle count every alt block and every share it embeds. That includes
  shares the main chain's block at the fork height also embeds; both
  blocks have the same parent, so their shares can coincide.
  - Affected: forks whose first blocks share workshares, e.g. two honest
    miners' competing blocks. There `n_f` can reach `k*w` early, and the
    window close sooner than the spec says.
  - Not affected: attack forks in our setup, because the attacker's
    offline miner never holds honest shares.
  - Not fixed: it needs a daemon change and a rebuild.

## Log line

One line per evaluation, in the daemon log (`bitmonero.log`), where the
message is `SIM-SoP-DEC ` followed by a single-line JSON object:

| field | type | meaning |
|---|---|---|
| `v` | int | format version, `1` |
| `mode` | str | `"whole_branch"` or `"rejudge"` |
| `reinsert` | bool | evaluation triggered by re-inserting a displaced block |
| `skipped` | bool | whole_branch mode skipped it; `result` is then `"KEEP"` |
| `h0` | int | the node's `h_0` |
| `hf` | int | height of the first alt block |
| `top` | int | height of the main-chain tip |
| `w`, `k`, `d_ms` | int | parameters (`d` in milliseconds) |
| `alt` | list | alt-suffix blocks, ascending height |
| `main` | list | main-suffix blocks (`hf..top`), ascending height |
| `nf` | int | the daemon's `n_f` |
| `regime` | str | `"subjective"` or `"objective"` |
| `w_alt`, `w_main` | str | the daemon's suffix weights (decimal strings) |
| `tie` | bool | `w_alt == w_main` |
| `tie_draw` | str/null | `"random"`, `"cached"` (the pair was drawn before), `"det"` (only under the PoP det-tie flag, never in SoP cells), or null when there is no tie or the evaluation was skipped |
| `result` | str | `"SWITCH"` or `"KEEP"` |

Each block entry: `h` (int), `id` (hex), `diff` (decimal string), `seen` (ms
or null), `n_sh` (int; 0 when the set does not conform), and `shares`, a list
in slot order of `{"id": hex, "seen": ms or null}`. `shares` is present when
`n_sh > 0`. A share's `seen` is its first gossip receipt, or null if it never
arrived by gossip.

The daemon skips the per-share list for main-suffix blocks at heights
`<= top - 10*w`, which never occur in practice (see convention 2).

## Hand-worked cases (expected oracle results)

`diff = 1216` everywhere, so `unit = 76`. `h0 = 994`, `hf = 1000`, `k*w = 48`,
`d = 5000 ms`. Times are in ms.

1. **Objective, shares decide (the smoke's T1 under the spec).** Alt: 7
   blocks at 1000..1006 with `n_sh` 8, 8, 9, 8, 9, 8, 9 (59 shares, `nf = 66`).
   None of the shares was gossiped. Main: 6 blocks at 1000..1005 with 15 shares
   each. Objective. `w_alt = 76*66 = 5016`, `w_main = 76*6*16 = 7296`, so KEEP.
   (Plain cumulative difficulty would have switched: 7 blocks beat 6.)
2. **Subjective, displaced prefix (the loop case).** The node is on the
   attacker chain. Alt: 1 honest block at 1000, `seen = 0`, with 11 shares
   gossiped at `seen = -60000`. Main: 7 attacker blocks at 1000..1006 with
   `seen` 2,160,000 onward and 8 never-gossiped shares each. `nf = 12`, so
   subjective. The alt block is not late (it was seen before the main block),
   and its shares count, so `w_alt = 76*12 = 912`. The main blocks have
   `l_b = 1` but their shares are not early, so `w_main = 76*7 = 532`.
   Result: SWITCH in `rejudge` mode. In `whole_branch` mode with
   `reinsert: true` it is skipped (KEEP).
3. **Late alt block.** Subjective. The alt block is seen 6000 after the main
   block at its height, so `l_b = 0` and it weighs 0, shares included.
4. **Share timing edge.** A share seen exactly `d` before `main_seen` does not
   count (`<= d`). One seen `d + 1` before it does.
5. **Alt ahead.** An alt block at a height above `top` takes
   `main_seen = its own seen`, so `l_b = 1`. Its shares count only if seen
   more than `d` before the block itself.
6. **Late joiner.** With `h0 >= hf` the regime is objective, even with a
   small `nf`.
7. **Tie.** Equal weights: `tie: true`, and the daemon draws.
8. **Non-conforming set.** `n_sh = 0`: the block is its header alone in
   `nf` and in weight.
9. **Old block.** A suffix block at `h <= top - 160` weighs its `diff`.
