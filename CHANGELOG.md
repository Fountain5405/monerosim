# Changelog

## [Unreleased]

### Added

- **Chain-snapshot difficulty preload for native mining** (`general.mining.chain_snapshot:
  auto | off | <preset name or path>`, default `auto`, native mode only): grafts a
  pre-mined chain — already at the target equilibrium difficulty with a full
  720-block DAA window — onto every node before Shadow starts, skipping the
  ~24h cold-start warm-up a fresh regtest chain otherwise needs.
  `patches/monero-sim-mining.patch` gained a generation-only
  `--sim-timestamp-offset <seconds>` flag (mined block templates timestamped
  `now - offset`, so a snapshot's tip can land safely before a consumer run's
  Shadow epoch); `scripts/chain_snapshot.py` exports a generator run's chain
  into a git-trackable preset (`blocks.jsonl.gz` + `manifest.json`) and
  materializes a machine-local LMDB template cache from one (real PoW
  re-verified via `submit_block`), keyed by
  `sha256(D0, monero_pin, hf_schedule, network_id, height)`;
  `src/utils/chain_snapshot.rs` resolves/preflights/copies at config-generation
  time. `test_configs/preload_chain.scenario.yaml` is the generator recipe
  (machinery only — the real preset + committed blobs are a follow-up).
  See `docs/CHAIN_SNAPSHOT.md`.
- **`analysis/topology_metrics.py`** (Gap G1): stage-2 validation metrics
  for the mainnet-replica scenario, computed on connection-graph snapshots
  sampled from monitor-level daemon logs (reusing `conn_matrix.py`'s
  connection-token regex and host loader) and observer
  `peerlist_dump.jsonl` files. Reports outbound-degree class shares
  (absolute and N-scaled thresholds), connection share of the top 13.2% of
  nodes, hub coverage and hub-neighbour overlap, degree assortativity,
  modularity (networkx, when importable), inbound connections per reachable
  honest node, and spy share of honest inbound/outbound slots and of
  peerlist entries, against the literature targets in
  `docs/20260923_mainnet_topology_literature.md`. Markdown table to stdout
  plus `--json`; `analysis/README.md` documents usage;
  `analysis/test_topology_metrics.py` covers every metric against a
  hand-built graph fixture plus a log-parser smoke test.
- **Mainnet observation tools** (`analysis/mainnet/`): measure the live
  Monero mainnet with the same metrics used on the simulator, for stage-2
  replica validation (`docs/superpowers/specs/2026-09-23-mainnet-replica-design.md`).
  `poll_node.py` polls a monerod's RPC (`get_info`/`get_connections`/
  `/get_peer_list`) into daily, gzip-rolled-over JSONL, state-free and safe
  under `systemd-run --user` for a week. `crawl.py` is a BFS crawler that
  Levin-handshakes real mainnet peers (`agents/levin_lib.py`, extended with
  initiator request/response helpers and peerlist/network-address parsing)
  and records reachability, RTT, peer_id, top height, support-flags
  presence and the peerlist-adjacency graph. `enrich_asn.py` does bulk
  ASN/country lookup via Team Cymru's whois, cached on disk. `summarize.py`
  turns a crawl+poll+ban-list+ASN dataset into `report.md`/`report.json`:
  reachable count, three-way spy-label overlap (ban list / peer-ID mismatch
  / absent support flags), spy and honest /24-ASN-country concentration, our
  node's connection/spy-slot shares over time, poll-derived
  connection-duration distribution, and crawl degree/hub-coverage stats —
  the mainnet counterparts of the replica spec's §6 table. Validated live:
  a bad default `top_version` in the handshake (not the current hard-fork
  version) made every real mainnet node look like a "genesis trick" spy
  decoy (0/200 reachable); fixed by fetching `hard_fork_info` (148/200
  reachable after the fix). Tests in `test_mainnet_tools.py` run with no
  network access.
- **Per-agent `turnover` override** (Gap G2): a per-agent `turnover: true|false`
  key (`AgentConfig::turnover`) overrides `general.turnover`'s default sampling
  for that agent. `true` forces the agent's daemon into the offline/online
  turnover cycle regardless of `fraction` — including nodes that pin
  `hide-my-port: false` (normally exempt as an always-reachable hub) — so a
  "medium" reachability class can be pinned reachable yet still cycle.
  `false` always excludes it, `fraction` notwithstanding. Miners and seed
  nodes stay always-on either way. Unset preserves prior behaviour
  (`src/agent/user_agents.rs`, `compute_turnover_set`).
