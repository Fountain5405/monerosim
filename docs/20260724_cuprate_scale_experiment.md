> Status: design record of 2026-07-24, kept as history; it may not match the current code. Current docs: docs/README.md.

# Cuprate at scale: a monerod vs monerod+cuprate network experiment

**Date:** 2026-07-24 (follow-up findings folded in 2026-07-26)
**Status:** Results — complete. §7 (connection characteristics), §8 (wallet RPC) and §9
(cadence vs fan-out) were added by follow-up work after the original write-up; they revise
conclusions below, so read them before citing §5's mechanism or the "relay-class only"
framing. §9 resolves the mechanism question §7 opened.
**Companions:** design/architecture in `docs/20260723_multi_node_type_architecture.md`;
full detail for the follow-ups in `docs/20260725_cuprate_connection_matrix.md` and
`docs/20260724_cuprate_wallet_rpc.md`.

## TL;DR

A 300-node regtest network that is **half cuprate (149 `cuprated` relays) / half
monerod** behaves like an all-monerod network of the same size — and propagates
transactions **noticeably faster**:

- **Full sync:** all 306 nodes (including all 149 cuprate relays) reached the
  chain tip (height 142). Zero failures, all success checks passed, in both runs.
- **Propagation reach:** every block and every transaction reached **100% of
  nodes** in both runs — cuprate relays strand nothing.
- **Block propagation:** comparable (median ~0.1s network-wide in both).
- **Transaction propagation: ~2× faster with cuprate relays** — monerod nodes
  saw txs propagate in **2.31s** median (half-cuprate) vs **4.95s** (all-monerod),
  measured by the *identical* monerod log event, so the speedup is real, not a
  measurement artifact. Likely due to cuprate's dandelion++ timing.
- **Connection behavior** (Rucknium analysis of the user nodes): consistent — 0%
  of connections exceed 6h in both; duration distributions are the same shape.
- **Connection characteristics (§7):** cuprate nodes hold **~2.4× more concurrent
  peers** (61.5 vs 26.1) — a *default* difference (32 vs 12 outbound), not a behavioural
  one. Cross-implementation mixing is **random once degree-corrected** (no clustering by
  implementation), and monerod's own connectivity is **unchanged** (26.1 vs 25.2 baseline).
- **Wallets (§8):** cuprate **can** back a real `monero-wallet-rpc` — sync *and* send,
  proven separately. Mining is the only remaining gate.

- **Cadence vs fan-out (§9):** the two mechanisms are now **separated** — pinning cuprate's
  outbound to monerod's 12 leaves it still **~1.78× faster** (vs 2.19× unpinned), so relay
  **cadence accounts for ~80%** of the speedup and fan-out ~20%.

**Conclusion: `cuprated` is a viable drop-in relay at 300-node scale, and a
faster transaction relay than monerod in this environment** — and it stays faster even when
given monerod's connection budget.

## Question

Does swapping a large fraction of a Monero simulation's relay nodes from monerod
to cuprate change network behavior — and if so, by how much (the "delta")? This is
the first scale test of the multi-node-type feature; prior work only proved
interop at 15 nodes.

## Experimental design

Two runs, **identical except node implementation**, for a clean A/B:

| | Run A — baseline | Run B — cuprate |
|---|---|---|
| Total daemon nodes | 300 | 300 |
| Miners (monerod, mine + seed) | 5 | 5 |
| Users (monerod + wallet, transact) | 50 | 50 |
| Relays | 245 monerod | **96 monerod + 149 cuprated** |
| `node_implementations` | (none) | `cuprated: 0.61` |
| Topology | `gml_processing/1200_nodes_caida_with_loops.gml` | same |
| `simulation_seed` | 20260723 | 20260723 (same) |
| Sim duration | 8h (coinbase matures ~2h → users transact from 3h) | same |

