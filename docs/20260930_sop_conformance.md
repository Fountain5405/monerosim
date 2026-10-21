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

*Updated 2026-10-16 for the issue's revision of 2026-10-15:* `n_f` covers
both chains, `main_seen` is fixed per height, "seen" is defined, and
`version_minor` is offset by `version_major`. Log format v2 carries the
lateness reference. The earlier text is kept below where runs depend on
it, since every campaign-7 run used it.

## The spec's rules (MRL #146, tevador, 2025-09-25; revised 2026-10-15)

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
- **Fork variables (revised).** `h_f` is the last common block of the alt
  chain and the main chain. `n_chain(h)` is the number of work objects in a
  chain from height `h+1` to its tip, and
  `n_f = max(n_main(h_f), n_alt(h_f))`. `h_0` is "the block height when the
  node came online". `block_seen` and `share_seen` are when the node first
  saw the evaluated block or share.
- **`main_seen` (revised).** It is "the unix timestamp when a block of height
  `h` that became part of the node's main chain was first seen by the node.
  This value is recorded when the block becomes part of the main chain and
  is not changed by later chain switches. If no block of height `h` has been
  part of the node's main chain (i.e. the alt chain is ahead), we set
  `main_seen = block_seen`."
- **"Seen" (new).** It "requires the block to pass PoW validation and have
  a known parent block. Blocks arriving out of order are not considered
  'seen' until they satisfy the rule."
- *Earlier text (before 2026-10-15), used by campaign 7:* `n_f` counted the
  alt chain's "work objects that are not contained in the main chain", and
  `main_seen` was when the node first saw "the main chain block of height
  h", which changes when the node switches. The v1 log records reproduce
  it (the oracle replays them with rule `alt`).
- **Lateness (Tables 4 and 5).** `l_b = 0` if
  `h_0 < h_f && n_f < k*w && block_seen - main_seen > d`, else `1`.
  `l_w = 0` if `h_0 < h_f && n_f < k*w && main_seen - share_seen <= d`,
  else `1`. "The lateness factors can be distinct from 1 only if the node was
  online before the fork height and the depth of the fork is fewer than
  `k*w` work objects." The author's comment of 2026-10-15 adds that lateness
  is judged on both chains: "The 'original' main block can never be judged
  late even after a chain switch."
- **Workshare slots (revised).** Miners set `version_minor` to
  `version_major` plus the number of included workshares. The shares carry
  sequential `version_minor` values from `version_major` to
  `version_minor - 1`. This keeps stock monerod's vote check
  (`version_minor >= version_major`), so SoP stays a soft fork. *Earlier
  text:* `version_minor` equalled the share count, with slots `0..N-1`.
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
   was online before the first diverging block. The revised text defines
   `h_f` as the last common block, one lower, so from log v3 the window
   test is `h_0 < hf - 1` (the daemon: `h0 + 1 < hf`). Logs v1 and v2
   tested `h_0 < hf`. The strict test keeps a fork off the block the node
   started on objective: the node may have missed the gossip of shares
   mined on that block before it came online.

   `h_0` is the node's tip once it has caught up and follows the network
   live. From log v3 the node comes online when monerod first counts it
   as synchronized, which it must be before it mines: at its first sync
   ("You are now synchronized with the network"), with `h_0` its tip
   then. The attacker's private miner runs `--offline`, which monerod
   counts as synchronized from startup; it never syncs, so it comes
   online at startup with the database tip as `h_0`. The daemon logs
   `SIM-SoP: online, h0=...` when the node comes online. Until then the
   node judges every fork objectively (record field `online: false`):
   its receive times are download times, not live observation. Logs v1
   and v2 used the database tip at startup throughout.
4. **`share_seen` for a share never gossiped to the node** is the `seen` time of
   the block that contains it, since the node first sees the share inside that
   block.