- **Honest prefix sharing** (gap G5, `network.distribution.prefix_sharing:
  {fraction, per_prefix}`): co-locates a fraction of eligible honest daemons
  (non-miner, non-seed, unpinned) onto shared GML nodes — `per_prefix` per
  node, inside their region — so mainnet's BGP-prefix concentration
  (Kirschner 2026 / S11: 12% of prefixes hold 55% of nodes) is reproducible
  under monerod's `/24` outbound dedup. Runs after the base distribution and
  before per-agent `topology_node` pins, which always win.
  `src/topology/prefix_sharing.rs`; `seeded_hash`/`finalize_hash` factored
  into `src/utils/seeded_hash.rs` (shared with the other seeded selections in
  `src/agent/user_agents.rs`). Absent config = unchanged behavior.
- **`patches/monero-sim-selfish-relay.patch`** (`--sim-relay-alt-blocks`, off by
  default, sim-only): makes a daemon relay a **locally-submitted** block that was
  accepted only as an equal-height alternative, which stock monerod drops silently.
  Blocks received over P2P are never re-relayed through this path, so the change
  cannot cascade. Enables γ>0 selfish-mining experiments; wired per-agent via
  `daemon_options: {sim-relay-alt-blocks: true}` and gated at preflight so a config
  that needs it cannot run against a binary without it. Measured result: it does
  **not** lift γ (`docs/SELFISH_MINING.md` §9).
- **Per-agent topology placement**: `topology_node: <gml node id>` pins an agent to
  a chosen GML vertex (`src/topology/placement.rs`).
- **Eclipse-attack reproduction (Nyx/Moros)**: replication of Shi et al., "Are
  Unreachable Nodes Truly Safe? Fully Eclipsing Monero's P2P Network" (CCS 2026).
  py-Levin fake-peer and trash-injector attackers (`agents/eclipse_fakepeer.py`,
  `agents/eclipse_injector.py`, `agents/levin_lib.py`), the eclipse monitor/probe
  agents, the `test_configs/eclipse_*.scenario.yaml` scenarios (54 to ~2,200 hosts)
  and the analysis harness + derived per-run metrics under `analysis/eclipse/`.
  Eclipse-at-birth measured 12/12 at 126 and 963 nodes; write-up in
  `docs/eclipse_reproduction.md`. Raw run artifacts live outside the repo
  (`~/basement_monerosim/20260917_eclipse_reproduction/`).
- **`patches/monero-sim-peerlist-dump.patch`** (`--peerlist-dump-file`, off by
  default, measurement only): monerod appends a JSONL snapshot of its own
  white+gray peer list every 30 s, off the simulated network, because Shadow's
  simulated TCP stalls the large un-chunked `get_peer_list` RPC response.
  `./setup.sh --sim-binary` (`--hardfork` is a synonym) applies every vendored
  patch into the single `monerod-sim` build, with a per-patch tripwire and
  provenance; the primary `monerod` stays vanilla. The eclipse scenarios run
  only their dumping nodes on `monerod-hf` (the `monerod-sim` alias). Rationale
  in `docs/PEERLIST_DUMP_PATCH.md`.
- `gml_processing/5000_nodes_caida_with_loops.gml`: regenerated 5,000-node CAIDA
  topology (AS 0-4999) for >1,200-host runs.
- **Full-scale fake-peer Nyx result committed**: `analysis/eclipse/results/
  20260916_215526_nyx_onboardfirst/` (metrics + write-up) — 2,220 hosts, an
  *established* unreachable victim taken to **12/12** (first full eclipse at 633 min,
  seeds/miners displaced at 146 min, steady-state mean 11.45/12). Real-node Nyx at
  the same scale plateaus at 7/12; port diversity is what flips graylist
  domination. The run had previously existed only outside the repo.

- **Per-agent topology placement**: the `topology_node: <gml node id>` agent
  attribute pins an agent to a specific GML topology node, overriding index-based
  distribution (`src/topology/placement.rs`). Requires a GML topology; validated
  against the GML node ids; co-location allowed. Enables γ-vs-network-position
  selfish-mining experiments (the placement lever phase 2 lacked). See
  `docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md`.

