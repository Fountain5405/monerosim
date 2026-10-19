# Dandelion++ relay log (`--sim-log-txrelay`)

Ground-truth log of how each daemon receives and relays transactions:
Dandelion++ stems, fluffs, epochs and stem peers. It is infrastructure item I1
of the spy-node test plan (`docs/20261018_spy_node_defenses.md` §5.2). Stock
monerod logs only `Received NOTIFY_NEW_TRANSACTIONS (N txes)`, without the
stem/fluff flag, the peer or the hashes, so stem paths and each node's stem
peers can't be rebuilt from `bitmonero.log`.

Measurement only: the patch changes no relay decision.

## Turning it on

The flag is added by `patches/monero-sim-txrelay-log.patch`, built into
`monerod-sim` by `./setup.sh --sim-binary`. Pass it per agent group:

```yaml
  relay-{001..015}:
    daemon: monerod-sim
    daemon_options:
      sim-log-txrelay: txrelay.jsonl
```

A relative path is resolved against the daemon's data dir, like
`--peerlist-dump-file`. `run_sim.sh` moves every `txrelay.jsonl` into
`daemon_logs/<node>/` when it archives the run.

Don't put the flag in `daemon_defaults`: by default the fallback seeds run
stock monerod, which rejects it. Declare the seeds on `monerod-sim` with the
flag instead (`docs/SCENARIO_FORMAT.md`, "Choosing a seed's binary"). They are
well connected and often stem peers: in the smoke run with stock seeds, 113 of
226 stem paths ended at a seed and went unrecorded.
Example: `test_configs/txrelay_log_smoke.scenario.yaml`.

## Format

One JSON object per line. Every line has `t` (microseconds since the Unix epoch;
under Shadow this is simulated time) and `ev`. Transaction hashes are hex,
connections are monerod's connection UUIDs, and `addr` is the peer's `ip:port`
as this node sees it. Relay methods are monerod's `relay_method`: `none`,
`local` (this node's own, from RPC), `forward` (Tor/I2P), `stem`, `fluff`,
`block`.

| `ev` | Written when | Fields |
|---|---|---|
| `epoch` | A Dandelion++ epoch starts (every 10 min + U(0, 30 s)) | `fluff` (true: this epoch fluffs every relayed stem tx), `stems` (list of `{conn, addr}`; up to 2) |
| `stems` | The stem set changes mid-epoch (a stem peer disconnected and a send was retried) | `stems` |
| `rx` | A tx arrives over P2P | `tx`, `conn`, `addr`, `dir` (`in`/`out`: who dialed), `fluff` (the message's flag), `result` (what the pool made of it; `none` = already known) |
| `send` | Anything asks the notifier to send txs | `txs`, `method`, `src` (the connection it came from, or `self`) |
| `stem` | A stem send succeeded | `txs`, `method`, `to` (`{conn, addr}`) |
| `fluff` | The notifier fluffs instead of stemming | `txs`, `method`, `reason` (`epoch`: fluff epoch; `no_stem`: no stem peer would take it) |
| `pool_relay` | The pool's periodic re-relay picks a tx | `tx`, `was` (`stem`/`forward`: the embargo timer fired and the tx is now fluffed; `local`: own tx resent; `fluff`/`block`: rebroadcast) |

Volume: every stem receipt is logged, but a fluffed tx only on its first
receipt (`result` other than `none`). Fluffs arrive again from most peers, so
logging them all would multiply the file by the peer count.

## Checking a run

`analysis/spy/txrelay_check.py <archive_dir>` rebuilds every transaction's
origin and stem path and reports how the paths ended. Smoke run 2026-10-19
(`archived_runs/20261019_195616_txrelay_smoke2`; 34 daemons, all logging, 225 txs, 7 min wall):

| Check | Result |
|---|---|
| Origin found / matches the recorded sender | 225 / 225 |
| Stem hops without a matching `rx` at the next node | 0 |
| Stem paths ending in a fluff epoch / a loop / no stem peer | 171 / 52 / 2 |
| Stem hops, mean (geometric with mean 5 when there are no loops) | 3.83 |
| Fluff epochs (stock: 20%) | 20.8% of 973 |
| Log size | ~120 KB per daemon |

Loops are real: with 34 daemons a stem often returns to a node that already
holds the tx, and monerod's pool then fluffs it. They should fall with network
size. No embargo timer fired (`pool_relay` with `was: stem`): every tx was
fluffed within seconds, well before the ~39 s timers.

## Reading it

- **Origin.** A tx's origin is the node with a `send` whose `method` is
  `local`.
- **Stem path.** Follow `stem` events: each names the next hop's address, and
  the next hop's `rx` with `fluff: false` and the same `tx` confirms it.
- **Where the fluff started.** The node with a `fluff` event for the tx
  (`reason` `epoch` or `no_stem`), or a `pool_relay` with `was: stem` (embargo).
- **Stem peers over time.** Each node's `epoch` and `stems` events. Map `addr`
  to agents with `shared/agent_registry.json`.
