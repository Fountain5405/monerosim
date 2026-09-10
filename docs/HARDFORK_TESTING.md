# Hard Fork / Network Upgrade Testing

How monerosim simulates a Monero network upgrade: start the network on
consensus version X, fork to X+1 at a chosen height, and leave any subset of
nodes behind to study how the network handles partial adoption.

**Status:** working; all three scenarios validated end-to-end — stall,
chain split, and late-upgrade healing (§8). monerod-only — cuprate nodes
cannot participate in fork scenarios (§7).

---

## 1. Why this needs a patched monerod

Regtest's hard fork schedule is hardcoded: v1 at height 0 and the **latest**
mainnet version at height 1, built once at core init
(`cryptonote_core.cpp`, `regtest_hard_forks`). There is no CLI option,
config setting, or env var that touches it. Two consequences:

- Every FAKECHAIN sim runs the newest consensus rules from height 1. A fork
  can never happen mid-run.
- Two *different stock releases* can't emulate an upgrade either: each
  activates its own top version at height 1, so a version difference between
  binaries is **retroactive to genesis, not prospective from a height**. The
  "upgraded" node would reject the entire existing chain instead of
  accepting history and diverging at H.

The fix is `patches/monero-fakechain-hardforks.patch` (~83 lines, one file):
a `--fakechain-hard-forks` option that replaces the regtest table. Applied
to the same vanilla monero that `monero.pin` pins — the primary `monerod`
stays byte-for-byte stock; the patched build installs as **`monerod-hf`**.

```
--fakechain-hard-forks=1:0,14:1,15:500
```

Format rules (enforced by the parser with real error messages, because
`Blockchain::init` silently ignores `add_fork` failures):

- comma-separated `version:height` pairs
- **strictly increasing in both** version and height
- first pair must be `1:0` (genesis is a v1 block)
- requires `--regtest`
- vote thresholds are not supported — activation is by height, which is
  also how mainnet forks actually activate

## 2. The key idea: "didn't upgrade" is a schedule, not a binary

A node whose schedule stops at v14 rejects every v15 block at the same
check, for the same reason, at the same point in the code as a node running
pre-v15 software (`HardFork::check` → "block has old version"). So **one
binary serves both roles**, and an n%-don't-upgrade scenario is just n% of
nodes with a shorter string:

```yaml
general:
  daemon_defaults:
    fakechain-hard-forks: "1:0,14:1,15:105"   # the upgraded network
agents:
  user-02:
    daemon_options:
      fakechain-hard-forks: "1:0,14:1"        # never learns about v15
```

Limit, stated plainly: this models **consensus** divergence faithfully, not
software divergence — a genuinely old binary also differs in P2P/RPC
details. For consensus-level upgrade dynamics (stalls, splits, bans,
partition, wallet behavior) it is equivalent.

Pick the fork pair deliberately. **14→15 is the substantive one**: BP → BP+,
view tags, min ring 11 → 16 all key on `HF_VERSION_* = 15`, so wallets
genuinely build different transactions on each side. 15→16 is near-ceremony.

## 3. Install

```bash
./setup.sh --sim-binary          # build + install ~/.monerosim/bin/monerod-sim (alias monerod-hf)
./update.sh --sim-binary --rebuild
```

`monerod-hf` is now a symlink to `monerod-sim`, which also carries the
native-mining patch (docs/NATIVE_MINING.md); `daemon: monerod-hf` keeps
working. `--hardfork` is accepted as a synonym for `--sim-binary`.

- Built in a **detached worktree** of the pinned checkout; the patch never
  touches the main monero tree. `git apply --check` is the tripwire: when
  `monero.pin` moves past the patch, setup fails loudly instead of drifting.
- `update.sh` rebuilds `monerod-hf` **automatically** whenever monero itself
  is rebuilt and a `monerod-hf` is installed — a pin bump can't leave a
  stale fork binary behind.
- Provenance (base tag + patch sha256) is written next to the binary.
- `run_sim.sh` gates conditionally (like the cuprate gate): only when the
  config names `monerod-hf` or the knob. It checks the pin **and probes
  `--help` for the flag** — the patched build prints the *same* version
  string as vanilla, so a version check alone proves nothing.
  Dev override: `MONEROSIM_SKIP_HARDFORK_CHECK=1`.

## 4. Writing a fork config

Start from `test_configs/hf_smoke_5m2u.yaml` (validation gate) or
`test_configs/hf_micro_2node.yaml` (smallest possible exercise). The rules:

1. **Every daemon-running agent sets `daemon: monerod-hf`.** The knob in
   `daemon_defaults` reaches every daemon, and stock monerod exits on
   unknown options. Generation-time preflight enforces this by actually
   probing each resolved binary's `--help` (a binary that can't parse the
   knob fails the config with a targeted message).
