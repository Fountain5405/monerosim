# Are the monerod-sim patches inert without their flags? (2026-11-03)

`monerod-sim` is Monero v0.18.5.1 (`monero.pin`) plus the 15 patches of
`patches/series`. Every patch adds `--sim-*` style daemon options, and the
promise of the one-binary design is that a patch does nothing until its flag
is set: an unflagged `monerod-sim` is stock `monerod`, so a run that uses no
patched feature is not changed by the patches it carries. This record is the
audit of that promise, done before deciding against a per-run patch pick-list
(the alternative the owner raised), and the test that now keeps it.

Scope: the 15 rows of `patches/series` at commit `0c639fda`, with the
id-consistency patch commented out as it is there. Two independent reviews
read every patch in full against the patched source tree under
`~/.monerosim/build/monero-sim`: one the Publish-or-Perish patch (2,415
lines), one the other 14. The questions put to each: every option's default
and whether it reproduces stock; every hunk that runs on the default path
(not inside a branch testing a new option), with its effect class; and where
patches touch the same function.

## Verdict

With no flag set, all 15 patches leave consensus, fork choice, mempool and
relay behaviour, peer selection and scoring, log output and RPC responses as
stock. The binary is not byte-for-byte stock, and what remains on the default
path is listed below; none of it changes what a simulation measures.

The consequence for the pick-list question: a per-run selection of patches
would not change any result, because the code it would leave out already does
nothing. It would cost several binaries per box, a provenance check matching
configs to builds instead of to one series, and rebuilds for every research
agent. The owner chose instead to make inertness a tested property:
`scripts/stock_equivalence.sh` runs quickstart on stock `monerod` and on an
unflagged `monerod-sim` and requires identical chains (below).

## Options and defaults

Every option's default reproduces stock. Where the stock value is a literal,
the default is that literal.

| Patch (owner) | Option | Default | Stock |
|---|---|---|---|
| fakechain-hardforks (core) | `--fakechain-hard-forks` | `""` | empty = stock schedule |
| sim-mining (core) | `--sim-hash-interval-ms` | 0, `not_use_default` | member stays 0 unless given |
| | `--sim-rx-full-dataset` | false | |
| | `--sim-timestamp-offset` | 0 | |
| selfish-relay (core) | `--sim-relay-alt-blocks` | false | |
| | RPC `flush_cache.sim_alt_blocks` | false | response field omitted when false |
| peerlist-dump (core) | `--peerlist-dump-file` | `""` | |
| tail-emission (core) | `--sim-tail-emission-height` | `UINT64_MAX` | `height >= UINT64_MAX` is never true |
| pop (sop) | `--sim-publish-or-perish`, `--sim-share-or-perish` | false | gate everything else |
| | `--sim-pop-k`, `--sim-pop-delay-s`, `--sim-pop-det-tie` | 3, 5, false | read only inside the gate |
| | `--sim-pop-uncles`, `--sim-pop-uncles-header` | false | |
| | `--sim-sop-delay-s`, `--sim-sop-k`, `--sim-sop-w` | 5, 3, 0 (16 when SoP is on) | |
| | `--sim-sop-rejudge-displaced`, `--sim-sop-seen-at-notify` | false | |
| | `--sim-no-drop-score` | false | stock scoring |
| txrelay-log (antiproxy) | `--sim-log-txrelay` | `""` | |
| subnet-dedup (antiproxy) | `--sim-subnet-dedup` | `"24"` | mask equals the stock constant |
| fixed-randomx-seed (antiproxy) | `--sim-fixed-randomx-seed` | false | |
| uniform-whitelist-pick (antiproxy) | `--sim-uniform-whitelist-pick` | false | |
| whitelist-candidates (antiproxy) | `--sim-whitelist-candidates` | 20 | stock literal 20 |
| random-whitelist-candidates (antiproxy) | `--sim-random-whitelist-candidates` | false | |
| peerlist-limits (antiproxy) | `--sim-white-peerlist-limit`, `--sim-gray-peerlist-limit` | 0, 0 | members start at the stock constants |
| stemmable-inbound (antiproxy) | `--sim-stemmable-inbound`, `--sim-stemmable-cidrs` | false, `""` | |
| peerlist-ports-per-host (antiproxy) | `--sim-peerlist-ports-per-host` | 0 | |