Cuprate nodes were placed as relay-class only, because at the time cuprate was believed
unable to mine *or* back a wallet, so the 5 miners and 50 users stayed monerod.
**The wallet half of that premise was wrong** — see §8; only mining is a real gate. This
does not affect any result here (the experiment ran as described), but a repeat could
legitimately place cuprate under the 50 user nodes too.
Configs: `test_configs/cuprate_exp_*_300_8h.yaml`.
Both launched via `run_sim.sh` (niced, to share the box politely). Run A completed
overnight; Run B was interrupted once by a power outage and re-run (Shadow has no
checkpoint/resume) — no data was lost since both archives are on persistent disk.

## Making cuprate data first-class ("handle properly")

Cuprate logs are not monerod logs, and for a rigorous cross-impl analysis they
can't be second-class. Three changes (committed `72cd80e0`, `5fe400b5`):

1. **`CupratedImpl` emits `[tracing.file] level="debug"`** — cuprate logs *block*
   events at INFO but *tx-relay, P2P connection, and handshake* events only at
   DEBUG, so a debug **file** sink (in each node's data dir) is required to
   capture propagation data comparable to monerod's `net.p2p.msg` logging. (stdout
   stays lean at INFO.)
2. **`run_sim.sh archive_daemon_logs`** also collects cuprate logs into
   `daemon_logs/<node>/` alongside monerod's `bitmonero.log`. Confirmed end-to-end
   on Run B: *"157 monerod (bitmonero.log) + 149 cuprate log file(s) archived"* —
   all 306 nodes uniform in the archive.
3. **`analysis/prop_delta.py`** normalizes both log formats into one event schema
   (block/tx receive, sim timestamps) and computes propagation latency + reach,
   **split by node implementation**.

## Results

### 1. Network health — equivalent

| Metric | Baseline (all monerod) | Cuprate (149 cuprate) |
|---|---|---|
| Completion | 8h, exit 0, **ALL CHECKS PASS** | 8h, exit 0, **ALL CHECKS PASS** |
| Blocks mined | 142 | 141 (same production; same seed) |
| Block intervals | mean 3.4m / median 2.2m | identical |
| Txs created / in blocks | 2290 / 2052 | 2304 / 2024 |
| Failures / alerts | 0 / 0 | **0 / 0** |

### 2. Full-network sync — including all cuprate nodes

Every node reached height 142. The 149 cuprate relays were verified from their own
logs (each added all 142 blocks, top height 142) — the run summary's "157 online"
is only because the monitor polls monerod RPC and doesn't count cuprate nodes; the
cuprate nodes *are* synced.

### 3. Propagation reach — 100% in both runs

Every block hash (142) and every tx hash (~2100) was observed by **all 306 nodes**
in both runs (median & p90 reach = 306). Inserting 149 cuprate relays does not
strand any block or transaction.

### 4. Block propagation latency — comparable

Latency = each node's receipt time minus the block's network-first-appearance
(seconds, sim-time):

| | median | p90 |
|---|---|---|
| Baseline — monerod | 0.136 | 0.211 |
| Cuprate run — monerod nodes | 0.115 | 0.188 |
| Cuprate run — cuprate nodes | 0.081 | 0.141 |

Blocks propagate network-wide in ~0.1s in both runs; cuprate nodes keep pace (in
fact slightly tighter). **Tail note:** the cuprate run shows a max block latency of
~152s, but this is a **boot-timing artifact, not a propagation failure** — the
outliers are all late-booting nodes (staggered start times) syncing the *earliest*
blocks at boot, each within ~6-8s of coming online. It affects both cuprate and
monerod nodes; the median/p90 exclude it.

### 5. Transaction propagation — ~2× faster with cuprate relays

Latency to receive+pool a transaction (sim-time seconds):

| | median | p90 |
|---|---|---|
| Baseline — monerod (`Including transaction`) | 4.95 | 5.88 |
| **Cuprate run — monerod nodes (same event)** | **2.31** | 3.64 |
| Cuprate run — cuprate nodes (`passing tx to tx-pool`) | 1.73 | 3.16 |

The robust result is the **monerod-vs-monerod** comparison (rows 1 and 2): the
*same* monerod `Including transaction` log event, so no cross-implementation
matching bias. Monerod nodes in the half-cuprate network see transactions ~2×
faster than in the all-monerod network. The cuprate nodes themselves are faster
still. This is most likely cuprate's dandelion++ timing (`fluff_probability=0.12`,
`time_between_hop=175ms`) diffusing transactions more aggressively.

