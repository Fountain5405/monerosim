# Native mining under Shadow — design

**Date:** 2026-09-10
**Status:** approved design, phase 1 (implementation plan to follow)
**Supersedes:** the `mininghook` socket-protocol branch of monero-shadow (rejected, §9)
**Evidence:** spike run `archived_runs/20260910_033731_spike_native_mining3` (§2)

## 1. Goal

Make `monerod` mine natively inside a monerosim run instead of having a Python agent
call the `generateblocks` RPC on a synthetic Poisson schedule. "Natively" means:

1. **Real mining lifecycle.** `start_mining` / `stop_mining` / `mining_status` behave
   truthfully; the daemon's miner thread holds a block template, refreshes it every
   5 s and on every accepted block, and submits blocks through `handle_block_found`.
2. **Native difficulty.** monerod's own difficulty algorithm (LWMA, 720-block window)
   drives block timing. The Python LWMA replay (`DAA_WINDOW`) is bypassed in this mode.
3. **A seam for adversarial strategies.** Selfish mining, withholding and timestamp
   games are phase 2 (§10). Phase 1 must not preclude them and does not.

Non-goals for phase 1: adversarial controls, cuprate mining, replacing `generateblocks`
as the default (§6.4), upstreaming the patch.

## 2. Why this works: the spike

The historic blocker (docs/20260512_how_pow_works.md) is Shadow's scheduling model:
simulated time advances only when a process makes a blocking syscall. The stock miner
loop is a syscall-free RandomX grind, so sim-time freezes; at trivial difficulty the
same loop submits blocks at wall-clock pace. Both failures come from the loop shape,
not from hashing. RandomX itself already runs under Shadow on every block today
(`generateblocks` on the producer, verification on every receiver).

The fix is to put one blocking `sleep` before every hash attempt. Each miner becomes a
geometric clock: success probability exactly `1/D` per attempt, attempts every `1/H`
sim-seconds, so expected time to a block is `D/H`, which is precisely real mining with
a virtual hashrate `H`. Nothing else changes: PoW is real, verification is stock.

Spike (throwaway patch, v0.18.5.1, 2 patched miners at 10 and 2.5 h/s, 2 stock relays,
6 stock seeds, 3 sim-hours):

| Measure | Result | Expected |
|---|---|---|
| Blocks | 94, linear chain, 0 forks, 0 reorgs | |
| Difficulty | 1, 1, 120, 14520 (h4 transient), then 1300–1600 | 12.5 h/s × 120 s = 1500 |
| Hashrate split | 76 / 19 = 80.9 % / 20.2 % | 80 / 20 |
| Cadence, last 30 blocks | mean 119 s | 120 s |
| Stock relays | accepted all 94, 0 PoW rejections | |
| Sim time | advanced normally, 100 % sync | |
| Wall time | 50 min vs 4 min for the same net without mining | see §7 |

## 3. Architecture

```
YAML  general.mining {mode, rx_full_dataset}        per-miner hashrate = hashes/second
        │                                                   │
        ▼                                                   ▼
orchestrator (Rust) ── derives --sim-hash-interval-ms per miner ──▶ monerod-sim (patched)
        │              probes binary capability (--help)              │ miner thread:
        │              selects monerod-sim for miners                 │ sleep(1/H) → hash →
        ▼                                                             │ check_hash → submit
miner agent (Python) ── start_mining / mining_status / stop_mining ──▶│
                        registry: mode, interval, difficulty, found   ▼
                                                        stock monerod / monerod-hf / cuprated
                                                        validators: unchanged, real PoW check
```

Three units, each independently testable:

- **Patch** (`patches/monero-sim-mining.patch`): the daemon-side throttle. Depends on
  nothing in monerosim.
- **Orchestrator wiring** (`src/`): config schema, interval derivation, binary selection,
  capability probe, preflight guards. Depends on the patch only through the `--help`
  probe string.
