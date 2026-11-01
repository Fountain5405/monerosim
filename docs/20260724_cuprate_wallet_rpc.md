> Status: design record of 2026-07-24, kept as history; it may not match the current code. Current docs: docs/README.md.

# Cuprate wallet-RPC interop: a real `monero-wallet-rpc` syncs and sends through `cuprated`

**Date:** 2026-07-24
**Status:** proven in-simulation (sync + send)
**Archives:** `archived_runs/20260724_212401_cuprate_wallet_rpc` (remote light wallet),
`archived_runs/20260724_224301_cuprate_local_wallet` (co-located wallet)

## Summary

A real `monero-wallet-rpc` (Monero v0.18.5.1) can use a `cuprated` node as its daemon:
it syncs the chain and successfully relays transactions. **No monerosim code changes were
required to make this work** — cuprate already implemented the wallet-facing RPC, and
monerosim already rendered it reachable. The previously documented "cuprate has no wallet"
limitation was a *wiring* gap in how monerosim assigned wallets, not a capability gap in
cuprate.

This retires one of the two experimental gates on cuprate node placement. **Mining remains
the only real gate** (`GenerateBlocks` is a stub), so miners still stay monerod.

## Why we believed otherwise

`NodeCaps.can_wallet` was set to `false` for `CupratedImpl` with the comment "cuprate has no
wallet", and `compute_node_impl_set` excluded every wallet-bearing agent from cuprate
placement on that premise. The phrase conflated two different things:

- cuprate does not ship a *wallet application* (no `cuprate-wallet-rpc`) — **true**, and still true;
- cuprate cannot *serve* a wallet over daemon RPC — **false**.

Only the first is a cuprate limitation. Monero's wallet is a separate process; a node only has
to answer its RPC calls.

## What cuprate actually implements

Checked in `Fountain5405/cuprate` @ `30dd459` (= upstream `main` d57d59d + our `seed_nodes`
patch). Every wallet-critical method has a real handler:

| Method | Location |
|---|---|
| `get_height` | `binaries/cuprated/src/rpc/handlers/other_json.rs:113` |
| `get_info` | `handlers/json_rpc.rs:460` |
| `get_blocks.bin` | `handlers/bin.rs:64` |
| `get_hashes.bin` | `handlers/bin.rs:233` |
| `get_o_indexes.bin` | `handlers/bin.rs:264` |
| `get_outs.bin` | `handlers/bin.rs:275` |
| `get_transactions` | `handlers/other_json.rs:129` |
| `send_raw_transaction` | `handlers/other_json.rs:381` |
| `get_fee_estimate` | `handlers/json_rpc.rs:900` |
| `get_transaction_pool_hashes.bin` | `handlers/bin.rs:283` |

There are 48 `todo!`/`unimplemented!` markers in the handler tree, but they cluster in
**mining and admin** methods — `GenerateBlocks`, `GetBlockTemplate`, `GetConnections`,
`RelayTx`, `SyncInfo`, `Set/GetBans`, `FlushTxpool`. None sit on the wallet path.

The server is genuinely wired up: `binaries/cuprated/src/lib.rs:266` calls
`rpc::init_rpc_servers()`, which spawns an axum listener (`rpc/server.rs:31`).

monerosim's `CupratedImpl.render` (`src/agent/node_impl.rs`) already emitted:

```toml
[rpc.unrestricted]
enable = true
i_know_what_im_doing_allow_public_unrestricted_rpc = true
address = "<node's routable sim IP>"
port = 18081
```

so cuprate nodes were reachable on 18081 all along — including throughout the 300-node scale
experiment. Nothing was ever bound to localhost only.

## Experiment 1 — remote light wallet

`test_configs/cuprate_wallet_rpc.yaml`. 17 agents, 6h sim, **15m41s wall, exit 0, 0 process
failures, ALL CHECKS PASSED**.