*Matching caveat:* cuprate **batches** its tx broadcasts and logs only a batch
count (no per-tx send event), so a send-vs-send cross-impl comparison isn't
possible; the parser pairs the receive/process events (monerod `Including
transaction` ↔ cuprate `passing tx to tx-pool manager`), which the scouting of
both codebases confirmed are the closest semantic match. The monerod-vs-monerod
number above sidesteps this caveat entirely and is the one to trust.

### 6. Rucknium connection-duration analysis — consistent

`analysis/ruck_analysis.r` samples the 50 monerod **user** nodes (present in both
runs) and ignores cuprate logs by construction (it globs `monero-user-*/bitmonero.log`).

| | Baseline | Cuprate |
|---|---|---|
| Connections > 6h | **0%** | **0%** |
| Conn-duration median | 102 min | 127 min |
| Conn-duration max | 243 min | 245 min |
| Messages with >10 txs | 45.0% | 41.0% |

The distributions are the same shape (0% > 6h, max ~4h in both). The modest median
shift (102 → 127 min) suggests cuprate relays are slightly more stable connection
partners, but the overall connection behavior of the monerod user nodes is
unchanged by the presence of cuprate. (Outputs: `ruck_{baseline,cuprate}_output.txt`
+ `p2p-connection-duration.png` in each archive.)

### 7. Connection characteristics between the two node types

*Added 2026-07-26. Tool: `analysis/conn_matrix.py`. Full detail:
`docs/20260725_cuprate_connection_matrix.md`.*

How do the implementations actually wire up to each other? Measured on **concurrent**
connectivity — distinct peers a node exchanged P2P traffic with inside a 5-minute mid-run
window (sim-time 04:00–04:05, well after bootstrap):

| pair | count | share |
|---|---|---|
| monerod ↔ monerod | 563 | 8.4% |
| **monerod ↔ cuprate** | **3047** | **45.7%** |
| cuprate ↔ cuprate | 3061 | 45.9% |

| node impl | n | peers/node | → monerod | → cuprate |
|---|---|---|---|---|
| monerod | 157 | 26.1 | 7.2 | 19.0 |
| cuprate | 149 | **61.5** | 20.4 | 41.1 |

Baseline arm for comparison: 306 monerod nodes, **25.2** peers/node, all pairs monerod↔monerod.

**Cuprate holds ~2.4× more concurrent peers — and this is a configuration default, not a
behavioural quirk.** Cuprate targets 32 outbound connections
(`cuprate/binaries/cuprated/src/config/p2p.rs:324`, max inbound 128); monerod targets 12
(`P2P_DEFAULT_CONNECTIONS_COUNT`, `monero/src/cryptonote_config.h:139`, inbound effectively
unlimited). Neither arm's config overrides these, so both ran stock defaults. The observed
2.36× degree ratio tracks the 32/12 = 2.67× outbound-target ratio.

**Mixing is random — implementations do not cluster.** cuprate↔cuprate at 45.9% looks
hugely over-represented against the 23.7% you'd expect from node counts alone, which would
suggest cuprate nodes prefer each other. That null is invalid here: when degrees differ
2.4×, high-degree nodes appear in more pairs *by construction*. Against the degree-corrected
(configuration-model) null — group share of degree **stubs**, not of nodes (monerod
157×26.1 = 4098 = 30.9%; cuprate 149×61.5 = 9164 = 69.1%):

| pair | observed | degree-corrected expectation | Δ |
|---|---|---|---|
| monerod ↔ monerod | 8.4% | 9.5% | −1.1pp |
| monerod ↔ cuprate | 45.7% | 42.7% | +3.0pp |
| cuprate ↔ cuprate | 45.9% | 47.7% | −1.8pp |

Agreement is within 1–3pp and the residual leans *toward* cross-implementation pairing —
the opposite of homophily. Mechanically expected: neither implementation can identify a
peer's implementation before connecting, both draw from a shared address book, and cuprate's
bootstrap seeds are the monerod miners.

**Monerod is unaffected by cuprate's presence** (26.1 vs 25.2 peers/node), reinforcing §1–3's
functional equivalence.

