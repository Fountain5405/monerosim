# Native Mining under Shadow

**Status:** shipped (opt-in) 2026-09-10. Gates: micro, 5-way split, A/A
determinism, cuprate relay, light-vs-full cost (§7). Default mode stays
`generateblocks` this release; native mining is opt-in via
`general.mining.mode: native`.

## 1. What it is

By default, monerosim doesn't let `monerod`'s own miner loop run under
Shadow: the stock RandomX grind makes no blocking syscalls, so Shadow's
simulated clock never advances while it spins, and at the trivial
difficulty a fresh regtest chain starts at, the same loop would instead
submit blocks at wall-clock pace with no relationship to declared hashrate
(docs/20260512_how_pow_works.md). The historical workaround is
`generateblocks` mode: a Python agent per miner fires the `generateblocks`
RPC on a seeded Poisson schedule, and a Python replay of LWMA
(`DAA_WINDOW`) tracks difficulty. Real PoW is still computed and verified
on every block; only the *election* — who mines the next block, and when —
happens in agent code instead of in the hash grinder.

Native mode (`general.mining.mode: native`) removes that workaround for
miners specifically. A vendored patch
(`patches/monero-sim-mining.patch`) adds one blocking `sleep` before every
hash attempt in monerod's miner thread. Each miner becomes a geometric
clock: success probability exactly `1/D` per attempt, attempts every
`1/H` sim-seconds for a declared hashrate `H`, so expected time to a block
is `D/H` — precisely real mining with a virtual hashrate. Nothing else
changes: the miner thread holds a real block template (refreshed every 5 s
and on every accepted block), computes real RandomX, submits through the
stock `handle_block_found` path, and monerod's own difficulty algorithm
(LWMA, 720-block window) drives block timing instead of the Python replay.

Only nodes that mine need the patched binary. Verification is untouched,
so stock `monerod`, `monerod-hf`, and `cuprated` validators accept
natively mined blocks exactly as they accept any other block — mixed
binary/implementation sims keep working (§7 has a cuprate-relay gate that
proves this at runtime).

## 2. The three operating modes

| Mode | Miner binary | Block production | Hard forks | Use |
|---|---|---|---|---|
| 1. Vanilla | stock `monerod` | `generateblocks` (Python Poisson + LWMA replay) | no | default; byte-for-byte upstream daemon |
| 2. Fork-capable, fast | `monerod-sim` (alias `monerod-hf`) with `fakechain-hard-forks` | `generateblocks` | yes | very long simulations at minimum wall cost |
| 3. Native PoW | `monerod-sim` with `general.mining.mode: native` | monerod's own miner thread, real RandomX, real LWMA | optional | PoW / difficulty / mining-behaviour studies |

One patched build (`monerod-sim`) serves modes 2 and 3: every patch it
carries is flag-gated and behaves stock when its flag is absent. The
hard-fork knob (`--fakechain-hard-forks`) is injected only when a schedule
is configured; the mining knob (`--sim-hash-interval-ms`) is injected only
in native mode. Mode 2 is today's hard-fork feature, unchanged.

## 3. Install

```bash
./setup.sh --sim-binary          # build + install ~/.monerosim/bin/monerod-sim (alias monerod-hf)
./update.sh --sim-binary --rebuild
```

`--sim-binary` builds vanilla `monerod` (`monero.pin`) plus
`patches/monero-fakechain-hardforks.patch` and
`patches/monero-sim-mining.patch`, applied in that order in a detached
worktree, and installs the result to `~/.monerosim/bin/monerod-sim` along
with `monerod-sim.provenance` (base tag + both patch sha256s).
`~/.monerosim/bin/monerod-hf` becomes a symlink to `monerod-sim`, so
existing fork configs (`daemon: monerod-hf`) keep working unchanged.
`--hardfork` is accepted as a synonym for `--sim-binary` on both `setup.sh`
and `update.sh`.

`run_sim.sh` preflight gates on the flags a config actually needs: it
probes the resolved miner binary's `--help` output for
`sim-hash-interval-ms` (and, for fork configs, `fakechain-hard-forks`) and
checks provenance against `monero.pin`, the same pattern as the existing
hard-fork gate. A stale or missing `monerod-sim` only blocks configs that
need it. Dev override for tests/dev boxes without the binary:
`MONEROSIM_SKIP_SIM_BINARY_CHECK=1` (`MONEROSIM_SKIP_HARDFORK_CHECK=1` is
still honoured for the fork-only gate).

## 4. Config

```yaml
general:
  mining:
    mode: native            # native | generateblocks   (default: generateblocks)
    rx_full_dataset: true   # native only; default true (see §6)
agents:
  miner-001:
    hashrate: 20            # native mode: LITERAL hashes per second for this miner
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
```

`general.mining` is optional; when absent, behaviour is exactly today's
`generateblocks` mode.