Four *light* wallets (real `monero-wallet-rpc`, **no local daemon**) via the existing
`daemon: {address: "ip:18081"}` remote path, differing only in which daemon they point at:

- **treatment** — `cupuser-01` → `181.0.0.10` (cuprated), `cupuser-02` → `105.0.0.10` (cuprated)
- **control** — `monuser-01` → `7.0.0.10` (monerod), `monuser-02` → `31.0.0.10` (monerod)

The control isolates "remote RPC" as a variable, so a treatment-only failure would be
attributable to cuprate rather than to the light-wallet path itself.

| agent | daemon | synced | height | received funds | txs sent |
|---|---|---|---|---|---|
| `cupuser-01` | **cuprated** | yes | 71 | yes | 34 |
| `cupuser-02` | **cuprated** | yes | 72 | yes | 33 |
| `monuser-01` | monerod | yes | 71 | yes | 30 |
| `monuser-02` | monerod | yes | 72 | yes | 33 |

Cuprate-backed wallets performed at least as well as the monerod controls on every axis.
No binary, serialization, or parse errors appeared in any wallet log.

### Server-side confirmation

Rather than rely on absence of client errors, cuprate's own debug log
(`daemon_logs/monero-relay-001/`) shows what it served:

```
getblocks.bin                2898
get_outs.bin                  171
get_output_distribution.bin   171
sendrawtransaction            136
json_rpc                       87
getheight                       3
gethashes.bin                   3
```

**Every response `status=200`; zero non-200.** The `.bin` endpoints wallet2 is pickiest about
worked, and `sendrawtransaction` confirms the *send* path end to end, not merely sync.
(`get_output_distribution.bin` is also served — it was not on our original checklist.)

### Strength of the claim

This proves wallet2 **accepts** cuprate's `.bin` responses for the paths this workload
exercised. It does **not** prove byte-identity with monerod's serialization. Absence of parse
errors is compatibility evidence, not equality. Untested paths (unusual ring configurations,
multisig, cold signing, very deep rescans) remain unproven.

## Experiment 2 — co-located wallet

`test_configs/cuprate_local_wallet.yaml`. Tests the configuration the code change newly
permits: a user agent whose **own local daemon** is cuprated, wallet pointed at localhost.
The additional risk here is not wallet RPC but *agent-side* daemon RPC — user scripts and
`simulation-monitor` may call methods cuprate stubs (`get_connections`, `sync_info`).

Seeded assignment put `user-02` and `user-03` on cuprated, leaving `user-01/04/05/06` on
monerod as controls. 20 agents, 6h sim, **18m10s wall, exit 0, 0 process failures, ALL CHECKS
PASSED**, network height 129.

| agent | local daemon | synced | txs sent |
|---|---|---|---|
| `user-01` | monerod | yes | 32 |
| `user-02` | **cuprated** | yes | 32 |
| `user-03` | **cuprated** | yes | 32 |
| `user-04` | monerod | yes | 35 |
| `user-05` | monerod | yes | 32 |
| `user-06` | monerod | yes | 36 |

`user-02`'s wallet refreshed continuously to the end of the run — final entries show
`Refresh done, blocks received: 1, balance (all accounts): 228.078616034052` at 05:58:52 —
so the wallet tracked the chain to the last block, not merely at startup.

Its co-located cuprate daemon served:

```
getblocks.bin                2937
get_outs.bin                  153
get_output_distribution.bin   153
sendrawtransaction            128
json_rpc                       90
getheight                       3
gethashes.bin                   3
```

again **all `status=200`, zero non-200** — essentially identical to the remote case.

The anticipated risk did not materialise: neither the user scripts nor `simulation-monitor`
called any method cuprate stubs (`get_connections`, `sync_info`, `get_block_template` never
appear). No RPC-method-missing errors (`-32601`, "Method not found", "not available") in any
log. The only errors on cuprate hosts were benign P2P churn
(`LevinBucketError ... ConnectionAborted`, "Peer is already connected"), which the small-network
runs produce regardless of implementation.