- **Miner agent** (`agents/autonomous_miner.py`): native-mode lifecycle loop. Depends on
  stock RPC methods only.

## 4. The patch

`patches/monero-sim-mining.patch`, applied to the pinned vanilla monero
(`monero.pin`, v0.18.5.1) on top of `patches/monero-fakechain-hardforks.patch`.
Touches `src/cryptonote_basic/miner.cpp` and `miner.h` only. ~90 lines.

New daemon options, registered once in `miner::init_options`:

| Option | Type | Default | Effect |
|---|---|---|---|
| `--sim-hash-interval-ms N` | uint64 | 0 | `N > 0` enables sim mining: one `sleep_no_w(N)` before every hash attempt; forces a single mining thread (in `start()` and for `--mining-threads`); skips `rx_set_miner_thread` so the miner hashes in RandomX light mode (no 2 GB dataset). `0` = byte-for-byte stock behaviour. |
| `--sim-rx-full-dataset` | bool | false | With sim mining, call `rx_set_miner_thread` anyway: ~1–2 ms/hash instead of ~20 ms at +2 GB RSS per miner. The daemon default is off (stock-shaped); the **orchestrator default is on** (§6.1), because literal hashrates make light mode too slow (§7). Measured in phase 1 (§11e). |

Behaviour kept stock on purpose: template refresh (5 s / on chain update), the found-block
path (`handle_block_found` → relay), `mining_status.speed` (truthful: counts real
attempts), the starter nonce (`/dev/urandom`, which Shadow serves from a per-host seeded
generator, so runs stay deterministic). A found block on a template invalidated by a
reorg is dropped by stock code; the patch logs it at INFO.

Why interval in ms rather than a hashrate flag: integer, exact, and it is what the spike
validated. Fractional hashrates (a 2 % miner at 10 h/s total = 0.2 h/s = 5000 ms) need no
float parsing. The orchestrator owns the conversion.

No verification bypass anywhere. That is the property that makes only **miner** nodes
need the patched binary; stock `monerod`, `monerod-hf`, and `cuprated` validate the
blocks unchanged, and mixed-implementation sims keep working.

## 5. Binary: `monerod-sim`

One patched build carrying both vendored patches, each flag-gated and stock when unset:

- `setup.sh --sim-binary` (alias: `--hardfork`, kept) and `update.sh` mirror the existing
  `install_hardfork_monerod` flow: detached worktree of `monero.pin`, `git apply --check`
  tripwire for **both** patches in order (hard forks, then sim mining), `make daemon`,
  install to `~/.monerosim/bin/monerod-sim`, provenance file listing both patch sha256s.
- `~/.monerosim/bin/monerod-hf` becomes a symlink to `monerod-sim`. Existing fork configs
  (`daemon: monerod-hf`) keep working unchanged.
- Capability detection stays a `--help` probe, per flag: `fakechain-hard-forks` for fork
  configs, `sim-hash-interval-ms` for native mining. Version strings are identical to
  stock and are never used.
- `run_sim.sh` preflight: when the config enables native mining, probe the resolved miner
  binary for `sim-hash-interval-ms` and check provenance against `monero.pin` (same
  pattern as the current monerod-hf gate, lines ~613–644). Dev override
  `MONEROSIM_SKIP_SIM_BINARY_CHECK=1`.

## 6. Configuration and orchestrator

### 6.1 Schema

```yaml
general:
  mining:
    mode: native            # native | generateblocks   (default: generateblocks)
    rx_full_dataset: true   # native only; default true (2 GB RSS per miner, ~1–2 ms/hash)
agents:
  miner-001:
    hashrate: 20            # native mode: LITERAL hashes per second for this miner
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
```

`general.mining` is optional; absent = today's behaviour exactly.