**Method warning — cumulative peer counts saturate and must not be used for mixing.** Over
the 8h run *every* cuprate node completes handshakes with all 305 other nodes (`relay-001`:
1201 `Handshake complete.` events across 305 distinct peers), while monerod nodes only ever
touch ~115–206 of them. Cumulative pair counts therefore degenerate to exactly 149×157
(complete bipartite) and C(149,2) — an initial pass reported "+11.7pp cross-impl homophily"
from those numbers before the exact integers gave the artifact away. That cuprate churns
through the entire network while monerod touches ~40% is itself a real difference in peer
turnover, and is reported as such — but any assortativity read off cumulative counts is
saturation, not topology.

**Privacy implication.** A cuprate node observes more of the network per unit time (61.5 vs
26.1 concurrent peers), so a cuprate-based passive observer gets a wider view for the same
node count, and each cuprate node is visible to more peers. This is a *degree* effect
available to any node that raises `out_peers`, not something cuprate-specific — but it means
"n% cuprate" shifts the network's observability profile, not only its speed.

### 8. Cuprate can back a real wallet

*Added 2026-07-26. Full detail: `docs/20260724_cuprate_wallet_rpc.md`.*

The "cuprate cannot run a wallet" premise used to scope this experiment (§ Experimental
design) was **false**, and has been retired. A real `monero-wallet-rpc` syncs *and* sends
through a `cuprated` daemon, proven in two separate runs — as a remote light wallet (no
local daemon) and with the wallet co-located on a cuprate node. **No code changes were
needed**: cuprate already implemented the wallet-facing RPC, and monerosim already rendered
it reachable on each node's routable IP:18081, so every cuprate node in *this* experiment
was already serving wallet-capable RPC.

The phrase conflated two things: cuprate ships no wallet *application* (true, still true),
and cuprate cannot *serve* a wallet over daemon RPC (false — Monero's wallet is a separate
process; a node need only answer its RPC).

Server-side, cuprate answered `getblocks.bin`, `get_outs.bin`, `get_output_distribution.bin`
and `sendrawtransaction` with **HTTP 200 and zero non-200** in both runs. This shows wallet2
*accepts* cuprate's `.bin` responses on the exercised paths; it does not prove byte-identity
with monerod's serialization. **Mining (`GenerateBlocks` is a stub) is now the only real
gate on cuprate placement.**

One side finding relevant to fingerprinting: `monero-wallet-rpc` autodetects SSL and probes
TLS first. monerod's RPC answers; cuprate's plaintext-only axum server does not, so a cuprate
endpoint logs a single SSL-handshake failure and falls back to plaintext. Functionally
harmless, but it is a trivially observable **remote fingerprint** distinguishing the two
implementations by RPC port alone — the first *measured* fingerprinting signal, where the
privacy discussion below reasons from mechanism.

### 9. Separating cadence from fan-out — cadence dominates (~80/20)

*Added 2026-07-26. This resolves the open question raised by §7.*

§5 attributed the tx speedup to relay **cadence**; §7 showed cuprate also has ~2.4× the
**fan-out**, an independent candidate mechanism. To separate them, cuprate's outbound target
was pinned to monerod's 12 via the `out-peers` daemon option (which
[`CupratedImpl`] renders as `outbound_connections = 12` plus
`extra_outbound_connections = 0`, since monerod has no load-triggered overshoot).

Two fresh arms, **identical except that one line** — same seed, same agents, both
180 cuprate / 126 monerod:

**Manipulation check — the pin worked, and it is large:**

| arm | cuprate peers/node | monerod peers/node | cuprate:monerod |
|---|---|---|---|
| cuprate-32 (unpinned) | **60.2** | 28.9 | 2.08× |
| cuprate-12 (pinned) | **26.4** | 22.9 | **1.15×** |

Cuprate's degree fell 60.2 → 26.4 (−56%), to near-parity with monerod.

**Result — most of the speedup survives degree matching:**

