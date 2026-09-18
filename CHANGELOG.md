# Changelog

## [Unreleased]

### Added

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