5. **Unknown receive times** (`seen` null) make the factor permissive (1).
   Grafted chain-snapshot blocks have no receive time, but they are older than
   any fork.

   **Recording "seen" and `main_seen`.** The daemon records a block's
   receive time when the block enters `add_new_block`. It drops that time
   again if the block is orphaned (unknown parent) or fails verification,
   which includes PoW. So a block that arrives out of order is seen when it
   next arrives with a known parent. `main_seen` for height `h` is set once,
   to the receive time of the first block at `h` to join the main chain;
   later switches don't change it. Heights with no recorded time (loaded
   from disk, or the alt chain is ahead) log `ref: null`, which means
   `main_seen = block_seen`.

   A gossiped share is recorded only if its parent (the block at `h - 1`
   it builds on, main or alt) is known. Otherwise the node drops it and
   doesn't relay it, so it first sees the share from another peer or
   inside its block. The share's PoW is checked when weights are computed;
   one that fails keeps a receive time but never counts. In the 12 stage-A
   runs on the rev2 build, and the first part of three 240 h runs, no share
   was dropped for an unknown parent.
6. **Whole branches, not parts.** When a reorg displaces blocks, monerod
   re-inserts them one at a time. In `whole_branch` mode those re-insertions
   are stored without judging (`skipped: true`). A displaced branch is judged
   again, as a whole, when a new block extends it. This is the reading that
   tevador's own security analysis assumes. `rejudge` mode judges every
   re-insertion; it is kept for the implementation-hazard measurement.
   It is the daemon flag `--sim-sop-rejudge-displaced`, off by default.
7. **One draw per tie.** The daemon caches the random draw per (alt tip, main
   tip) pair, so re-judging the same pair cannot re-roll it.
8. **Share validity.** The slot rule itself is the spec's (revised:
   `version_minor = version_major + N`, slots `version_major..version_minor-1`;
   before 2026-10-15, `version_minor = N`, slots `0..N-1`). Every share's PoW
   must meet `diff/w`. The spec does not say
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
11. **`n_f` rule.** The window is open while both `nf` (alt) and
    `nf_main` are below `k*w`: the revised spec, logged as
    `nf_rule: "either"`. The daemon option `--sim-sop-nf-rule`, which also
    offered the earlier alt-only reading (`alt`, its default), was removed
    after campaign 8. The oracle uses the rule a record logs, and records
    from before the option mean `alt`.


## Revised 2026-10-16 and 2026-10-20 (log v4)

Source: the issue body as edited 2026-10-16 22:07 and 2026-10-20 16:47 UTC
(GitHub edit history). Rules for v4 records; v1-v3 records keep the rules above.

- **Window (2026-10-16).** `n_max` is the larger branch's count of work objects
  above h_f+1: the first block after the fork (its header and its shares) is not
  counted, nor are pool shares. Subjective iff the node came online before the
  fork (`online` and `h0 < hf - 1`, with `hf` the first fork block in the log),
  `h_max - h_f < 10*w`, `n_max < (k-1)*w`, and the first alt block's difficulty
  is >= w (convention 9). Else objective if `h_max - h_f < 10*w`, else nakamoto.
  `h_max` = max(top, last alt height); `h_f` = hf - 1.
- **Scores (Table 3, 2026-10-20).** nakamoto: header diff, shares 0, pool 0.
  objective: header unit, each valid embedded share unit, each counted pool
  share on the chain's tip unit_pool. subjective: as v2/v3 (l_b, l_w), pool 0.
  `unit = max(1, diff // w)` per block; `unit_pool = max(1, pool_diff // w)`.
- **Pool shares (convention 11, R2).** A chain's pool shares are the pooled
  shares with `prev_id` = the chain's tip and height tip+1 whose PoW passes
  (`pow_ok`). Per slot keep the first seen; count the contiguous run of slots
  `major, major+1, ...`. `pool_diff` is the tip block's difficulty (sim
  convention, exact under constant difficulty).
- **Evaluation (convention 12, R3).** The fork choice runs when an alt block
  arrives, as in monerod. A share arriving does not re-run it.
- **Two chains (convention 13, R4).** main against the alt chain being
  extended. `alt_tips` counts alt tips whose fork is within 10*w of top.