| arm | tx latency, monerod-only median | vs baseline |
|---|---|---|
| baseline (306 monerod) | 4.953s | — |
| cuprate-32 (degree 60.2) | 2.260s | **2.19× faster** |
| cuprate-12 (degree 26.4) | 2.786s | **1.78× faster** |

Decomposing the 2.693s total improvement (baseline → unpinned):

- **fan-out** accounts for 2.786 − 2.260 = **0.526s (~20%)**
- **cadence** accounts for 4.953 − 2.786 = **2.167s (~80%)**

**So relay cadence is the dominant mechanism, and §5's original attribution was
substantially right.** Fan-out is a real but secondary contributor: cutting cuprate's
outbound degree by 56% cost only ~23% of its latency advantage. A cuprate network with
monerod's connection budget is still ~1.8× faster at propagating transactions.

Block propagation stayed flat throughout (monerod-only median 0.136s baseline / 0.111s
unpinned / 0.120s pinned) — blocks are fast in every arm, so this is a transaction-relay
effect, as §4 and §5 indicated.

**Caveats specific to this decomposition:**

- **Not a perfectly isolated variable.** Cutting cuprate's *outbound* also cuts monerod's
  *inbound*, because inbound degree is just other nodes dialling you — monerod fell 28.9 →
  22.9 peers as a side effect. The cuprate:monerod degree ratio went 2.08× → 1.15×, not to
  exactly 1.0, so a small fan-out advantage remains in the pinned arm. If anything this makes
  the ~80% cadence share a slight *under*-estimate of cadence's role.
- The 80/20 split assumes the two effects combine additively; it is a first-order
  decomposition, not a fitted model.
- Single seed, single window per arm.
- These arms carry 180 cuprate nodes (not §Experimental-design's 149) because the eligibility
  fix in `b0d6a064` enlarged the pool — see §8. The unpinned arm's 2.19× is consistent with
  the original 149-cuprate arm's ~2.14×, which is a useful cross-check that the reassignment
  did not distort the effect.
- §7's mixing residual grew in the pinned arm (monerod↔cuprate +12.3pp above the
  degree-corrected null, vs +4.0pp unpinned, with cuprate↔cuprate −6.6pp). Worth noting but
  not over-interpreting from one window; the no-clustering conclusion in §7 stands for the
  default configuration.

## Mechanism: why cuprate propagates transactions faster

> **UPDATE 2026-07-26 — RESOLVED, see §9.** This section attributes the speedup to relay
> *cadence*. §7 showed fan-out (cuprate's ~2.4× concurrent peers) as a rival explanation, and
> §9 separated them with a degree-pinned arm: **cadence accounts for ~80% of the improvement,
> fan-out ~20%.** With cuprate's outbound pinned to monerod's 12, transactions still propagate
> **~1.78× faster** (vs 2.19× unpinned). The cadence account below is therefore substantially
> correct, but it is not the whole story.

The tx-propagation speedup (§5) is structural, not incidental — it's a difference
in how the two implementations run dandelion++ (the privacy relay layer). On paper
the configs are near-identical; the difference is **timing granularity**:

| Knob | monerod | cuprate |
|---|---|---|
| Relay driver | **1-second poll loop** (`relay_txpool_transactions()` every 1s) | **event-driven, 175ms** between stem hops |
| Stem → fluff | timer-based embargo, poisson **avg 39s** ceiling | epoch role; hop until a Fluff-role node (~1.46s expected) |
| Fluff probability | 20% | 12% |
| Fluff flush | ~5s poisson | fast diffusion timer |
| Epoch | 10 min | 10 min |
| Regtest change | none (fakechain → mainnet params) | none |

The dominant factor is the **relay driver**. Monerod advances every relay step on a
**1-second poll loop**, so each dandelion hop waits up to ~1s (plus a ~5s poisson
fluff-flush); cuprate is **event-driven with 175ms hops** and immediate diffusion.
Each propagation hop is ~5-6× faster in cuprate, and over the multi-hop path to all
306 nodes that accumulates to the ~2× network-wide spread measured in §5.
(Sources: monero `src/cryptonote_config.h` + `tx_pool.cpp` + `cryptonote_core.cpp`
on-idle relay loop; cuprate `binaries/cuprated/src/txpool/dandelion.rs` +
`p2p/dandelion-tower/`.)

**End-to-end check (measured).** Joining each transaction's creation time
(`transaction_registry/transactions.json`) to its first network appearance confirms
that §5's latency *is* the full origin→network time: the originating node logs a tx
only **~0.14s median** after creation in *both* runs, so §5's spread already captures
the entire stem+fluff propagation. And monerod's **39s embargo does not materially
factor** — it is a rare safety ceiling a well-connected regtest network never hits
(max tx latency ~12s baseline / ~19s cuprate, far below 39s). So the ~2× is the real,
full end-to-end difference, driven by the per-hop relay cadence (monerod's 1s poll vs
cuprate's 175ms), *not* the embargo. (Earlier drafts speculated a large hidden
embargo delta; the measurement falsifies that.)

**Privacy dimension (nuanced — a trade-off, not a simple downgrade).** Dandelion++
obscures a tx's origin two ways: *graph* decorrelation (relay through N private stem
hops before broadcasting, so the broadcast point is N hops from the source) and
*time* decorrelation (delay before broadcast). Cuprate's lower fluff probability
(12% vs 20%) means *more* stem hops (~8 vs ~5) → arguably **stronger** graph
decorrelation; but its faster hops (175ms vs ~1s) make the stem ~3× shorter in time →
**weaker** against a timing-correlation adversary. So cuprate is not simply "less
private" at the network layer — it trades time-obfuscation for graph-obfuscation, and
the net effect is threat-model-dependent. Separately, the distinct relay *timing
signature* is a behavioral fingerprint. Both are treated in the privacy/fingerprinting
follow-up.