## What runs on the default path

Ordered by how much it could matter. Line numbers are lines of the patch
file.

**Behaviour, local miner only.** The pop patch (line 49, `miner.cpp`,
`worker_thread`) adds an unconditional `b.invalidate_hashes()` after the
nonce is set. Stock caches the block id at the "Found block" log line; if
`handle_block_found` does not replace the template (the block was rejected or
went to an alt chain), a later find on the same template reuses the stale id
on its way into `add_new_block`. The patched build computes a fresh id. This
is a fix of a stock corner case, visible only to a node's own
`generateblocks`-style miner, never to consensus or the network. It is the one
hunk in the series that changes daemon behaviour with every flag off. Gating
it is the SoP study's call, since it changes the patch's bytes.

**RPC-visible only.**

- pop, lines 177-186 (`tx_extra.h`): two new tx-extra tags (0x75, 0x76) parse
  where stock would fail to parse. The daemon's consensus and relay paths
  never call `parse_tx_extra`; its users are pop's own code, the wallet and
  RPC. Wire bytes are unchanged, and such tags only exist in blocks from
  flag-enabled miners.
- pop, lines 2051 and 2112-2123: a new P2P command, `NOTIFY_NEW_WORKSHARE`
  (id 2011), is accepted by a default node, logged once at Info and dropped.
  Only a mixed network, flag-enabled miners beside default nodes, sends it.
- pop, lines 2285-2286: two new RPCs, `sim_get_workshares` and
  `sim_submit_workshare`, return an error unless SoP is on.
- selfish-relay, lines 109-151: `flush_cache` gains a request field and a
  response field; the response field is omitted on store when false, so stock
  responses are byte-identical.

**Timing only, O(1), no new locks on hot paths.**

- tail-emission, lines 352-357, 361-375 and 438-452: an extra lockless
  `m_db->height()` read in `check_fee`, in both dynamic fee estimates, and
  in `fill_block_template` once per candidate transaction. Lines 343-348 and
  425-430 wrap the miner-transaction check and construction in a compare.
  This patch's inertness rests on the `UINT64_MAX` sentinel rather than a
  flag branch, and is still provable from the patch text.
- pop, line 1948 and 1412-1414: `sim_sop_on_synchronized` takes the
  blockchain lock before its enabled check, once per sync transition; line
  2098: a call per fluffy-block notification that returns before any lock.
- sim-mining, lines 184-196: one member read per hash attempt in the miner
  loop; the RandomX condition `(!0 || x)` equals stock.
- txrelay-log, lines 13-22, 40-69 and 142-204: atomic loads per relayed or
  received transaction and per stem send, two empty strings per stem send.
- stemmable-inbound, lines 98-145 and 337-348: an atomic load per
  Dandelion++ epoch and a bool test per stem lookup.
- fixed-randomx-seed, lines 29-31: a static-int test per `rx_seedheight`.
- peerlist-dump, lines 277-287: a `std::string::empty()` per idle tick.
- The four white-list patches in `make_new_connection_from_peerlist`
  (subnet-dedup 442-461, uniform-pick 134-136, whitelist-candidates 198-200,
  random-candidates 258-286): bool tests with identical values, one empty
  vector per step.
- peerlist-limits, lines 387-399, and ports-per-host, lines 568-582: a
  constant replaced by a same-valued member; `if (0)`.
- fakechain-hardforks, lines 27-107: an empty schedule built once in
  `core::init`.
- selfish-relay, lines 44-46: `added || (false && ...)`.