`hashrate` keeps its type (integer ≥ 1) and its `generateblocks`-mode meaning (weight,
sum-to-100 warning). In native mode it is read literally as hashes per second and the
sum-to-100 warning is suppressed. A 20/20/20/20/20 config therefore mines at 100 h/s
total, and the chain settles near `D_eq ≈ 120 × Σ hashrate = 12 000`. The user chose
literal semantics deliberately, to watch monerod's difficulty algorithm respond to
declared hashrate directly.

### 6.2 Interval derivation (pure function, unit-tested)

```
interval_ms = max(1, round(1000 / hashrate_i))          hashrate_i ≥ 1 → interval ≤ 1000 ms
```

`D_eq ≈ 120 × Σ hashrate` is printed at generation time so the operator sees what the
chain will settle to.

### 6.3 Binary selection for miners in native mode

| miner `daemon:` | Result |
|---|---|
| unset or `monerod` | substituted with `monerod-sim`, logged once per miner |
| `monerod-sim` or `monerod-hf` | used (same binary) |
| explicit path | used; must pass the probe |
| cuprate-eligible node | error (cuprate cannot mine; existing `can_mine` cap) |

Rendered args add `--sim-hash-interval-ms=<n>` and, unless
`general.mining.rx_full_dataset: false`, `--sim-rx-full-dataset`. Non-miner nodes are
untouched.

### 6.4 Preflight guards (hard errors, in `user_agents.rs` next to the hard-fork guards)

- native mode and a miner's resolved binary fails the probe → error naming the binary and
  the `setup.sh --sim-binary` fix.
- `sim-hash-interval-ms` present in `daemon_defaults`, `daemon_options` or raw args while
  native mode is on → duplicate-knob error (monerod aborts on duplicate scalars, as with
  the fork knob).
- native mode with zero miners → error.
- `generateblocks` mode with the knob set anywhere → error (the knob would start nothing,
  because no `start_mining` is issued, but it signals a confused config).

Why opt-in this release: native mode changes wall cost (§7) and the meaning of the
`difficulty` column in every existing analysis. The default flips after the scale gate
(§8f) in a later release.

### 6.5 Agent attributes

The orchestrator passes `mining_mode` and `hash_interval_ms` to the miner agent
alongside the existing `hashrate` attribute.

### 6.6 Why literal hashes per second (decision record)

Considered: weights plus a `total_hashrate` scale knob (bounded cost regardless of how
configs are written). Chosen: literal, because the operator wants declared hashrate to
map one-to-one onto what monerod's difficulty algorithm sees, and full-dataset mode
makes the cost acceptable. The trade-off is that configs written with large weights
now imply large hashrates; the printed `D_eq` and the cost note in the doc make that
visible.

## 7. Cost model (documented for operators)

Each miner hashes serially; miners run in parallel across Shadow workers. So

```
extra wall ≈ max_i(H_i) × sim_seconds × t_hash
t_hash     ≈ 20 ms   light mode (measured, spike)
           ≈ 1–2 ms  full dataset (to measure, §8e), +2 GB RSS per miner
```

Total hashes are `Σ hashrate × sim_seconds`, independent of difficulty. With literal
hashrates a typical 20 h/s miner would cost `20 × 20 ms = 0.4` wall-seconds per
sim-second in light mode (a 16-hour sim ≥ 6.4 wall-hours), which is why the full
dataset is the orchestrator default: at ~1.5 ms/hash the same miner costs ~3 % of
sim-time (~30 min over 16 hours) for +2 GB RSS. Levers: lower the declared hashrates
(difficulty scales with them; the statistics do not change), or accept light mode on
RAM-constrained boxes via `rx_full_dataset: false`.

Fidelity note to document: the stock window grows to 720 blocks, so difficulty retargets
over hours, as on mainnet, not over 30 blocks like the Python replay. Partition and
heal experiments tuned to the replay's fast retarget will behave differently.

## 8. Miner agent (native mode)