## Caveats & limitations

- **Wall-clock is not comparable.** Run A took 3h28m, Run B 2h41m — but this is a
  **shared box** (another user runs their own monero workloads), and the two runs
  ran under different co-tenant load, so wall-time carries co-tenancy noise. It is
  *not* evidence of a cuprate speedup. All the deterministic metrics above (sync,
  height, tx counts, propagation in sim-time) are unaffected by co-tenancy.
- **Monerod-centric monitoring.** The run summary counts only monerod nodes as
  "online"; cuprate sync was verified separately from cuprate logs. *Root cause since
  identified:* `agents/simulation_monitor/agent.py:233` hardcodes `bitmonero.log`, while
  cuprate writes to `<data>/<network>/logs/<date-file>`, so cuprate nodes never leave
  "pending startup". `summary.txt`'s "Nodes online" and "Sync %" therefore count monerod
  only on any mixed run (here: 157 of 306). A reporting blind spot, not a functional
  failure — and **no claim in this document depends on those counts**. Unfixed; a proper
  fix needs a cuprate log-format parser, since the monitor parses monerod's format for
  height and connections.
- ~~**Cadence and fan-out are not separated.**~~ **RESOLVED in §9**: a degree-pinned arm
  apportions the speedup ~80% cadence / ~20% fan-out. The residual caveat is that pinning
  cuprate's outbound also lowers monerod's inbound, so degree parity is approximate
  (1.15× rather than 1.0×) — see §9's caveats.
- **§7 is one window, one seed.** The degree gap is large and mechanically explained by
  config defaults, so it is robust; the ±1–3pp mixing residuals are not resolvable at that
  precision. §7's metric is also activity-based (traffic within the window), so a connection
  open but idle for the full 5 minutes is not counted.
- **Tx-event matching** (see §5): the cross-impl tx pairing is receive-vs-receive
  (best available); the trustworthy figure is the monerod-vs-monerod same-event
  comparison. A packet-level or added-instrumentation measurement could tighten it.
- Single seed / single run per arm. Repeats would quantify run-to-run variance.

## Conclusion

At 300-node scale, a network that is half `cuprated` is **functionally equivalent
to all-monerod** on every health and coverage metric — full sync of all 306 nodes,
identical block production, zero failures, 100% propagation reach — and is
**materially better at transaction propagation** (~2× faster, robustly measured).
Cuprate is a viable drop-in relay, and this experiment is the runtime evidence that
the multi-node-type feature works at scale.