- **Native mining (opt-in)**: `general.mining.mode: native` makes miners run
  `monerod-sim`, whose miner thread mines with real RandomX throttled by
  `--sim-hash-interval-ms` (patches/monero-sim-mining.patch, plus
  `--sim-rx-full-dataset` by default for the full-speed RandomX dataset);
  monerod's own difficulty algorithm drives block timing and `hashrate` is
  read as literal hashes/second (not a weight, as in `generateblocks` mode).
  Validators need no patch. Default stays `generateblocks`.
  See `docs/NATIVE_MINING.md`.
  Validated at 300 nodes over 10 sim-hours with a 200 h/s miner joining at
  4h: difficulty follows monerod's own window formula within 6% at every
  checkpoint, late-joiner share 65.2% vs 66.7% expected, 0 PoW rejections
  (`docs/NATIVE_MINING.md` §7).
  **Change:** `./setup.sh --hardfork` now builds `monerod-sim` (hard-fork +
  mining patches) and installs `monerod-hf` as a symlink alias; `--sim-binary`
  is the new spelling.
  AI config generator: understands `general.mining.mode: native` (literal
  hashes/second, mirror guards, worked example); request extras via
  `AI_CONFIG_REQUEST_EXTRAS` (e.g. z.ai GLM thinking off); Ollama-only body
  fields sent only to local endpoints.

- Selfish-mining apparatus (phase 1): an offline attacker miner + connected
  bridge + `SelfishMinerAgent` running Eyal-Sirer withholding over stock RPCs
  (no daemon patch); `scripts/selfish_mining_analysis.py` measures attacker
  revenue share vs the gamma=0 theory curve. See docs/SELFISH_MINING.md.

- Selfish-mining apparatus (phase 2): the attacker now floods a release to
  **every** bridge in a comma-separated `bridges` list (`bridge_agent` remains
  a one-element alias), which lifts gamma above the phase-1 single-bridge
  baseline by fan-out/connectivity rather than topology position (monerosim
  has no per-agent position control). `SelfishStrategy.update` gained
  `forward_to`, letting a strategy withhold the honest lead from the offline
  miner so it stays on a non-longest private branch (`honest`/`eyal_sirer`
  keep `forward_to=None`, unchanged); three stubborn variants use it:
  `trail_stubborn` (holds while behind by at most `trail_depth`),
  `equal_fork_stubborn` (never concedes straight out of a tie), and
  `lead_stubborn` (reveals only to the honest tip on the override step,
  keeping the top block hidden). `scripts/selfish_mining_analysis.py` now
  reports realized gamma, num ties, and revenue vs the Eyal-Sirer theory
  curve at that measured gamma, not just at gamma=0. New sweep/stubborn
  configs: `test_configs/selfish_phase2/fanout_{1,3,6}.yaml` and
  `stub_{trail,equalfork,lead}.yaml` (alpha=0.4, 3 miners + 12 relays so
  gamma is measurable). See docs/SELFISH_MINING.md §8.

### Fixed

- **BREAKING: seeded reachable/turnover/node-impl selections were contiguous id
  blocks, not a uniform sample.** `compute_node_impl_set`, `compute_unreachable_set`,
  and `compute_turnover_set` (`src/agent/user_agents.rs`) sorted candidate ids
  by the raw FNV-1a `seeded_hash` value and took a prefix. FNV-1a's high bits
  are dominated by an id's *leading* bytes, so the raw hash sorts ids into
  contiguous name/number blocks; a run with `--reachable 0.15` on
  `topo1k_supernodes` made exactly `relay-633..790` unreachable (not a random
  15%), and `mainnet_replica` put `medium-a` at 42/42 reachable and `medium-b`
  at 0/42. Fixed by running the hash through the existing splitmix64 finaliser
  (factored out of `seeded_unit` into `finalize_hash`) before sorting. Same
  seed still reproduces the same set, but **any prior run that used
  `reachable_fraction`/`reachable_by_role` < 1.0, `turnover`, or
  `node_implementations` will get a different (now correctly uniform)
  selection on re-run** — this is an intentional reshuffle, not a regression.
