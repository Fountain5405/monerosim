# Cuprate Integration

How monerosim runs [cuprate](https://github.com/Cuprate/cuprate) (`cuprated`, the Rust Monero
node) alongside `monerod` in the same simulated network.

**Status:** working and validated at 300-node scale, but gated behind an explicit opt-in.
Mining is the one remaining capability gap.

Experiment write-ups: [scale experiment](20260724_cuprate_scale_experiment.md),
[connection matrix](20260725_cuprate_connection_matrix.md),
[wallet RPC](20260724_cuprate_wallet_rpc.md),
[upstream merge](20260802_cuprate_upstream_merge.md).

---

## 1. Quick start

Install `cuprated` (opt-in — it is a large Rust build and most runs don't need it):

```bash
./setup.sh --cuprate
# reuse an existing checkout instead of cloning a second copy:
CUPRATE_DIR=/path/to/cuprate ./setup.sh --cuprate
```

Then add **three lines** to an otherwise ordinary config:

```yaml
general:
  node_implementations:
    cuprated: 0.5           # fraction of ELIGIBLE nodes — see §2
  experimental_cuprate_boot: true
```

Nothing under `agents:` changes. Run it as usual:

```bash
./run_sim.sh --config test_configs/your_config.yaml
```

Keep it current with `./update.sh --cuprate --rebuild` (`--all` includes it too).

---

## 2. Which nodes become cuprate

`node_implementations.cuprated` is a **fraction of the eligible pool, not of all nodes.**
Getting this wrong is the most common surprise.

Eligibility (`src/agent/user_agents.rs:120-137`) — every agent that runs a daemon, **except**:

| Excluded | Why |
|---|---|
| miners (`cfg.is_miner()`) | mine via `generateblocks`, which is a stub in cuprate |
| seed nodes (`is_seed_node`) | the bootstrap backbone stays monerod |
| daemon-phase nodes (`has_daemon_phases()`) | upgrade-phase scenarios are monerod-only |

Everything else qualifies — **including wallet-bearing `user-*` agents**, since cuprate can back
a real `monero-wallet-rpc` (sync and send, both proven). Daemon-only `relay-*` agents and
daemon+wallet `user-*` agents are treated identically here.

Worked example, from `test_configs/cuprate_exp_cuprate_300_8h.yaml`:

| | count | eligible |
|---|---|---|
| `relay-001..245` (daemon) | 245 | yes |
| `user-001..050` (daemon + wallet) | 50 | yes |
| `miner-001..005` (daemon + wallet) | 5 | no — mining |
| seed nodes | — | no — backbone |

295 eligible × `0.61` = **180 cuprate nodes**, which is 59% of the 306 daemons. If you want
"half the network is cuprate", solve against the eligible pool, not the total.

### Assignment is seeded, and aggregate-only

Nodes are sorted by `seeded_hash(seed, "nodeimpl:<agent-id>")` and the first *fraction* taken
(`user_agents.rs:138`). Deterministic and reproducible for a given seed.

**There is no per-agent override.** You cannot say "make `relay-007` cuprate". Two consequences:

- Changing *eligibility* reshuffles *every* assignment. Commit `b0d6a064` made wallet nodes
  eligible, which grew the pool from 245 to 295 and moved every node — same config, same seed,
  different assignment.
- Pinning a wallet to a daemon by IP in a config is fragile: the implementation behind that IP
  can change. `test_configs/cuprate_wallet_rpc.yaml` has this problem today.

---

## 3. What gets rendered

`CupratedImpl::render` (`src/agent/node_impl.rs`) writes a `Cuprated.toml` per node and launches:

```
cuprated --config-file <config_dir>/Cuprated.toml --regtest
```

`--config-file` points at the **stable** config dir (survives cleanup); the config's `fs.*`
entries point at the runtime data dir.

Notable choices in the generated TOML:

| Setting | Why |
|---|---|
| `network = "Mainnet"` **plus** `--regtest` | The `network` TOML field only accepts Mainnet/Testnet/Stagenet. FakeChain is reachable **only** via the `--regtest` CLI flag |
| `fast_sync = false` | Irrelevant on a private chain |
| `[tokio] [rayon] [storage]` threads pinned | **Load-bearing.** Under Shadow, `/proc` reflects the *host* (e.g. 256 cores / 1 TB), so cuprate's auto-sizing would allocate a host-sized pool *per simulated node*. Uses `general.process_threads` (default 1), or 2 if it is set to `0` |
| `[tracing.stdout] level = "info"` | Keeps stdout lean |
| `[tracing.file] level = "debug"` | **Required for analysis.** cuprate logs block events at INFO but tx-relay, P2P connection and handshake events only at DEBUG |
| `[p2p.clear_net] seed_nodes = [...]` | Filled from the spec's `peer_addrs`. This is what joins the node to the sim topology — FakeChain ships no built-in seeds |
| `[rpc.unrestricted] enable = true` | Bound to the agent IP. This is why wallets can talk to cuprate nodes with no extra wiring |
| `[rpc.restricted] enable = false` | Not needed in-sim |

### Degree matching with `out-peers`

The two implementations have very different connection defaults — monerod targets **12**
outbound, cuprate **32 plus up to 8 "extra under load"** (so up to 40). At 300 nodes that gave
cuprate ~2.4× more concurrent peers, a confound for any propagation comparison.

Setting `out-peers` drives **both** implementations from one knob:

```yaml
general:
  daemon_defaults:
    out-peers: 12
```

For cuprate this emits `outbound_connections` **and** pins `extra_outbound_connections = 0`,
because monerod has no load-triggered overshoot to match. Left unset, each keeps its own default.

---

## 4. Capabilities and limits

`CupratedImpl::capabilities()`:

| | value | meaning |
|---|---|---|
| `can_mine` | **false** | `GenerateBlocks` is a stub upstream — miners stay monerod |
| `can_wallet` | true | runtime-proven: a real `monero-wallet-rpc` synced *and* sent through cuprated's RPC, co-located and remote |
| `supports_regtest` | true | FakeChain, verified equivalent to monerod `--regtest` |
| `peer_pinning` | false | `seed_nodes` gives bootstrap seeds, not persistent peer pins |

**`experimental_cuprate_boot: true` is still required.** Preflight refuses to place cuprate nodes
without it. Given mining is the only real gap, this is now caution rather than a blocker.

---

## 5. Version pinning

`cuprate.pin` at the repo root holds a **commit** of canonical `Cuprate/cuprate`.

A commit rather than a tag because `p2p.clear_net.seed_nodes` landed in `e3a869d`
(PR [#663](https://github.com/Cuprate/cuprate/pull/663)) *after* the `cuprated-0.1.0-preview`
tag was cut. Any older build fails hard: cuprate's config uses serde `deny_unknown_fields`, so
the `seed_nodes` key monerosim emits is rejected outright at daemon start — 300 hosts at a time,
with an opaque parse error.

`run_sim.sh` enforces the pin, but **conditionally**: unlike `monero.pin` and
`shadowformonero.pin`, the check only fires when the config actually names `cuprated:`, so a
stale or absent `cuprated` never blocks a monerod-only run. Override with
`MONEROSIM_SKIP_CUPRATE_CHECK=1`.

### Reverting to the fork

Upstream now carries everything we need, so the fork exists only as an escape hatch:

```bash
git -C <cuprate> checkout feat/config-seed-nodes-0.1.0   # Fountain5405/cuprateformonerosim
cargo build --release -p cuprated
cp target/release/cuprated ~/.monerosim/bin/cuprated
# then set cuprate.pin to that branch's HEAD, or the preflight check will reject it
```

---

## 6. Logs and analysis

**Cuprate nodes do not write `bitmonero.log`.** Their tracing file sink writes a *date-named*
file under the data dir:

```
<data_dir>/<network>/logs/2000-01-01      e.g. monero-relay-001/fakechain/logs/2000-01-01
```

`run_sim.sh` collects both into the archive as `daemon_logs/<host>/`, so a completed run has:

```
daemon_logs/monero-miner-001/bitmonero.log     # monerod
daemon_logs/monero-relay-001/2000-01-01        # cuprate
```

Analysis tooling keys on exactly that (`analysis/prop_delta.py:59-67`): a `bitmonero.log` means
monerod, otherwise the first regular file in the directory is treated as a cuprate log. Both
`prop_delta.py` (propagation latency/reach, splits results per implementation) and
`conn_matrix.py` (peer graph, cross-implementation mixing) handle mixed runs.

`conn_matrix.py` takes `--window=<ERE>` for a sim-time slice; `prop_delta.py` has **no**
windowing flag — dump events with `--csv` and filter those if you need a time window.

### Known gap: the monitor is blind to cuprate

`agents/simulation_monitor/agent.py:233` hardcodes `bitmonero.log`, so live progress and
`summary.txt` **count monerod nodes only**. On a 180-cuprate run the monitor reports
"126/306 online" while all 306 daemons are healthy. Fixing it needs a cuprate log parser, not
just a wider filename glob — the monitor also parses monerod's log *format* for height and
connection counts.

---

## 7. Known gaps

- **Mining.** `GenerateBlocks` is a stub upstream; miners must stay monerod.
- **`simulation_monitor`** undercounts on mixed runs (above).
- **No per-agent implementation override** (§2).
- **Wallet coverage is partial** — sync and send are proven; rescan-from-height, multisig and
  cold signing are not exercised.
- **`setup.sh --cuprate` is opt-in**, so a fresh clone has no `cuprated` until asked.