**Refactor without behaviour change.** pop, lines 208-212, 238-258,
1543-1596 and 2167: an RAII depth counter in
`switch_to_alternative_blockchain`, a copied extra nonce, `return f()`
rewritten as `r = f(); ...; return r` with three false flags, and an extra
false test in `hit_score`. Lines 1491-1493 and 1513-1515 are comments, and
wrong for this series: no patch touches `hardfork.cpp`, and the vote check is
still enforced.

**Logging.** No unconditional log line in any patch; every added `MGINFO`
sits behind a flag test.

## Fork choice

The one line that decides between chains, in `handle_alternative_block`
(pop, lines 1501-1504):

```cpp
// stock
else if(main_chain_cumulative_difficulty < bei.cumulative_difficulty)
// patched
else if(m_sim_pop_enabled ? sim_pop_should_switch(alt_chain, bei)
                          : main_chain_cumulative_difficulty < bei.cumulative_difficulty)
```

`m_sim_pop_enabled` defaults to false (line 1672) and is set only by
`set_sim_pop` and `set_sim_sop`. With it off the identical strict comparison
runs, so a tie keeps the main chain exactly as stock does. The checkpoint
branch above it is untouched.

## Interactions between patches

- **A flag trap, not a default-path issue:** `--sim-subnet-dedup=legacy`
  returns early (subnet-dedup, lines 442-443) into the legacy connection
  routine, which hard-codes the candidate limit 20 (line 533) and the cubic
  draw (line 592). `--sim-uniform-whitelist-pick`,
  `--sim-whitelist-candidates` and `--sim-random-whitelist-candidates` are
  silently ignored under `legacy`. For the antiproxy study to document or
  fix.
- `core::init` and its options: fakechain-hardforks, sim-mining,
  selfish-relay, tail-emission, fixed-randomx-seed and pop; independent
  assignments.
- `node_server::handle_command_line`: all nine P2P patches.
- `make_new_connection_from_peerlist`: subnet-dedup, uniform-pick,
  whitelist-candidates, random-candidates.
- `peerlist_manager`: peerlist-limits (trim) and ports-per-host (append)
  compose as a per-host trim followed by the global trim.
- `levin_notify.cpp`: stemmable-inbound's enabled branch calls
  txrelay-log's `sim_peer` and `write` (stemmable, lines 122-131), a build
  dependency that the series order satisfies.
- pop's hunks carry selfish-relay's lines as context (lines 1745, 1827 and
  the RPC hunk), so reversing their order fails to apply. The two share no
  function; they couple only with both flags on.

## The test that keeps this true

`scripts/stock_equivalence.sh` runs `test_configs/quickstart.yaml` twice with
its committed seed: once as committed, where every daemon is stock
`monerod`, and once with every `daemon: monerod` rewritten to `monerod-sim`
and nothing else changed. Quickstart uses legacy mining and no patched
feature, so stock can run it. The test passes only when both runs pass
`tests/baselines/quickstart_metrics.json` and `scripts/compare_chains.py`
finds every daemon node's block ids identical over the heights both runs
reached. Each run appends to `tests/baselines/stock_equivalence_history.csv`.
Quickstart is a fair chain-identity test: during the 2026-11 reorganization
two quickstarts from different trees matched at all 180 heights, while longer
scenarios (refactor_gate) part by run-to-run spread
(`20261101_repo_reorganization.md`).

### First result

_Pending: filled in from the first run on this box._

## Follow-ups, by owner

- **SoP study:** gate the miner's `invalidate_hashes()` (pop patch, line 49)
  behind the flag, or record that the stock corner case is wanted fixed.
- **Antiproxy study:** document or fix the `legacy` trap above.
- **Core:** `run_sim.sh`'s capability gate reads only `daemon_defaults` and
  `daemon_options`; a patched flag in raw `daemon_args` or in a daemon phase
  is not checked against the binary.