- **Bare binary invocations no longer default into a shared `/tmp` namespace.**
  With `MONEROSIM_SHARED_DIR` / `MONEROSIM_DAEMON_DATA_DIR` unset, the
  generator used to default `general.shared_dir` / `general.daemon_data_dir`
  to the fixed, unnamespaced `/tmp/monerosim_shared` / `/tmp` — a real hazard
  on a shared box (another user's `/tmp/monerosim_shared` from their own
  simulations sat at that exact path). It now mints one run id per process
  (`<UTC timestamp>_<config-file-stem>_<pid>`) and defaults to
  `/tmp/monerosim-<run id>` / `/tmp/monerosim-<run id>/shared`, the same
  per-run namespace shape `run_sim.sh` already sets up. Precedence unchanged:
  explicit config value > env var > this generated default. Belt-and-braces:
  `fix_permissions_recursive` / `remove_dir_with_permissions` now refuse
  (`PermissionDenied`) to chmod or `rm -rf` any existing directory not owned
  by the current uid, applied to the output dir, shared dir, and the
  `{daemon_data_dir}/monero-*` stale-cleanup loop. See
  `docs/20260721_per_run_tmp_namespacing.md` §6a.
- **`tx_analyzer` no longer defaults into that same fresh, empty per-process
  `/tmp` namespace, and now actually loads a finished run's data with no
  flags at all.** It used `monerosim::shared_dir()` /
  `default_daemon_data_dir()` as CLI defaults to locate a *finished* run's
  data; after the bare-binary fix above those functions mint a namespace no
  process ever wrote to, so the analyzer would silently look in an empty
  directory. It now resolves `--shared-dir` and the daemon log dir via the
  run-dir contract instead (new `src/run_dir.rs`, mirroring
  `scripts/run_dirs.py`): explicit flag > `--run-dir`/`$MONEROSIM_RUN_DIR`
  (else newest `archived_runs/<run_id>`)'s archived copy
  (`transaction_registry/`, `daemon_logs/` — what `run_sim.sh`'s own
  archiving leaves behind) > the live `shadow_output/run_env.sh` breadcrumb
  path *if it still exists* (a finished run has had it `rm -rf`'d) > a clear
  error naming both candidates tried. See
  `docs/20260721_per_run_tmp_namespacing.md` §6a.
- **Success criteria are tri-state and no longer misreport mining-only runs.**
  The monitor marked `transactions_created_broadcast` / `transactions_in_blocks`
  FAIL on any config without a transaction workload — 36 of 111 clean runs in the
  archive, every one of them a selfish-mining, eclipse or topology scenario that
  never had a transaction to send. Criteria may now be `true`, `false` or
  `"n/a"`, the verdict line reports `ALL APPLICABLE CHECKS PASSED`, and
  applicability is derived from whether the run has a wallet-bearing non-miner
  agent (erring toward evaluating, so a real failure can never be masked).
- **`blocks_propagated` was measuring the wrong thing.** It was
  `len(nodes_with_balance) > 0` — whether any wallet held a balance, not whether
  blocks propagated — so a mining run with no wallets failed it despite perfect
  propagation. The old check is renamed **`nodes_funded`**, and a real
  **`actual_blocks_propagated`** (at least two nodes synced above genesis) is
  added alongside. The `blocks_propagated` key is deliberately **not** reused, so
  a consumer reading it finds it absent on new runs instead of silently comparing
  funded-node counts against propagation results; it is still rendered for
  archived pre-2026-09-20 reports. Consumers updated: `run_sim_helpers.py`,
  `append_run_history.py`, `smoke_assertions.py`.
- Pure-script agents (script, no daemon/wallet) now honor their configured
  `start_time` instead of a hardcoded `6+2i` s, so late-joining attackers and
  monitors can be scheduled; unset falls back to the legacy formula. They are
  also spread across distinct GML nodes/subnets rather than all on node 0.
- A per-agent `rpc-bind-ip` in `daemon_options` no longer collides with the
  orchestrator's hardcoded flag (a node can bind `0.0.0.0`).
- AS numbers >= 1200 (GMLs with more than 1,200 nodes) mapped to loopback and
  CGNAT first octets, which Shadow's DNS rejects at init. The fallback now cycles
  the routable RIR octet tables and pins the third octet >= 1, so every AS gets
  its own routable /24 disjoint from the AS 0-1199 subnets. IPs for AS < 1200
  are unchanged (`gml_processing/AS_IP_ALLOCATION_NOTE.md`).
- Agents' shared-file locks (transactions.json, node registry, user/miner info, DNS
  records) no longer take a blocking `flock`. Under Shadow a blocking flock runs
  natively on the simulator's worker thread and deadlocks the whole simulation when
  the lock holder is a descheduled host — observed 2026-09-11 at sim-time 5h56m of a
  300-node native-mining run with `native_preemption: true` (gdb: one shadow-worker in
  `regularfile_flock`, 62 spinning). Locks now poll with `LOCK_NB` and sleep 50 ms
  between attempts (sleep yields simulated time), timing out after 120 s
  (`agents/file_locking.py`).