2. **Declare the six seed hosts.** Auto-injected fallback seeds
   (`monero-seed-001..006`) run hardcoded stock `monerod`; declaring them in
   the config (the orchestrator adopts declared seeds and pins their IPs)
   puts the backbone on `monerod-hf` with the full schedule:
   ```yaml
   monero-seed-001: { daemon: monerod-hf, start_time: 0s }
   # ... through monero-seed-006
   ```
3. **Laggards** get the short schedule via per-agent `daemon_options`
   (per-agent wins over `daemon_defaults` on key collision).
4. **Stall vs split.** Miners' block templates take their version from the
   miner's own schedule. All miners upgraded ⇒ zero old-version blocks after
   H ⇒ laggards freeze at H (the **stall** variant). For a **chain split**,
   put one or more miners on the short schedule — both sides keep producing.
5. **Phase-based upgrades** (a laggard that upgrades mid-run via
   `daemon_N` phases): put the schedule in **per-phase args only**
   (`daemon_0_args: ["--fakechain-hard-forks=1:0,14:1"]`), never in
   `daemon_defaults`/`daemon_options` for that config — the flag would be
   emitted twice and monerod aborts on duplicated options. Preflight rejects
   the combination.
6. **No cuprate.** Custom schedules are monerod-only; preflight hard-fails a
   config that sets the knob alongside `general.node_implementations`
   (cuprate's FakeChain table is compiled in, and its renderer silently
   drops unknown option keys — the failure would otherwise surface only as
   runtime chain rejection).

### Planning the fork height