**Conclusion: a wallet works identically whether its cuprate daemon is local or remote.**

## Known limitation surfaced by this work: the monitor can't see cuprate nodes

`summary.txt` for this run reports `Nodes online: 15` against 19 daemons, and its
`NODE STATUS` table lists only the monerod users. Root cause:
`agents/simulation_monitor/agent.py:233` hardcodes `bitmonero.log`:

```python
log_file = node_dir / "bitmonero.log"
if not log_file.exists():
    continue
```

cuprate writes to `<data>/<network>/logs/<date-named file>` instead, so cuprate nodes never
leave "pending startup" and are silently dropped from the monitor's counts. `analysis/prop_delta.py:59-67`
already solves this with a `detect_node()` fallback; the monitor was never updated to match.

**Consequences.** `Nodes online` and `Sync: %` in `summary.txt` are computed over monerod
nodes ONLY, and silently understate coverage on any mixed-implementation run. This is a
reporting blind spot, **not** a functional failure — cuprate nodes sync fine, as verified
directly from their own logs and RPC traffic above.

This limitation was already identified and worked around in the 300-node scale experiment
(`docs/20260724_cuprate_scale_experiment.md` §2 and the caveats section), where cuprate sync
was verified from cuprate logs rather than the monitor. **No published claim depends on the
monitor's counts.** The underlying bug remains unfixed — a proper fix needs a cuprate log
parser (the monitor parses monerod's log *format* for height/connections, so merely locating
the file is not enough), which is tracked as a follow-up rather than bundled here.

## Fingerprinting: cuprate RPC endpoints are remotely distinguishable

`monero-wallet-rpc` uses *autodetect* SSL and probes TLS before falling back to plaintext.
monerod's RPC supports SSL; cuprate's axum server is plaintext-only. So against a cuprate
daemon the wallet logs exactly two extra lines, once, at connect:

```
E SSL handshake failed, connection dropped: wrong version number (SSL routines)
E SSL handshake failed on an autodetect connection, reconnecting without SSL
```

then reconnects without SSL and works normally. Both implementations log five
`Generating SSL certificate` lines — that part is symmetric.

Functionally this is harmless. But it is a trivially observable **remote fingerprint**: anyone
who can open a TCP connection to a node's RPC port can tell cuprate from monerod by whether a
TLS handshake completes, without any behavioural or timing analysis. This is a concrete
addition to `docs/20260724_cuprate_scale_experiment.md`'s privacy section, which until now
reasoned from mechanism rather than measurement.

Scope: this distinguishes nodes by their *RPC* port. It says nothing about P2P-level
fingerprinting, and it only matters for nodes exposing RPC publicly.

## Code changes made

1. `NodeCaps.can_wallet` for `CupratedImpl`: `false` → `true`, comment replaced with the
   evidence. (`NodeCaps` is declarative — nothing consumes it for placement — so this is
   documentation that had gone stale into an outright false claim.)
2. `CupratedImpl.preflight()` message no longer claims cuprate "cannot run a wallet"; it now
   names mining as the sole remaining gate.
3. `compute_node_impl_set` (`src/agent/user_agents.rs`) no longer skips wallet-bearing agents.
   Miners and seeds are still excluded.

### Breaking change

Change 3 enlarges the eligible pool, so for any config that sets `node_implementations`,
**the seeded-hash assignment reshuffles** — the same config + seed no longer selects the same
nodes as before. Runs published prior to this commit (notably the 300-node scale experiment,
`docs/20260724_cuprate_scale_experiment.md`) are reproducible only from their archived
`shadow_agents.yaml`, not by re-running their input config against current `main`.

## Follow-ups

- Mining support (`GenerateBlocks`) is now the only gate on full cuprate parity.
- Exercise wallet paths this workload didn't: rescan-from-height, multisig, cold signing.
- The TLS-probe fingerprint is worth folding into the deferred adversary experiments.