The follow-up work sharpens three things. The speedup is driven **mostly by relay cadence
(~80%), with fan-out contributing ~20%** — established by pinning cuprate's outbound to
monerod's 12, after which it is still ~1.78× faster (§9). Cuprate mixes into the network
**without clustering by implementation** while leaving monerod's own connectivity untouched
(§7), the topology-level counterpart to the functional equivalence above. And cuprate is less
limited than assumed: it can back a real wallet (§8), leaving **mining as the sole remaining
gate**.

## Reproducibility

- Configs: `test_configs/cuprate_exp_{baseline,cuprate}_300_8h.yaml`
- Analysis: `analysis/prop_delta.py` (propagation delta), `analysis/ruck_analysis.r`
  (connection duration), `analysis/conn_matrix.py` (§7 cross-impl connection matrix)
- Archives: `archived_runs/20260723_212123_cuprate_exp_baseline`, `archived_runs/20260724_133050_cuprate_exp_cuprate`
- §8 archives: `archived_runs/20260724_212401_cuprate_wallet_rpc` (remote light wallet),
  `archived_runs/20260724_224301_cuprate_local_wallet` (co-located wallet);
  configs `test_configs/cuprate_{wallet_rpc,local_wallet}.yaml`
- §9 archives: `archived_runs/20260726_150824_cuprate_exp_cuprate32_reassigned` (unpinned
  reference, 2h26m), `archived_runs/20260726_173445_cuprate_exp_cuprate_out12` (pinned,
  2h14m); config `test_configs/cuprate_exp_cuprate_out12_300_8h.yaml` — byte-identical to
  the cuprate arm's config apart from `daemon_defaults.out-peers: 12`
- Commits: `72cd80e0` (debug file-logging + collection + parser + configs), `5fe400b5`
  (cuprate tx-regex fix), `b0d6a064` (§8 wallet support + gate retired), `a2b3b8c2`
  (§7 connection matrix)
- Run: `nice -n10 ./run_sim.sh --config test_configs/cuprate_exp_<arm>_300_8h.yaml --name <arm>`
- Delta: `python3 analysis/prop_delta.py <baseline>/daemon_logs <cuprate>/daemon_logs`
- §7 matrix (concurrent; ~35 min per archive pair over ~14 GB):
  `python3 analysis/conn_matrix.py --window='^2000-01-01[ T]04:0[0-4]:' <baseline> <cuprate>`

## Follow-ups

- ~~**End-to-end tx-delay**~~ **DONE** — measured; see the "End-to-end check" note in the
  Mechanism section. The expected large hidden embargo delta did *not* exist: the
  originating node broadcasts ~0.14s after creation in both arms, and monerod's 39s embargo
  never fires. §5's ~2× is the full end-to-end difference.
- ~~**Privacy / fingerprinting**~~ **DONE (analysis)** — see the privacy dimension in the
  Mechanism section plus §7 (observability/degree) and §8 (TLS-probe RPC fingerprint, the
  first *measured* signal). The in-sim **adversary experiments** (fingerprint classifier,
  first-spy / timing origin-tracing) remain deliberately deferred.
- ~~**Separate cadence from fan-out**~~ **DONE — see §9.** The speedup survived degree
  pinning (~1.78× vs 2.19×), so cadence drives ~80% of it. Remaining refinement: monerod's
  inbound degree also drops when cuprate's outbound is pinned, so a truly degree-matched pair
  would need monerod's `in-peers` capped in step.
- **Sweep the cuprate fraction** (0 / 25 / 50 / 75 / 100%) now that the mechanism is
  understood, to see whether the speedup is linear in cuprate share or has a threshold.
- **Fix monitor blindness to cuprate nodes** so `summary.txt` stops undercounting on mixed
  runs (needs a cuprate log-format parser — see Caveats).
- Quantify run-to-run variance (repeat each arm with different seeds).
- Push the cuprate fraction higher (all-cuprate relays) and to larger node counts.
- Now that §8 retires the wallet gate, place cuprate under **user/wallet** nodes too, not
  just relays — the original design excluded them on a false premise.
- Exercise wallet paths §8's workload didn't: rescan-from-height, multisig, cold signing.