### Changed

- Transactions ledger is now one append-only `shared/transactions/<agent_id>.jsonl`
  per writer (fields unchanged plus `writer_id`, `seq`), with no file lock; the
  monitor and `tx_analyzer` read the directory and fall back to the old array; the
  archive still contains `transaction_registry/transactions.json` (materialized at
  archive time). Only tools that read `transactions.json` from the **live** shared
  directory during a run are affected.

## [0.3.1] — 2026-09-05

- **Liveness check parity**: the bash resolver (`scripts/run_dir_lib.sh`)
  now treats a malformed start-time token in `.owner_pid` the same way the
  Python resolver does (existence-only fallback) instead of reporting the
  run dead; the user doc and design spec now describe the two-token
  `<pid> <starttime>` owner file and the start-time match that defeats
  pid reuse.
- **Acceptance test at scale**: `scripts/test_parallel_runs.sh [CONFIG] [N]` now
  launches N concurrent runs (and `--check CONFIG RUN_DIR...` re-asserts on
  finished ones), asserts equal block counts across runs and byte-identical
  chain snapshots when native preemption is off. Validated with three
  concurrent 105-agent runs (`test_configs/par100_6h.yaml`) plus a
  `--data-dir` run alongside them, then a batch covering the collision
  aborts, same-second launches, `--no-archive`/`--no-clean`, a
  cross-filesystem `--data-dir`, a custom archive base and the hard-fork,
  cuprate and turnover scenarios; see `docs/20260904_per_run_directories.md`.

## [0.3.0] — 2026-09-05

- **Per-run directories**: any number of `run_sim.sh` instances can now run
  concurrently from one checkout: each run gets its own
  `archived_runs/<run_id>/`, allocated before Shadow starts, instead of
  sharing `<checkout>/shadow.data` and `<checkout>/shadow_output`. Preflight
  reports other live runs on the box and reserves their projected disk
  growth. See `docs/20260904_per_run_directories.md`.
  **Breaking:** `--data-dir` now takes a base directory (the run's scratch
  data lands at `<base>/<run_id>/shadow.data`, then moves home unless
  `--no-archive`); `run_env.sh` moved from `<checkout>/shadow_output/` to
  `<run_dir>/shadow_output/`; analysers now write into
  `<run>/analysis_output/`; `run_sim_helpers.py config-summary` prints a
  sixth field (`parallelism`).

## [0.2.0] — 2026-06-27

_The v0.2.0 tag was re-cut on 2026-08-23 and also contains the July work below,
which had been listed as unreleased._

- **Full-codebase quality review**: `docs/20260711_code_quality_review.md` —
  AI-tell taxonomy, per-subsystem grades, prioritized fix list.
- **P0 fixes**: discarded print-loop side effect pinned all miner IPs to
  node 0's /24; `agent_registry.json` torn-read race between writer and
  readers; fabricated `t*0.9` significance fudge replaced with a real
  Student's t-test; structurally-~100% tx-relay fulfillment metric deleted
  (not derivable from logs) along with its phantom fallback fields;
  upgrade wizard emitting N+5 hosts for "N agents".
- **P1 fixes**: `start_here.sh` passing a rejected `--full-monero` flag;
  `post_run_analysis.sh` launching an analyzer without its required
  `--config`; `update.sh` missing RAM-capped build jobs and un-pinning
  setup.sh's ref pin; live geolocation lookups on simulated IPs replaced
  with a static placeholder; simulation-monitor metrics silently reading
  the wrong keys (always-0 counters, cycles miscounted as txs).