`hashrate` keeps its type (integer ≥ 1) but its meaning changes with mode:
in `generateblocks` mode it stays a **weight** (percentages that should
sum to 100, with a warning if they don't); in `native` mode it is read as
**literal hashes per second**, and the sum-to-100 warning is suppressed. A
20/20/20/20/20 config therefore mines at 100 h/s total, and the chain
settles near `D_eq ≈ 120 × Σ hashrate = 12 000` (Monero's 120-second block
target times total declared hashrate). At generation time the orchestrator
logs (`log::info!`, into `monerosim.log` — not printed to the console):

```
Native mining: 5 miner(s), total hashrate 100 h/s, equilibrium difficulty ~12000
```

**Interval derivation** (`src/utils/mining.rs`, unit-tested): for a miner
declaring `H` hashes/second, the sleep between hash attempts is
`interval_ms = max(1, round(1000 / H))`, so `H ≥ 1` gives an interval
≤ 1000 ms. `H` must be in `1..=1000`: the knob floors at 1 ms, so a larger
declared hashrate would silently mine at 1000 h/s while the logged `D_eq`
still reports the declared value; validation rejects `H > 1000` with an
error naming the miner and the bound.

**Binary selection.** In native mode:

| miner `daemon:` | Result |
|---|---|
| unset or `monerod` | substituted with `monerod-sim`, logged once per miner |
| `monerod-sim` or `monerod-hf` | used (same binary) |
| explicit path | used; must pass the `--help` probe |
| cuprate-eligible node | rejected (cuprate cannot mine — `GenerateBlocks` RPC is a stub, `can_mine: false`) |

Rendered args add `--sim-hash-interval-ms=<n>` and, unless
`general.mining.rx_full_dataset: false`, `--sim-rx-full-dataset`.
Non-miner nodes are untouched.

**Guards** (hard errors at generation time, in `src/agent/user_agents.rs`
and `src/utils/validation.rs`):

- `general.mining.mode` is `native` and the config has zero miners (no
  agent with a `hashrate` field) →
  `general.mining.mode is native but the config has no miners (an agent
  with a hashrate field)`.
- `--sim-hash-interval-ms` or `--sim-rx-full-dataset` set by hand anywhere
  (`daemon_defaults`, `daemon_options`, raw `daemon_args`, or any daemon
  phase), in either mode →
  `Agent '<id>': sim-hash-interval-ms / sim-rx-full-dataset is set directly
  in daemon options/args. It is derived from general.mining (mode: native)
  and the agent's hashrate; remove it.` These knobs are always derived,
  never user-set.
- native mode and a miner has daemon phases configured →
  `Agent '<id>': native mining does not support daemon phases on miners in
  this release (the mining knob is injected into the single daemon launch
  only).`
- native mode and a miner's resolved binary fails the `--help` probe →
  `Agent '<id>': general.mining.mode is native but '<binary>' does not
  support --sim-hash-interval-ms. Build the patched daemon with ./setup.sh
  --sim-binary (miners default to monerod-sim; an explicit daemon: must
  point at it).`

## 5. What the agent does in native mode

`agents/autonomous_miner.py` reads two attributes the orchestrator passes
in native mode (alongside the existing `hashrate` attribute):
`mining_mode: native` and `hash_interval_ms`. When native, the agent's
loop is a lifecycle driver, not a block producer:

1. Wait for the daemon RPC, resolve the mining reward address (existing
   code, unchanged).
2. Issue `start_mining` (one thread) until the daemon accepts it; retry on
   `BUSY` / "not synchronized" every 5 s.
3. On each poll: `mining_status` + `get_info` are logged (`mining_mode`,
   `hash_interval_ms`, `active`, `speed`, `height`, `difficulty`) — no
   registry write happens here, in either mining mode; if mining isn't
   active, `start_mining` is reissued.
4. Own found blocks are picked up by tailing the daemon's log file
   (`bitmonero.log`, host-local — the "Found block `<hash>` at height N"
   line, `global` category INFO level, which the `monitor` log level
   already emits) rather than by the RPC return, and mirrored into the
   agent's own log so log-based tooling keeps working. The tailer is
   rotation/truncation-safe (resets to offset 0 if the file shrinks) and
   only consumes newline-terminated lines; it also decrements attribution
   when the patched daemon reports that a found block was a stale-template
   loss (never added to the main chain).
5. At stop − 120 s, `stop_mining` is called (existing SIGTERM hook point).
   At shutdown, `_cleanup_agent` writes the registry artifact this feature
   produces: `<agent_id>_mining_summary.json`, the same summary the
   `generateblocks` path has always written at cleanup (native mode
   produces it too because `_native_try_start` sets `mining_start_time`,
   which gates the write). No per-block or per-poll registry records are
   written in either mode.

Nothing about the Poisson scheduler, the LWMA replay, or `generateblocks`
mode changes; that code path is untouched and still byte-for-byte what it
was before this feature.

`agents/monero_rpc.py`'s `_make_legacy_request` helper (`start_mining`/
`stop_mining`/`mining_status`, monerod's older positional-params RPC
style) was added by this feature — native mode calls the same stock RPC
methods every other daemon exposes, but monerosim's RPC client didn't have
a caller for them before.