Log v4 (`SIM-SoP-DEC`): all v3 fields (with `"v":4`), plus
`n_alt`, `n_main` (objects above h_f+1), `nakamoto` (bool), `major` (int),
`alt_tip`, `main_tip` (hex ids), `pool_alt`, `pool_main` (lists of
`{"id","slot","seen","pow_ok"}`), `pool_diff_alt`, `pool_diff_main` (strings),
`pool_alt_counted`, `pool_main_counted` (ints), `alt_tips` (int). `regime` is
one of `subjective`, `objective`, `nakamoto`. `nf`/`nf_main` keep their v3
meaning for older tools.
Share admissions log `SIM-SoP: pooled (local|remote) share <id> at height <h>
prev <prev_id> slot <s> tip <0|1>` (for the R3 probe).

## Known deviations

- *Fixed in log v3:* **`h_0` at the last common block (found
  2026-10-16).** Logs v1 and v2 opened the window when `h_0 < hf` (first
  alt block); the revised spec needs `h_0 <` the last common block. A node
  that came online exactly at the last common block's height got a
  subjective window where the spec says objective. Over the first 400
  decisions of every node log in 155 archived SoP runs, 134 of 78,430
  decisions, in 7 runs, were such cases (forks off the snapshot tip); 45
  were subjective, and 2 outcomes would change, both in a `rejudge` run.
- *Fixed in log v3:* **`h_0` for a node that starts behind the network
  (found 2026-10-16).** Logs v1 and v2 took `h_0` as the database tip at
  startup. A node that started after the network had mined past that tip
  got an `h_0` below the height at which it came online, so it could judge
  forks it received only while catching up as if it had seen them live.
  We read "the block height when the node came online" as the node's tip
  once it has caught up and follows the network live; from log v3 that is
  its tip at its first sync (convention 3). Every matrix daemon starts on
  the snapshot tip, but not at once: miners at 0 s, seeds at 5 s, and
  relays at 30 s and 60 s (12 daemons) or every 10 s up to 260 s (40
  daemons). Checked 2026-10-19 over 166 archived SoP runs, 73 of them with
  decisions up to height 1050 (11,152 decisions): 62 deciding nodes, all
  relays, came online one to three blocks above their database tip (18 in
  14 of 70 twelve-daemon runs, and 44 of the 72 relays in the three
  40-daemon runs). None decided while catching up. 14 of their decisions were on
  forks off a block at or below the height they came online at, all in
  one run and all objective under either `h_0` (a branch held at least 57
  work objects), so no regime or outcome changed. From log v3 a node also
  judges every fork objectively until it comes online, so a fork it meets
  while catching up is judged on work alone. No archived decision was
  taken before its node came online.
- *Resolved by the revision (found 2026-10-07):* **`n_f` counts shared
  workshares.** The earlier text counted the alt chain's work objects "that
  are not contained in the main chain". The daemon and the oracle count
  every alt block and every share it embeds, including shares the main
  chain's block at the fork height also embeds; both blocks have the same
  parent, so their shares can coincide. The revised `n_chain(h)` counts
  every work object in the chain above `h`, which is what we count. Under
  the earlier text it affected forks whose first blocks share workshares,
  such as two honest miners' competing blocks, not attack forks in our
  setup.

## Log line

One line per evaluation, in the daemon log (`bitmonero.log`), where the
message is `SIM-SoP-DEC ` followed by a single-line JSON object:

| field | type | meaning |
|---|---|---|
| `v` | int | format version: `3` after campaign 8 (window test on the revised `h_f`, `h_0` from the first sync, `online`: convention 3), `2` from 2026-10-15 (block entries carry `ref`), `1` before |
| `mode` | str | `"whole_branch"` or `"rejudge"` |
| `reinsert` | bool | evaluation triggered by re-inserting a displaced block |
| `skipped` | bool | whole_branch mode skipped it; `result` is then `"KEEP"` |
| `h0` | int | the node's `h_0` at this decision; from v3 the database tip until the node comes online, then the tip it came online at (convention 3) |
| `online` | bool | from v3: whether the node had come online (convention 3); `false` forces the objective regime |
| `hf` | int | height of the first alt block |
| `top` | int | height of the main-chain tip |
| `w`, `k`, `d_ms` | int | parameters (`d` in milliseconds) |
| `alt` | list | alt-suffix blocks, ascending height |
| `main` | list | main-suffix blocks (`hf..top`), ascending height |
| `nf` | int | work objects in the alt suffix (`n_alt(h_f)`) |
| `nf_main` | int | work objects in the main suffix (`n_main(h_f)`) |
| `nf_rule` | str | `"either"` from v3; `"alt"` or `"either"` in older records (convention 11); absent in records from before the option |
| `regime` | str | `"subjective"` or `"objective"` |
| `w_alt`, `w_main` | str | the daemon's suffix weights (decimal strings) |
| `tie` | bool | `w_alt == w_main` |
| `tie_draw` | str/null | `"random"`, `"cached"` (the pair was drawn before), `"det"` (only under the PoP det-tie flag, never in SoP cells), or null when there is no tie or the evaluation was skipped |
| `result` | str | `"SWITCH"` or `"KEEP"` |

Each block entry: `h` (int), `id` (hex), `diff` (decimal string), `seen` (ms
or null), `ref` (v2 only: `main_seen` for that height in ms, or null, see
convention 5), `n_sh` (int; 0 when the set does not conform), and `shares`, a list
in slot order of `{"id": hex, "seen": ms or null}`. `shares` is present when
`n_sh > 0`. A share's `seen` is its first gossip receipt, or null if it never
arrived by gossip.

The daemon skips the per-share list for main-suffix blocks at heights
`<= top - 10*w`, which never occur in practice (see convention 2).

The oracle times a v2 block entry against its `ref`, on both branches. A
v1 entry has no `ref`. The oracle then times an alt block against the main
block logged at its height, and a main block against itself: the earlier
text's reference.

## Hand-worked cases (expected oracle results)

`diff = 1216` everywhere, so `unit = 76`. `h0 = 994`, `hf = 1000`, `k*w = 48`,
`d = 5000 ms`. Times are in ms. Cases 1–9 were written for the earlier
text (rule `alt`, v1 reference); where the revised rules change the
answer, the case says so.

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
   `reinsert: true` it is skipped (KEEP). *Under rule `either`:*
   `nf_main = 7 + 56 = 63 >= 48`, so objective, `w_alt = 912`,
   `w_main = 76*63 = 4788`, KEEP. The pair no longer flips.
3. **Late alt block.** Subjective. The alt block is seen 6000 after
   `main_seen` at its height, so `l_b = 0` and it weighs 0, shares included.
4. **Share timing edge.** A share seen exactly `d` before `main_seen` does not
   count (`<= d`). One seen `d + 1` before it does.
5. **Alt ahead.** An alt block at a height above `top` takes
   `main_seen = its own seen` (v2: `ref: null`), so `l_b = 1`. Its shares count only if seen
   more than `d` before the block itself.
6. **Late joiner.** With `h0 >= hf` the regime is objective, even with a
   small `nf`.
7. **Tie.** Equal weights: `tie: true`, and the daemon draws.
8. **Non-conforming set.** `n_sh = 0`: the block is its header alone in
   `nf` and in weight.
9. **Old block.** A suffix block at `h <= top - 160` weighs its `diff`.
10. **Fixed reference (v2; `scripts/sop_lateness_probe.py`).** Two honest
    blocks at 1000, both suffixes far under `k*w`. X, seen 0, joined the
    main chain first, so `ref = 0` on both entries. X has 3 shares seen
    -4000, -3000 and -2000. Y, seen 4000, has 2 shares seen -10000 and
    -9000.
    - Node on X: Y is on time (4000 <= d) and both its shares count, so
      `w_alt = 228`. X's shares are not early, so `w_main = 76`. SWITCH.
    - Node on Y: X is on time, with no shares counted, so `w_alt = 76`, and
      `w_main = 228`. KEEP.
    - Under the v1 reference, on the second side Y is main and is timed
      against itself. X's shares are then 6–8 s before Y and count, so X
      weighs 304 against Y's 228. Both sides say SWITCH, under either
      `n_f` rule.