**Cadence changed at v0.2.0** (commit `ec973683`, issue #8): the miner
pacing bug that made every run measure ~2.8 min/block was removed, and the
effective cadence is now the nominal **2.0 min/block** (validated: 202/201
blocks in 7h on two seeds, mean 2.07m). Rule of thumb:

```
H ≈ (minutes until desired fork time) / 2.0     # runs at/after v0.2.0
H ≈ (minutes until desired fork time) / 2.8     # historical runs before it
```

The validated results below (§8) were produced at the old 2.8 cadence; the
`hf_*` configs' fork heights have been re-tuned for 2.0.

Height convention: monerod reports height = block **count** = top index + 1.
A laggard with fork height H stalls showing height **H** (top block index
H−1) — it accepted blocks 0..H−1 and rejected the first vNEW block at
index H.

## 5. What happens at the fork (mechanics, all code-verified)

- Upgraded miners' blocks carry `major_version = current`, `minor_version
  (vote) = ideal` — so **before** H the laggard happily accepts v14 blocks
  that vote 15, and its `hard_fork_info` shows the real-world
  "update needed" signal building.
- At H, block templates flip to `major_version 15`. The laggard fails them
  in `HardFork::check` ("has old version: 15 ... current: 14"), sets
  verification-failed, drops the connection with a fail score.
- Two partition layers, and at small scale the **handshake wins**: peers
  whose sync data advertises a higher `top_version` are refused outright
  ("peer claims higher version than we think ... we may be forked from the
  network"), which cuts connections faster than fail-score bans (score >10
  → 24h ban) can accumulate. Expect the laggard's connection count to
  collapse while ban counters may stay at zero.
- **Late upgrade heals by design**: restarting a laggard with the full
  schedule (phase upgrade) pops its now-invalid top blocks
  ("Current top block ... disagrees with the ideal version") and resyncs
  the majority chain.
- Cross-partition transactions die at H: v14-era txs (ring 11, BP) violate
  v15 relay rules, so a stalled node's new transactions stay in its own
  pool. Its wallet keeps submitting but nothing confirms — the authentic
  "my node stopped working" experience.

## 6. Observability

| signal | where |
|---|---|
| rejections | laggard `bitmonero.log`: `has old version`, `Block verification failed, dropping connection` |
| handshake refusals | `claims higher version` — **needs `net.cn:DEBUG`**; the gate configs set `log-level: "1,net.cn:DEBUG"` on laggards |
| fork state per node | `hard_fork_info` RPC: `version`, `earliest_height`, `enabled`, `voting` |
| stall / partition | `summary.txt` node table: laggard height frozen at H, connection count collapsed |
| vote signal pre-fork | laggard `hard_fork_info` `voting` > `version` |

Analysis note: `prop_delta.py` reach metrics will (correctly) show the
laggard unreachable post-H — that is the finding, not a broken run.

## 7. Known limits

- **monerod-only.** Cuprate has no custom-schedule support; preflight blocks
  the mix. Mirror-patching cuprate's `fake_chain()` table is the obvious
  follow-up if mixed-implementation fork studies are wanted.
- **Height-based activation only** — no vote-threshold gating (regtest
  passes threshold 0; the default 10080-block voting window dwarfs sim
  chain lengths).
- **Consensus divergence, not software divergence** (§2).
- The `simulation_monitor` "Processes: N monerod" counter pattern-matches
  the name `monerod` and shows 0 for `monerod-hf` runs — cosmetic; per-node
  status (from `bitmonero.log`) is correct.
- The patch is **vendored deliberately** — upstreaming to monero-project is
  possible later (it is `--regtest`-scoped test tooling, the same shape as
  the cuprate `seed_nodes` option accepted upstream as PR #663) but is
  deferred for now; `git apply --check` in setup.sh guards against pin
  drift in the meantime.

## 8. Validation results

### Micro smoke (`hf_micro_2node.yaml`, fork at 10, 45 min sim)

| check | result |
|---|---|
| laggard frozen at fork boundary | height 10 = blocks 0..9, first v15 block rejected |
| upgraded tip | 15, all 7 upgraded nodes in agreement |
| rejections | 7× `has old version: 15 current: 14`, 7 drops |
| partition | laggard conns 6 → **1**; 14 handshake refusals; **0 bans** (handshake-first finding) |
| shadow | exit 0 |

### Validation gate (`hf_smoke_5m2u.yaml`, 5 miners + 2 users, 6h, fork at 105)

| check | result |
|---|---|
| completion | shadow exit 0, all 13 daemons ran to 6h |
| laggard (user-02) | frozen at height **105** exactly (top index 104); conns 12 → **1** |
| upgraded network | all 12 daemons on identical tip **128** |
| rejections | 12× `has old version: 15 current: 14`, 12 drops |
| partition mechanism | 24 handshake refusals, **0 bans** — handshake-first confirmed at this scale too |
| user-01 wallet (upgraded) | **16 txs confirmed pre-fork + 22 post-fork** — transacted on both sides |
| user-02 wallet (laggard) | 14 confirmed pre-fork; **20 sent post-fork, 0 confirmed** — stranded, kept trying |
| cadence | 128 blocks / 6h = 2.81 min/block, matching the recalibration |

### Chain split (`hf_split_5m2u.yaml`, minority = miner-005 + user-02, 20% hashrate)

| check | result |
|---|---|
| two live chains | majority tip **125** (v15, 11 nodes identical) vs minority tip **108** (v14, both members identical) — 80/20 hashrate visible in the heights |
| divergence | minority rejected v15 blocks 15×/11×; miner-005 logged **12,167** handshake refusals reconnect-churning against the majority |
| **minority economy lives** | user-02 saw tx inclusions continuously after the fork (57 post-fork, 05:00→05:57) at the minority's slower cadence — vs **0** in the stall variant |
| completion | shadow exit 0, all 13 daemons to 6h |

Together with the stall gate this is the full answer to "what happens to
the n% who don't upgrade": **without hashpower they strand; with hashpower
they run a parallel economy on the old chain.**

### Late-upgrade healing (`hf_heal_split.yaml`, 50/50 split + phase upgrade)

| check | result |
|---|---|
| healer rode the minority chain | popped from top index **11** — two v14 blocks above fork index 10 |
| pop path fired | `Current top block ... has version 14 which disagrees with the ideal version 15`, blocks popped on phase-1 restart |
| healed | final height == majority tip (21), minority chain abandoned |
| phases | phase-0 clean exit at 55m, phase-1 restart on same data dir, shadow exit 0 |

Checker lesson encoded here: under a 50/50 hashrate split both chains grow
at the **same rate**, so equal heights are expected — chain divergence must
be proven behaviorally (the minority rejecting v15 blocks), not by height
inequality.

### Multi-fork (`hf_multifork_micro.yaml`, v14→v15→v16 at 10 and 20, 90 min)

The schedule string takes any number of forks; this run validates two in
one sim with a laggard cohort at each step:

| check | result |
|---|---|
| upgraded nodes | one tip, **38**, past both forks |
| relay-old (schedule ends at v14) | frozen at **10** — first fork; rejected only `15 vs 14` |
| relay-mid (schedule ends at v15) | frozen at **20** — second fork; rejected only `16 vs 15`, never `15 vs 14` — proving it followed fork 1 and stalled at fork 2 |
| partition | handshake refusals on both laggards |

So staged multi-fork scenarios (cohorts stuck at different consensus eras)
are measured behavior, not just architecture.

---

*Feature branch: `feat/hardfork-schedule`. Patch:
`patches/monero-fakechain-hardforks.patch`. Preflight guards:
`src/agent/user_agents.rs` (capability probe, duplicate knob, cuprate mix).*