- Golden output-equivalence tests regenerated for `d21f971b`
  (max-connections-per-ip floor) — had been red since June.
- **P2 hygiene cleanup**: dead code removed, fallback chains hardened,
  parser fixes, and root-level doc/script hygiene (orphaned scripts
  deleted, stale session artifacts and config graveyard retired to
  `attic/`, CHANGELOG brought current).

- **`--reachable` knob** models mainnet's NAT-unreachable majority instead
  of the previous all-reachable default.
- **Peer turnover**: relays and users cycle offline/online during a run,
  with a `native_preemption` fix for the LMDB-resize livelock it exposed.
- **Turnover-robust Rucknium parser** — the prior xmrpeers-based parser
  crashed on restarted logs.
- **`max-connections-per-ip` floored at 4** and surfaced as a documented,
  overridable default (the old default-1 caused P2P reconnect loops at
  small/dense scale).
- **Network topology realism study**:
  [docs/20260620_network_topology_study.md](docs/20260620_network_topology_study.md)
  — reachability + turnover reproduce mainnet connection-duration stats.
- **Rucknium review response v2** — verified mechanisms, replication, and
  corrected scope.
- `setup.sh` prompts to reinstall when `shadowformonero` is stale or wrong.
- `run_sim.sh` gains `--no-archive` and `--no-clean` flags.

## [0.1.0] — 2026-05-12

**First public beta of monerosim.** Monerosim runs Monero network
simulations inside [Shadow](https://shadow.github.io/) using real
`monerod` and `monero-wallet-rpc` binaries. You write a YAML config
describing a network — miners, users, relays, topology, runtime —
and monerosim's Rust orchestrator generates the Shadow configuration
needed to execute it. Designed for protocol research, performance
benchmarking, and reproducible experiments at scales from a handful
of agents up to ~1000-node networks on a workstation.

### Highlights of this release

- **Full Monero protocol fidelity.** Real RandomX PoW is computed on
  every block; real ring signatures, real bulletproofs, real P2P
  propagation. The simulator runs `monerod` itself; only the cost of
  finding PoW is artificially lowered (regtest difficulty) so block
  arrivals are agent-rate-controlled rather than CPU-bound. See
  [docs/20260512_how_pow_works.md](docs/20260512_how_pow_works.md).

- **Realistic networks at scale.** CAIDA-based GML topologies with
  per-link bandwidth, latency, and packet loss; geographic IP
  allocation across 6 continents; batched agent spawning for large
  networks. The headline benchmark scenario runs 5 miners + 200
  users + 800 relays for 16 simulated hours.

- **Compact scenario format.** Write `user-{001..200}` and
  `start_time_stagger: auto` once instead of hand-rolling 200 agent
  blocks. See [docs/SCENARIO_FORMAT.md](docs/SCENARIO_FORMAT.md).

- **AI config generator.** Describe a scenario in natural language;
  the generator produces a valid YAML against a local Ollama-served
  Qwen3 model. See [docs/AI_CONFIG_GENERATOR.md](docs/AI_CONFIG_GENERATOR.md).

- **Calibrated safe defaults.** Per-machine RAM / core caps,
  auto-bumped `transaction_interval` based on user count and network
  size, and runtime guardrails warn before configurations that
  would overload the host.

- **End-to-end portability** verified on Ubuntu 24.04, Fedora 43,
  Debian 13, Rocky 10, and openSUSE 16. `setup.sh` auto-detects the
  package manager. See [PORTABILITY.md](PORTABILITY.md).

- **Live block-production telemetry.** `run_sim.sh`'s live monitor
  shows current block height, recent rate in min/block, time since
  the last block, and a single-line ASCII histogram of block-interval
  distribution accumulated across the run plus a sliding-window "last
  N blocks" view. Post-run, `summary.txt` gets the full mean/median/
  stdev/percentile-style breakdown plus a wider bucketed histogram.
  Both come from a new parser that reads the daemon log tail and
  dedupes by block height so reorg replays don't double-count.

- **Documented validity envelope.** The new
  [docs/20260512_how_pow_works.md](docs/20260512_how_pow_works.md)
  walks through how synthetic block production preserves real PoW
  while delegating producer election to the agent timer, and the
  README "Known limitations" now spells out what the simulator is
  validated for (protocol-level network research, with statistical
  evidence) and what it isn't (mining-economics research, reorg
  dynamics, mainnet-scale difficulty granularity).