```
wait for daemon RPC → resolve mining address (existing code)
loop until start_mining OK:  start_mining(addr, threads=1, do_background=false,
                             ignore_battery=true); on BUSY / "not synchronized" sleep 5 s
every poll_interval:         mining_status + get_info → registry
                             {mining_mode, hash_interval_ms, active, speed, height,
                              difficulty}; if not active → start_mining again
own found blocks:            tail the daemon log for "Found block <hash> at height N"
                             (host-local file, global:INFO is in the monitor log level)
                             → registry block records, same schema the generateblocks
                             path writes today
at stop − 120 s:             stop_mining (existing SIGTERM hook point)
```

Not touched in native mode: the Poisson scheduler, the LWMA replay, `generateblocks`.
The `generateblocks` mode is byte-for-byte today's code path.

## 9. Alternatives rejected

- **Socket mining hook** (monero-shadow `mininghook`, commit 0d6028981): external agent
  returns a nonce over TCP, verification bypassed on every node. Never run end to end,
  written on monero master (2 hunks fail on v0.18.5.1), blocking read ignores template
  changes, registers its flag twice. The bypass forces the patched binary onto every node
  and breaks cuprate and stock validators. Nothing it enables is unavailable in the
  chosen design.
- **In-daemon virtual clock** (exponential sleep, garbage nonce, bypass): same all-node
  bypass problem. Kept as the fallback if hashing cost ever bites; the loop shape is the
  chosen design minus the hash.
- **Cheap hash on FAKECHAIN**, **stock background mining**, **miner-side difficulty
  floor**, **timestamp tricks**: evaluated in the design memo; the floor is actively
  harmful (starves the LWMA of work evidence), the others need validator patches or are
  non-deterministic.

## 10. Phase 2 seam (not built now)

Withholding = gate the relay in `core::handle_block_found`; the private chain is the
miner's own main chain, so templates extend it automatically. Masking is mandatory: the
private height leaks on handshake and 60 s timed-sync data, chain requests, object
requests and fluffy-block height. A `public_tip` clamp on those four surfaces plus a
release RPC is ~120–180 lines. Timestamp games need a template-time offset knob (the
timestamp is under the PoW). Phase 1 changes none of these code paths.

## 11. Validation gates

Ship gates for phase 1 (all must pass):

- a. **Micro** (`test_configs/native_micro.yaml`, the spike config formalised with the
  Python agent): cadence 120 s ± 15 % over the last 30 blocks, difficulty within
  ± 25 % of `120 × Σ hashrate`, block share within ± 5 points of each miner's hashrate
  share, 0 PoW rejections on stock relays, summary.txt success criteria pass.
- b. **Determinism A/A**: two runs, same seed → identical block hash sequence.
- c. **Mixed implementation**: a cuprate relay accepts every natively mined block.
- d. **Existing suites**: `cargo test`, Python tests, generation smoke, hard-fork micro
  config still passes on `monerod-sim` via the `monerod-hf` alias.
- e. **Cost measurement**: light vs full dataset, wall and RSS, recorded in the doc;
  confirms (or overturns) the full-dataset default.

Follow-up gate before flipping the default (not required to ship): f. 1000-node run in
native mode vs the generateblocks baseline, comparing block interval distribution,
propagation reach and orphan rate.

## 12. Deliverables

- `patches/monero-sim-mining.patch`; setup.sh/update.sh/run_sim.sh changes (§5).
- Rust: `general.mining` schema, interval derivation, binary substitution, probe,
  guards, unit tests.
- Python: native-mode loop in `autonomous_miner.py`, unit test with a mocked RPC
  (BUSY → OK, inactive → restart).
- Configs: `test_configs/native_micro.yaml`, `test_configs/native_5m_split.yaml`.
- Docs: `docs/NATIVE_MINING.md`; correct the "Aside: the mininghook branch" section of
  `docs/20260512_how_pow_works.md` (the constraint it describes no longer holds; point to
  the new doc); `docs/HARDFORK_TESTING.md` §3 install (monerod-sim + alias);
  README/QUICKSTART pointer; CHANGELOG entry.