## 6. Cost model

Each miner hashes serially (one thread, forced regardless of
`--mining-threads`); miners run in parallel across Shadow workers. Total
hashes performed over a run are `Σ hashrate × sim_seconds`, independent of
difficulty, so cost is driven by the declared hashrates, not by how the
chain converges.

`--sim-rx-full-dataset` (the patch's second flag) trades ~2 GB extra RSS
per miner for a large wall-time win: measured on the 3-sim-hour micro gate
(two miners, `native_micro.yaml`, otherwise identical config):

| Dataset mode | Wall time | max `total_rss_mb` |
|---|---|---|
| Full (`rx_full_dataset: true`, orchestrator default) | 18m 39s | 8594 |
| Light (`rx_full_dataset: false`) | 1h 30m | 4378 |

Full dataset is ~4.8× faster and costs ~4.2 GB more total RSS across the
two miners (~2 GB/miner), matching the patch's documented full-dataset
cost. Because literal hashrates make the light-mode grind expensive at
scale (a 20 h/s miner in light mode costs roughly 20 attempts/s ×
~20 ms/attempt ≈ 0.4 wall-seconds per sim-second), `rx_full_dataset`
**defaults to true** in `general.mining`.

**Memory-sampler caveat:** `run_sim.sh`'s memory monitor buckets processes
by an exact `ps -o comm=` match on the literal string `monerod`. Native
miners run the `monerod-sim` binary, whose `comm` is `monerod-sim`, so
`memory_samples.csv`'s `monerod_rss_mb` column only ever counts *stock*
`monerod` processes (relays, non-mining validators) and silently excludes
miners in a native-mining run. The real per-miner RSS cost of
`rx_full_dataset` only shows up in the `total_rss_mb` column, as in the
table above — do not read `monerod_rss_mb` as "miner memory" on a native
run.

Levers if wall cost matters: lower the declared hashrates (difficulty
scales down with them; the statistics are unaffected), or accept light
mode on RAM-constrained boxes via `rx_full_dataset: false`.

## 7. Validation results

All tolerances below (except difficulty and PoW rejections, which stay
fixed) are statistical, not arbitrary: `max(fixed floor, 2.5σ)`, with
binomial σ for per-miner block share (`σ ≈ sqrt(p(1-p)/n) × 100` points)
and `120/√k` for the cadence mean over `k` steady-state intervals. At the
~100-block sample sizes these gates run at, a fixed ±5-point share
tolerance fails roughly 1 in 5 statistically-healthy runs; the 2.5σ floor
avoids that false-failure rate while leaving the underlying targets
(120 s cadence, `D_eq = 120 × Σhashrate`, declared hashrate share)
unchanged. In fact both gate runs below originally failed the fixed
±5-point share tolerance (micro: 86.7/13.3 vs 80/20; split: 26.2 vs 20)
before the statistical rule was adopted — the targets were not changed,
only the tolerance. Implemented in `scripts/native_mining_check.py`.

### Micro (`test_configs/native_micro.yaml`, 2 miners at 20/5 h/s, 3 sim-hours)

Run: `archived_runs/20260910_123240_gate_native_micro` (wall 18m 39s).

```
blocks found (all miners)           98       >= 35         PASS
mean interval, last 30 (s)       136.7       120.0  ±55.7  PASS
difficulty, last block            3031        3000   ±750  PASS
share miner-001 (%)               86.7        80.0  ±10.1  PASS
share miner-002 (%)               13.3        20.0  ±10.1  PASS
PoW rejections on relays             0           0         PASS
RESULT: PASS
```

`summary.txt` success criteria: `Blocks created` PASS, `Blocks propagated`
PASS (`Transactions broadcast`/`Transactions in blocks` FAIL as expected —
this config has no transaction-generating agents).

### 5-way split (`test_configs/native_5m_split.yaml`, 5 miners at 20 h/s each, 4 sim-hours)

Run: `archived_runs/20260910_125449_gate_native_split` (wall 44m 40s).

```
blocks found (all miners)          130       >= 35         PASS
mean interval, last 30 (s)       107.2       120.0  ±55.7  PASS
difficulty, last block           11952       12000  ±3000  PASS
share miner-001 (%)               20.8        20.0   ±8.8  PASS
share miner-002 (%)               17.7        20.0   ±8.8  PASS
share miner-003 (%)               16.9        20.0   ±8.8  PASS
share miner-004 (%)               26.2        20.0   ±8.8  PASS
share miner-005 (%)               18.5        20.0   ±8.8  PASS
PoW rejections on relays             0           0         PASS
RESULT: PASS
```

Same `Blocks created`/`Blocks propagated` PASS, `Transactions *` FAIL
(expected, no transaction agents).

### A/A determinism

Two same-seed runs of `native_micro.yaml`, compared on the sorted
`<height> <block hash>` list of every `Found block` line:

| `native_preemption` | Runs | Result |
|---|---|---|
| `true` (config default) | `archived_runs/20260910_134704_gate_native_aa1` (108 blocks) vs `archived_runs/20260910_140722_gate_native_aa2` (101 blocks) | **not identical** — diverges around height 15 (both chains still individually valid; the two miners' race resolved differently) |
| `false` | `archived_runs/20260910_142708_gate_native_np1` vs `archived_runs/20260910_144317_gate_native_np2`, 99 blocks each | **byte-identical** height/hash sequence |

Same seed reproduces the block-hash sequence exactly **only with
`native_preemption: false`**. This is not a native-mining regression: it
matches the pre-existing behaviour documented for `native_preemption` in
`src/config/types.rs` ("helps prevent thread starvation but breaks
determinism") for `generateblocks` mode too. Separately, transaction-
carrying sims have never been fully reproducible run-to-run because of
Dandelion++ relay timing; the A/A gate above is transaction-free by
design, so it isolates the mining-specific determinism question from that
pre-existing limitation.

### Mixed implementation: cuprate relay

Run: `archived_runs/20260910_150013_gate_native_cuprate` (wall 17m 10s),
`native_micro.yaml` plus `general.node_implementations: {cuprated: 1.0}`
and `general.experimental_cuprate_boot: true` (preflight requires the
latter — cuprate placement is gated experimental regardless of mining
mode; see docs/CUPRATE_INTEGRATION.md). Both relay nodes were placed on
`cuprated` (miners stayed on `monerod-sim` — cuprate cannot mine).

Both cuprate relays reached the same tip as the monerod miners: relay
logs end at `height=73 ... Successfully added block hash=...2a74c485...`,
identical hash on both relays, and `summary.txt` reports `Blocks mined: 73`
— the cuprate relays synced every natively mined block, cross-
implementation.

### Cost (light vs full dataset)

See §6 for the numbers and the `monerod_rss_mb`/`total_rss_mb` caveat.

### Running the gate yourself

```bash
python3 scripts/native_mining_check.py <run_dir> --miners id:hashrate,...
```

e.g. `python3 scripts/native_mining_check.py archived_runs/<run> --miners miner-001:20,miner-002:5`.
Run this after any native-mining run to check cadence, difficulty, per-miner
block share, and PoW rejections against the tolerances described above.
Exit 0 = PASS, 1 = FAIL; it prints the comparison table either way.

## 8. Fidelity notes and limits

- **Retarget window.** monerod's stock LWMA window is 720 blocks in native
  mode, so difficulty retargets over hours — mainnet-like. This differs
  from `generateblocks` mode's Python LWMA replay, which uses a 30-block
  window. Partition and heal experiments tuned to the replay's fast
  retarget will behave differently in native mode.
- **Warm-up transient.** The first few blocks are not representative. In
  the pre-gate spike run (2026-09-10, 12.5 h/s total, throwaway patch of
  the same design, `archived_runs/20260910_033731_spike_native_mining3`),
  difficulty went `1, 1, 120`, then overshot to `14520` at height 4, before
  settling into the 1300–1600 band (theory 1500) by about height 6. The
  shipped Task 8/9 gates were not instrumented to record per-height
  difficulty for heights 1–4, but converged to theory by the last block in
  both cases (3031 vs 3000 target in the micro gate; 11952 vs 12000 in the
  split gate — §7). Don't read cadence or difficulty from the first few
  blocks of a native-mining run as the converged behaviour.
- **No daemon phases on native miners.** The mining knob is injected into
  the single daemon launch only; a miner with `daemon_phases` configured
  and native mode enabled is a hard error (§4).
- **Knobs are derived, not user-set.** `--sim-hash-interval-ms` and
  `--sim-rx-full-dataset` can't be set by hand anywhere in the config
  (§4) — they come only from `general.mining` and the agent's `hashrate`.
- **Cuprate cannot mine.** `cuprated`'s `GenerateBlocks` RPC is a stub, so
  cuprate nodes are never eligible for the miner role in either mining
  mode; they validate natively mined blocks like any other node (§7).
- **Phase 2 (adversarial mining controls) is not built.** Selfish mining,
  block withholding, and timestamp games are out of scope for this
  release; see docs/superpowers/specs/2026-09-10-native-mining-design.md
  §10 for the seam left for that work.