### Install

```bash
git clone https://github.com/Fountain5405/monerosim.git
cd monerosim
./setup.sh                                # ~30-60 min build
./run_sim.sh --config test_configs/quickstart.yaml
```

`setup.sh` pins [shadowformonero](https://github.com/Fountain5405/shadowformonero)
(the Shadow fork carrying Monero-compatibility patches) to its matching
`v0.1.0` tag, so this monerosim release is reproducible from clone to result.

### Known limitations

This is a beta. Config schema and CLI flags may change on any 0.x.0
minor bump (patch bumps stay config-compatible). See the
[Known limitations](https://github.com/Fountain5405/monerosim#known-limitations)
section in the README for the full list — platform support
(glibc/Linux only; EL9 unsupported), resource appetite (16 GB RAM
minimum for real work), the `peer_mode: Dynamic`-is-tested caveat,
and the mid-cleanup `.unwrap()` density acknowledgement.

### For contributors

See [CONTRIBUTING.md](CONTRIBUTING.md) for the test-tier workflow
(orchestrator goldens / pytest / Shadow smoke), and `git log
v0.0.2..v0.1.0 -- :!CHANGELOG.md` if you want the
commit-by-commit detail of what landed in this release.

## v0.0.2 (2026-04-16)

Changes since v0.0.1 (2025-10-07). The section "Since last shared (Mar 11)"
highlights what changed after the project was shared externally.

### Key fix: transaction starvation in Shadow

Shadow is a discrete-event network simulator where all processes on the same
simulated host share a single real CPU thread, switching only at syscall
boundaries. Each user agent runs two processes on one host: `monerod` (daemon)
and `monero-wallet-rpc` (wallet). When one user broadcasts a transaction, it
propagates to every other daemon for verification — and Monero tx verification
is CPU-heavy (~140ms for CLSAG + Bulletproofs+). While a daemon is verifying,
the wallet on that same host is blocked from running.

This caused a "winner take all" failure: the first user to transact would
flood other daemons with verification work, starving their wallets of CPU time.
The wallets would time out (180s), and only one user would ever successfully
transact.

The fix has two parts:
1. **Stagger**: space out `activity_start_time` values so transaction
   generation is evenly distributed: `stagger = interval / num_users`.
   With 3 users and a 60s interval, users start 20s apart, producing one
   tx every 20s instead of three simultaneous txs.
2. **Calibration**: measure how fast this specific CPU can verify transactions
   (by benchmarking CLSAG and Bulletproofs+ natively), then enforce a minimum
   `transaction_interval` so the network is never asked to verify faster
   than the hardware can handle.

This is a **Shadow simulation artifact**, not a real Monero issue. On real
hardware each node has its own CPU. See `docs/shadow-tx-stagger.md` for the
full explanation.

### Since last shared (Mar 11)

#### Calibration system (new)
- **Native hardware calibration**: `python3 scripts/calibrate.py` runs Monero's
  built-in `performance_tests` binary to benchmark CLSAG ring signature and
  Bulletproofs+ range proof verification on the local machine (~30 seconds).
- Calibration auto-runs on first config generation if no data exists.
  Use `--no-calibrate` on `scenario_parser.py` or `generate_config.py` to skip.
- Results saved to `~/.monerosim/calibration.json` and used to set a floor on
  `transaction_interval` so simulations don't exceed what the hardware can handle.

#### Transaction stagger (rewrite)
- **Replaced complex activity batching** with simple formula:
  `stagger = transaction_interval / num_users`. Removed `activity_batch_size`,
  `activity_batch_interval_s`, `activity_batch_jitter` parameters.
- **Fixed "only one user transacts" bug**: all users now reliably send
  transactions when using staggered `activity_start_time`.
- `activity_start_time: auto` now uses `compute_stagger()` for proper spacing.

#### wallet-rpc stability (Mar 27-28)
- Removed broken wallet-rpc restart logic that caused more harm than good.
- Fixed transfer deadlock by removing `max-concurrency` limit on wallet-rpc.
- Settled on `process_threads: 1` + `native_preemption: true` after testing
  many runahead/threading combinations.

#### run_sim.sh improvements (Mar 26)
- Human-readable `summary.txt` generated in archive directory.
- `--archive-blockchain` flag for percentage-based blockchain archiving.
- Fixed intermittent 0% progress display.
- Archive monitoring data (`final_report.json`) with simulation results.
- Guard archive steps so one failure doesn't skip the rest.

#### Portability and setup (Mar 14-24)
- Duration strings (`4h`, `30m`, `300s`) accepted in all config time fields.
- Auto-activate venv in all shell scripts.
- Move dependency repos into `sibling_repos/` (no more sibling dir assumptions).
- `--shared-ringdb-dir` isolates ring database per simulation.
- Various NameError and path discovery fixes.

#### AI config and scenario parser (Mar-Apr)
- Health check for MoneroWorld LLM server before use.
- Scenario parser bug fixes and Shadow settings documentation in AI prompt.
- Fixed expansion reporting and LLM config updates.

#### Other fixes since Mar 11
- Removed `initial_wait_time` from miner distributor.
- Updated quickstart config: seed 12345, reduced to 6h/8h durations.
- Updated `docs/shadow-tx-stagger.md` for new calibration method.

---

### Earlier changes (v0.0.1 to Mar 11)

#### Simulation runner (Mar 8-10)
- Full simulation runner (`run_sim.sh`) with live progress monitor, archiving,
  and disk space checks.
- Daemon logging switched from stdout to native `bitmonero.log` files.
- Live progress monitor parses Shadow's simulated time correctly.

#### AI config generator (Jan-Mar)
- Scenario YAML compact format with expander (`scenario_parser.py`).
- MoneroWorld test server as default LLM backend.
- Interactive mode with modify/new prompt options.
- Semantic validation and benchmark suite.
- Qwen3:8b model support, think-tag stripping.
- Ollama 8K context requirement documented and enforced.
- Monero facts display while waiting for LLM responses.

#### Config and agents (Jan-Mar)
- Named agents with configurable defaults (daemon_defaults, wallet_defaults).
- `process_threads` convenience setting for monerod/wallet-rpc thread control.
- `native_preemption` configurable.
- Duration strings in config fields.
- Relay node agent support (daemon-only, no wallet).
- Configurable relay node spawn staggering.
- Miner distributor refactored with unified `md_` parameters.
- Wallet recovery and continuous funding for upgrade resilience.

#### Setup and portability (Jan-Mar)
- `--clean` flag for fresh start.
- `--full-monero-compile` flag.
- Auto-install `python3-venv` when missing.
- Monero build dependency checks and auto-install.
- tmux/screen recommendation in setup intro.

#### Determinism (Dec 2025 - Jan 2026)
- Pass `simulation_seed` to Shadow for deterministic RNG.
- Replace `HashMap` with `BTreeMap` for deterministic serialization.
- File locking for shared state files.
- Sort lists before random selection.
- Determinism fingerprint generation and comparison tools.

#### Scaling and performance (Jan)
- 1200-node GML topology for scaling tests.
- Removed unnecessary GML placeholder hosts (major scaling improvement).
- `runahead` support for ~19% speedup.
- Memory monitoring and GML auto-selection.
- Batched bootstrap for large-scale simulations.
- Realistic regional bandwidth (Ookla data) and region-based latencies.

#### Network upgrade simulation (Jan)
- Multi-binary daemon support for upgrade scenarios.
- Wallet phase support and gap validation.
- Upgrade impact analysis for comparing pre/post metrics.
- `--daemon-binary` flag for config generator.

#### Analysis tools (Jan)
- Transaction routing analysis tool (`tx-analyzer`) in Python and Rust.
- Dandelion++ stem path reconstruction.
- Network graph analysis module for P2P topology.
- TX relay v2 protocol analysis for PR #9933 testing.
- Bandwidth analysis with time-windowed upgrade comparison.

#### Code quality (Feb)
- Major refactoring: Rust readability, Python agent cleanup, infrastructure.
- Dead code removal, deduplication, constant extraction.
- Code review fixes across the codebase.
- Consolidated duplicated patterns (deterministic hash, interruptible sleep,
  parse_bool, retry).

## v0.0.1 (2025-10-07)

Initial tagged release. Basic simulation with autonomous miners, regular users,
DNS server, and CAIDA network topology generation.
