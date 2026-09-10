# Native Mining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let monerod mine natively inside a Shadow simulation (real miner thread, real RandomX, monerod's own difficulty algorithm) via a sleep-throttled miner patch, shipped as an opt-in `general.mining.mode: native` alongside the existing `generateblocks` path.

**Architecture:** A ~110-line vendored patch adds `--sim-hash-interval-ms` / `--sim-rx-full-dataset` to monerod's miner thread; it is built together with the hard-fork patch into ONE binary `monerod-sim` (with `monerod-hf` kept as a symlink alias). The Rust orchestrator gains a `general.mining` block, derives each miner's interval from its literal `hashrate` (hashes/second), substitutes `monerod-sim` for miners, probes capability via `--help`, and enforces preflight guards. The Python miner agent gets a native-mode loop (`start_mining` → `mining_status` → `stop_mining`) that bypasses the Poisson scheduler and the synthetic DAA.

**Tech Stack:** C++ (monero v0.18.5.1 patch), bash (setup.sh / update.sh / run_sim.sh), Rust (serde/serde_yaml config, orchestrator), Python 3 (agents, pytest), Shadow.

**Spec:** `docs/superpowers/specs/2026-09-10-native-mining-design.md`

## Global Constraints

- Monero base is exactly `monero.pin` = `v0.18.5.1`; the patch must `git apply --check` on that tag AND on top of `patches/monero-fakechain-hardforks.patch`.
- No PoW-verification bypass anywhere: only miner nodes may need the patched binary (spec §4).
- `general.mining` absent ⇒ generated output byte-identical to today (`tests/golden/*` must not change unless a task says so).
- Three operating modes must all keep working (spec §1.1): vanilla+generateblocks, monerod-sim+HF+generateblocks, monerod-sim(+HF)+native.
- Native mode: `hashrate` is LITERAL hashes/second, integer ≥ 1; `rx_full_dataset` defaults to true at the orchestrator; daemon flag defaults stay stock-shaped (0 / false).
- Default `mode` is `generateblocks` this release.
- Shared box: never run unscoped `pkill`/`killall`; scope process operations to user `lever65`. Use `nice -n10` for builds and sims.
- Commit after every task with the attribution trailer used in this repo (see `git log -3` for the exact `Co-Authored-By:` / `Claude-Session:` lines).
- Work on a feature branch `feat/native-mining` created from `main`.

---

## File map

| File | Responsibility |
|---|---|
| `patches/monero-sim-mining.patch` | NEW. Daemon-side throttle (miner.cpp/.h only). |
| `setup.sh` | `--sim-binary` (alias `--hardfork`) builds `monerod-sim` from both patches, installs alias symlink + provenance. |
| `update.sh` | `rebuild_sim_binary` mirrors setup.sh; auto-rebuild when monero is rebuilt and monerod-sim exists. |
| `run_sim.sh` | Preflight gate: binary present, pin match, `--help` carries the flags the config needs. |
| `src/config/types.rs` | NEW `MiningConfig { mode, rx_full_dataset }`, `MiningMode` enum, `GeneralConfig.mining`. |
| `src/utils/validation.rs` | `validate_mining_config(agents, mode)`: literal-hashrate rules in native mode. |
| `src/config_loader.rs` | Passes the mode into `validate_mining_config`. |
| `src/utils/mining.rs` | NEW pure helpers: `SIM_HASH_INTERVAL_KNOB`, `SIM_RX_FULL_DATASET_KNOB`, `hash_interval_ms`, `equilibrium_difficulty`, `binary_supports_sim_mining`, `args_mention_sim_knob`. |
| `src/utils/mod.rs` | `pub mod mining;` |
| `src/agent/user_agents.rs` | Native-mode wiring: binary substitution, guards, knob injection, agent attributes. |
| `agents/autonomous_miner.py` | Native-mode loop; generateblocks path untouched. |
| `agents/test_autonomous_miner.py` | Unit tests for the native loop with a fake RPC. |
| `tests/fixtures/native.yaml`, `tests/golden/native.yaml`, `tests/orchestrator_native.rs` | Golden test for native-mode rendering. |
| `test_configs/native_micro.yaml`, `test_configs/native_5m_split.yaml` | Runnable validation configs. |
| `docs/NATIVE_MINING.md`, `docs/20260512_how_pow_works.md`, `docs/HARDFORK_TESTING.md`, `README.md`, `CHANGELOG.md` | Documentation. |

---

### Task 0: Branch

**Files:** none

- [ ] **Step 1: Create the branch**

```bash
cd /home/lever65/monerosim_scale/monerosim
git status --short   # must be empty
git checkout -b feat/native-mining main
```

Expected: `Switched to a new branch 'feat/native-mining'`.

---

### Task 1: Vendor the patch and build `monerod-sim` via setup.sh

**Files:**
- Create: `patches/monero-sim-mining.patch`
- Modify: `setup.sh` (arg parsing ~lines 30-53, help text, `install_hardfork_monerod` ~lines 1129-1186, its call site)

**Interfaces:**
- Produces: `~/.monerosim/bin/monerod-sim` (both patches), `~/.monerosim/bin/monerod-hf` → symlink to `monerod-sim`, `~/.monerosim/bin/monerod-sim.provenance`. `monerod-sim --help` lists `fakechain-hard-forks`, `sim-hash-interval-ms`, `sim-rx-full-dataset`.

- [ ] **Step 1: Write the patch file**

Create `patches/monero-sim-mining.patch` with EXACTLY this content (it is a `git diff` against v0.18.5.1; it also applies after the hard-fork patch because the two touch different files):

````diff
diff --git a/src/cryptonote_basic/miner.cpp b/src/cryptonote_basic/miner.cpp
index fd13ff74d..74845ce13 100644
--- a/src/cryptonote_basic/miner.cpp
+++ b/src/cryptonote_basic/miner.cpp
@@ -100,6 +100,15 @@ namespace cryptonote
     const command_line::arg_descriptor<uint64_t>    arg_bg_mining_min_idle_interval_seconds =  {"bg-mining-min-idle-interval", "Specify min lookback interval in seconds for determining idle state", miner::BACKGROUND_MINING_DEFAULT_MIN_IDLE_INTERVAL_IN_SECONDS, true};
     const command_line::arg_descriptor<uint16_t>     arg_bg_mining_idle_threshold_percentage =  {"bg-mining-idle-threshold", "Specify minimum avg idle percentage over lookback interval", miner::BACKGROUND_MINING_DEFAULT_IDLE_THRESHOLD_PERCENTAGE, true};
     const command_line::arg_descriptor<uint16_t>     arg_bg_mining_miner_target_percentage =  {"bg-mining-miner-target", "Specify maximum percentage cpu use by miner(s)", miner::BACKGROUND_MINING_DEFAULT_MINING_TARGET_PERCENTAGE, true};
+    // Simulation mining (monerosim patch). Under a discrete-event network simulator
+    // (Shadow) simulated time only advances when a process makes a blocking syscall;
+    // the stock hash loop makes none, so it freezes the clock. sim-hash-interval-ms
+    // inserts one blocking sleep before every hash attempt, turning the miner into a
+    // geometric clock with a declared virtual hashrate of 1000/N hashes per second.
+    // PoW itself is unchanged: every block still carries a real RandomX hash that
+    // meets the real difficulty target, so unpatched peers validate it normally.
+    const command_line::arg_descriptor<uint64_t>    arg_sim_hash_interval_ms =  {"sim-hash-interval-ms", "Simulation only: sleep this many milliseconds before every hash attempt (0 = stock miner). Throttles the miner to a virtual hashrate so a discrete-event simulator sees a syscall per hash; forces a single mining thread and RandomX light mode unless --sim-rx-full-dataset is set.", 0, true};
+    const command_line::arg_descriptor<bool>        arg_sim_rx_full_dataset =   {"sim-rx-full-dataset", "Simulation only, with --sim-hash-interval-ms: allocate the full RandomX dataset (~2 GB, fast hashing) instead of light mode.", false, true};
   }
 
 
@@ -126,7 +135,9 @@ namespace cryptonote
     m_idle_threshold(BACKGROUND_MINING_DEFAULT_IDLE_THRESHOLD_PERCENTAGE),
     m_mining_target(BACKGROUND_MINING_DEFAULT_MINING_TARGET_PERCENTAGE),
     m_miner_extra_sleep(BACKGROUND_MINING_DEFAULT_MINER_EXTRA_SLEEP_MILLIS),
-    m_block_reward(0)
+    m_block_reward(0),
+    m_sim_hash_interval_ms(0),
+    m_sim_rx_full_dataset(false)
   {
     m_attrs.set_stack_size(THREAD_STACK_SIZE);
   }
@@ -292,6 +303,8 @@ namespace cryptonote
     command_line::add_arg(desc, arg_bg_mining_min_idle_interval_seconds);
     command_line::add_arg(desc, arg_bg_mining_idle_threshold_percentage);
     command_line::add_arg(desc, arg_bg_mining_miner_target_percentage);
+    command_line::add_arg(desc, arg_sim_hash_interval_ms);
+    command_line::add_arg(desc, arg_sim_rx_full_dataset);
   }
   //-----------------------------------------------------------------------------------------------------
   bool miner::init(const boost::program_options::variables_map& vm, network_type nettype)
@@ -337,6 +350,14 @@ namespace cryptonote
       }
     }
 
+    if(command_line::has_arg(vm, arg_sim_hash_interval_ms))
+      m_sim_hash_interval_ms = command_line::get_arg(vm, arg_sim_hash_interval_ms);
+    if(command_line::has_arg(vm, arg_sim_rx_full_dataset))
+      m_sim_rx_full_dataset = command_line::get_arg(vm, arg_sim_rx_full_dataset);
+    if(m_sim_hash_interval_ms)
+      MGINFO_YELLOW("*** SIMULATION MINING: throttled to one hash attempt every " << m_sim_hash_interval_ms
+        << " ms (single thread, RandomX " << (m_sim_rx_full_dataset ? "full dataset" : "light mode") << ") ***");
+
     // Background mining parameters
     // Let init set all parameters even if background mining is not enabled, they can start later with params set
     if(command_line::has_arg(vm, arg_bg_mining_enable))
@@ -378,6 +399,13 @@ namespace cryptonote
       m_threads_autodetect.push_back({epee::misc_utils::get_ns_count(), m_total_hashes});
       m_threads_total = 1;
     }
+    if (m_sim_hash_interval_ms)
+    {
+      // Simulation mining is a single geometric clock; extra threads would
+      // multiply the declared hashrate.
+      m_threads_autodetect.clear();
+      m_threads_total = 1;
+    }
     m_starter_nonce = crypto::rand<uint32_t>();
     CRITICAL_REGION_LOCAL(m_threads_lock);
     if(is_mining())
@@ -576,13 +604,19 @@ namespace cryptonote
       b.nonce = nonce;
       crypto::hash h;
 
-      if ((b.major_version >= RX_BLOCK_VERSION) && !rx_set)
+      if ((b.major_version >= RX_BLOCK_VERSION) && !rx_set && (!m_sim_hash_interval_ms || m_sim_rx_full_dataset))
       {
         // Must be non-zero value because 0 means "not a miner thread, run with secure JIT" in rx-slow-hash.c
         crypto::rx_set_miner_thread(th_local_index + 1, tools::get_max_concurrency());
         rx_set = true;
       }
 
+      // Simulation throttle: one blocking sleep per hash attempt. Under a
+      // discrete-event simulator this is what advances simulated time; the
+      // stock loop makes no syscalls and would freeze the clock.
+      if (m_sim_hash_interval_ms)
+        misc_utils::sleep_no_w(m_sim_hash_interval_ms);
+
       m_gbh(b, height, NULL, tools::get_max_concurrency(), h);
 
       if(check_hash(h, local_diff))
@@ -594,6 +628,8 @@ namespace cryptonote
         if(!m_phandler->handle_block_found(b, bvc) || !bvc.m_added_to_main_chain)
         {
           --m_config.current_extra_message_index;
+          if (m_sim_hash_interval_ms)
+            MGINFO("Simulation mining: found block at height " << height << " was not added to the main chain (stale template or lost race)");
         }else
         {
           //success update, lets update config
diff --git a/src/cryptonote_basic/miner.h b/src/cryptonote_basic/miner.h
index 72dc12762..8595d0c2c 100644
--- a/src/cryptonote_basic/miner.h
+++ b/src/cryptonote_basic/miner.h
@@ -175,5 +175,8 @@ namespace cryptonote
     static uint8_t get_percent_of_total(uint64_t some_time, uint64_t total_time);
     static boost::logic::tribool on_battery_power();
     std::atomic<uint64_t> m_block_reward;
+    // Simulation mining (monerosim patch): 0 = stock miner.
+    uint64_t m_sim_hash_interval_ms;
+    bool m_sim_rx_full_dataset;
   };
 }
````

- [ ] **Step 2: Verify the patch applies to the pinned tag (both bare and stacked)**

```bash
cd /home/lever65/monerosim_scale/monerosim
MONERO_DIR=/home/lever65/monerosim_scale/monero
W=$(mktemp -d)/m; git -C "$MONERO_DIR" worktree add --detach "$W" "$(tr -d '[:space:]' < monero.pin)"
git -C "$W" apply --check patches/monero-sim-mining.patch && echo BARE_OK
git -C "$W" apply patches/monero-fakechain-hardforks.patch
git -C "$W" apply --check patches/monero-sim-mining.patch && echo STACKED_OK
git -C "$MONERO_DIR" worktree remove --force "$W"; git -C "$MONERO_DIR" worktree prune
```

Expected: `BARE_OK` and `STACKED_OK`.

- [ ] **Step 3: Rework setup.sh's hard-fork install into the combined build**

In `setup.sh`:

(a) Argument parsing: keep `--hardfork` and add `--sim-binary` as a synonym. Replace the `--hardfork)` case with:

```bash
        --hardfork|--sim-binary)
            INSTALL_SIM_BINARY=true
            shift
            ;;
```

and rename every other use of `INSTALL_HARDFORK` to `INSTALL_SIM_BINARY` (`grep -n INSTALL_HARDFORK setup.sh`).

(b) Help text: replace the three `--hardfork` help lines with:

```bash
            echo "  --sim-binary           Also build monerod-sim: vanilla monerod (monero.pin) plus"
            echo "                         patches/monero-fakechain-hardforks.patch (--fakechain-hard-forks,"
            echo "                         network-upgrade sims) and patches/monero-sim-mining.patch"
            echo "                         (--sim-hash-interval-ms, native PoW mining under Shadow)."
            echo "                         Installs ~/.monerosim/bin/monerod-sim and the alias monerod-hf."
            echo "                         --hardfork is accepted as a synonym."
```

(c) Replace the whole `install_hardfork_monerod()` function with:

```bash
install_sim_monerod() {
    # monerod-sim = vanilla monero (monero.pin) + every vendored patch, each
    # flag-gated and stock when its flag is absent:
    #   patches/monero-fakechain-hardforks.patch  --fakechain-hard-forks
    #   patches/monero-sim-mining.patch           --sim-hash-interval-ms / --sim-rx-full-dataset
    # One build serves the fork-schedule and native-mining features; monerod-hf
    # is kept as a symlink alias so existing fork configs keep working.
    local patches=(
        "$SCRIPT_DIR/patches/monero-fakechain-hardforks.patch"
        "$SCRIPT_DIR/patches/monero-sim-mining.patch"
    )
    local p
    for p in "${patches[@]}"; do
        if [[ ! -f "$p" ]]; then
            log_err "Patch not found: $p"
            exit 1
        fi
    done
    if [[ ! -d "$MONERO_DIR/.git" ]]; then
        log_err "Monero checkout not found at $MONERO_DIR (run the main setup first)"
        exit 1
    fi
    local monero_ref
    monero_ref=$(tr -d '[:space:]' < "$SCRIPT_DIR/monero.pin")

    # Build in a DETACHED WORKTREE of the pinned checkout. The patches are
    # applied there and only there: the main checkout — and the primary
    # monerod built from it — stays byte-for-byte vanilla. Recreated from
    # scratch every run so no stale patch state can survive; ccache keeps the
    # rebuild cheap.
    local sim_build_dir="$MONEROSIM_HOME/build/monero-sim"
    mkdir -p "$MONEROSIM_HOME/build"
    local d
    for d in "$sim_build_dir" "$MONEROSIM_HOME/build/monero-hf"; do
        if [[ -d "$d" ]]; then
            git -C "$MONERO_DIR" worktree remove --force "$d" 2>/dev/null || rm -rf "$d"
        fi
    done
    git -C "$MONERO_DIR" worktree prune 2>/dev/null || true
    git -C "$MONERO_DIR" fetch --tags --force origin >/dev/null 2>&1 || true
    if ! git -C "$MONERO_DIR" worktree add --detach "$sim_build_dir" "$monero_ref"; then
        log_err "Could not create monero worktree at $monero_ref (see monero.pin)"
        exit 1
    fi

    # Tripwire: when monero.pin moves past what a patch applies to, fail
    # loudly here instead of drifting silently. Applied in order.
    for p in "${patches[@]}"; do
        if ! git -C "$sim_build_dir" apply --check "$p"; then
            log_err "$(basename "$p") no longer applies to monero $monero_ref"
            log_err "The patch must be rebased onto the new pin (or upstreamed)."
            exit 1
        fi
        git -C "$sim_build_dir" apply "$p"
    done
    (cd "$sim_build_dir" && git submodule update --init --recursive)

    log_info "Building patched monerod (monerod-sim, -j${BUILD_JOBS}) — this takes a while..."
    if ! (cd "$sim_build_dir" && mkdir -p build/release && cd build/release \
          && cmake -DCMAKE_BUILD_TYPE=Release ../.. > cmake.log 2>&1 \
          && nice -n10 make -j"$BUILD_JOBS" daemon); then
        log_err "monerod-sim build failed (see $sim_build_dir/build/release/cmake.log)"
        exit 1
    fi

    cp -f "$sim_build_dir/build/release/bin/monerod" "$MONEROSIM_BIN/monerod-sim"
    # Alias for configs that predate the combined build (daemon: monerod-hf).
    ln -sfn monerod-sim "$MONEROSIM_BIN/monerod-hf"
    rm -f "$MONEROSIM_BIN/monerod-hf.provenance"
    {
        echo "binary: monerod-sim (alias: monerod-hf)"
        echo "base: $monero_ref (monero.pin)"
        for p in "${patches[@]}"; do
            echo "patch: patches/$(basename "$p")"
            echo "patch_sha256: $(sha256sum "$p" | cut -d' ' -f1)"
        done
        echo "built: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "$MONEROSIM_BIN/monerod-sim.provenance"
    log_ok "Installed monerod-sim to $MONEROSIM_BIN/monerod-sim (alias monerod-hf)"
    cd "$SCRIPT_DIR"
}
```

(d) Update the call site (`grep -n install_hardfork_monerod setup.sh`) to call `install_sim_monerod` under `INSTALL_SIM_BINARY`.

- [ ] **Step 4: Build it**

```bash
cd /home/lever65/monerosim_scale/monerosim && nice -n10 ./setup.sh --sim-binary 2>&1 | tail -5
```

Expected: last line `Installed monerod-sim to /home/lever65/.monerosim/bin/monerod-sim (alias monerod-hf)`.

- [ ] **Step 5: Verify the installed binary**

```bash
B=~/.monerosim/bin/monerod-sim
$B --version
$B --help 2>&1 | grep -cE 'fakechain-hard-forks|sim-hash-interval-ms|sim-rx-full-dataset'
readlink ~/.monerosim/bin/monerod-hf
cat ~/.monerosim/bin/monerod-sim.provenance
```

Expected: version contains `v0.18.5.1`; grep count `3`; readlink prints `monerod-sim`; provenance lists both patches.

- [ ] **Step 6: Mode-2 regression (hard-fork feature through the alias)**

```bash
cd /home/lever65/monerosim_scale/monerosim
nice -n10 ./run_sim.sh --config test_configs/hf_micro_2node.yaml --name t1_hf_alias --no-monitor 2>&1 | tail -3
grep -E "Blocks created|Result:" archived_runs/*t1_hf_alias/summary.txt
```

Expected: `run_sim` exits 0 (this config's own checks are described at the top of the YAML: the laggard stalls at height 9, the miner keeps extending). `Blocks created PASS`.

- [ ] **Step 7: Commit**

```bash
git add patches/monero-sim-mining.patch setup.sh
git commit -m "feat(native-mining): vendor sim-mining patch, build monerod-sim (HF + mining) with monerod-hf alias"
```

---

### Task 2: update.sh rebuild and run_sim.sh preflight gate

**Files:**
- Modify: `update.sh` (`rebuild_hardfork` ~lines 327-374 and call site ~501-508; `--hardfork` arg parsing)
- Modify: `run_sim.sh` (~lines 613-645)

**Interfaces:**
- Consumes: `monerod-sim`, `monerod-sim.provenance` from Task 1.

- [ ] **Step 1: update.sh — rename and generalise the rebuild**

Replace `rebuild_hardfork()` with `rebuild_sim_binary()` whose body is identical to `install_sim_monerod` from Task 1 step 3(c) except: it takes `monero_dir="$1"` instead of `$MONERO_DIR`, uses `return` instead of `exit 1` on failure, and logs `log_info "Rebuilding monerod-sim ($monero_ref + vendored patches)..."`. Update the arg parser so `--hardfork` and a new `--sim-binary` both set `UPDATE_SIM_BINARY=true` (rename `UPDATE_HARDFORK`, `grep -n UPDATE_HARDFORK update.sh`). Replace the call site with:

```bash
    if [[ "$UPDATE_SIM_BINARY" == "true" ]] \
        || { [[ -x "$MONEROSIM_BIN/monerod-sim" || -x "$MONEROSIM_BIN/monerod-hf" ]] && { [[ "$MONERO_UPDATED" == "true" ]] || [[ "$UPDATE_MONERO" == "true" ]]; }; }; then
        if [[ -d "$DEPS_DIR/monero/.git" ]]; then
            rebuild_sim_binary "$DEPS_DIR/monero"
        else
            log_warn "monero checkout not found at $DEPS_DIR/monero — cannot rebuild monerod-sim"
        fi
    fi
```

- [ ] **Step 2: run_sim.sh — generalise the gate**

Replace the block from the comment `# monerod-hf: conditional capability gate` through `log_ok "monerod-hf matches pin and carries --fakechain-hard-forks"` / `fi` with:

```bash
    # monerod-sim: conditional capability gate, same philosophy as the cuprate
    # gate above — only fires when the config needs a patched daemon (names
    # monerod-sim/monerod-hf, sets fakechain-hard-forks, or enables native
    # mining), so a stale or absent monerod-sim never blocks an ordinary run.
    # The --help probe is the real check: a vanilla rebuild copied over
    # monerod-sim would print the SAME version string, but cannot know the flags.
    # Dev override: MONEROSIM_SKIP_SIM_BINARY_CHECK=1 (MONEROSIM_SKIP_HARDFORK_CHECK=1 still honoured).
    local sim_bin="$HOME/.monerosim/bin/monerod-sim"
    [[ -x "$sim_bin" ]] || sim_bin="$HOME/.monerosim/bin/monerod-hf"
    local needs_hf=0 needs_native=0
    grep -qE 'monerod-hf|monerod-sim|fakechain-hard-forks' "$CONFIG" 2>/dev/null && needs_hf=1
    grep -qE '^[[:space:]]*mode:[[:space:]]*native([[:space:]]|$)' "$CONFIG" 2>/dev/null && needs_native=1
    if [[ "${MONEROSIM_SKIP_SIM_BINARY_CHECK:-0}" == "1" || "${MONEROSIM_SKIP_HARDFORK_CHECK:-0}" == "1" ]]; then
        log_warn "MONEROSIM_SKIP_SIM_BINARY_CHECK=1 — skipping monerod-sim check"
    elif [[ $needs_hf == 1 || $needs_native == 1 ]]; then
        if [[ ! -x "$sim_bin" ]]; then
            log_err "Config needs the patched daemon but no monerod-sim at $HOME/.monerosim/bin/monerod-sim"
            log_info "Build it: ./setup.sh --sim-binary"
            exit 1
        fi
        if [[ -f "$SCRIPT_DIR/monero.pin" ]]; then
            local sim_ver sim_pin
            sim_pin=$(tr -d '[:space:]' < "$SCRIPT_DIR/monero.pin")
            sim_ver=$("$sim_bin" --version 2>&1 | head -n1)
            if [[ "$sim_ver" != *"${sim_pin}"* ]]; then
                log_err "monerod-sim is built from '$sim_ver', not pinned $sim_pin"
                log_info "Fix: ./update.sh --sim-binary --rebuild"
                exit 1
            fi
        fi
        local sim_help
        sim_help=$("$sim_bin" --help 2>/dev/null)
        if [[ $needs_hf == 1 ]] && ! grep -q 'fakechain-hard-forks' <<< "$sim_help"; then
            log_err "monerod-sim does not carry the hard fork schedule patch (vanilla binary?)"
            log_info "Fix: ./setup.sh --sim-binary"
            exit 1
        fi
        if [[ $needs_native == 1 ]] && ! grep -q 'sim-hash-interval-ms' <<< "$sim_help"; then
            log_err "monerod-sim does not carry the sim-mining patch (old monerod-hf build?)"
            log_info "Fix: ./setup.sh --sim-binary"
            exit 1
        fi
        log_ok "monerod-sim matches pin and carries the flags this config needs"
    fi
```

- [ ] **Step 3: Test the gate three ways**

```bash
cd /home/lever65/monerosim_scale/monerosim
./run_sim.sh --config test_configs/quickstart.yaml --preflight-only 2>&1 | grep -c monerod-sim      # expect 0 (gate silent)
./run_sim.sh --config test_configs/hf_micro_2node.yaml --preflight-only 2>&1 | grep monerod-sim   # expect the log_ok line
printf 'general:\n  stop_time: 1m\n  mining:\n    mode: native\nagents: {}\n' > /tmp/native_gate_probe.yaml
./run_sim.sh --config /tmp/native_gate_probe.yaml --preflight-only 2>&1 | grep -E "monerod-sim"     # expect the log_ok line
```

Expected as annotated. (The third config fails later in preflight for having no agents; only the gate line matters.)

- [ ] **Step 4: Commit**

```bash
git add update.sh run_sim.sh
git commit -m "feat(native-mining): update.sh rebuilds monerod-sim; run_sim.sh gates on the flags a config needs"
```

---

### Task 3: Config schema — `general.mining`

**Files:**
- Modify: `src/config/types.rs` (add after `TurnoverConfig`, ~line 433; add field to `GeneralConfig` and its `Default`)
- Modify: `src/config/mod.rs` (re-export)
- Test: inline `#[cfg(test)]` in `src/config/types.rs`

**Interfaces:**
- Produces: `pub enum MiningMode { Generateblocks, Native }` (serde `snake_case`), `pub struct MiningConfig { pub mode: MiningMode, pub rx_full_dataset: bool }`, `GeneralConfig.mining: MiningConfig` (serde default), `MiningConfig::is_native(&self) -> bool`.

- [ ] **Step 1: Write the failing tests** (append to the `#[cfg(test)] mod tests` in `src/config/types.rs`, or create one at the bottom of the file if none exists)

```rust
#[cfg(test)]
mod mining_config_tests {
    use super::*;

    #[test]
    fn mining_defaults_to_generateblocks_with_full_dataset() {
        let yaml = "stop_time: 1h\n";
        let g: GeneralConfig = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(g.mining.mode, MiningMode::Generateblocks);
        assert!(g.mining.rx_full_dataset);
        assert!(!g.mining.is_native());
    }

    #[test]
    fn mining_native_parses_and_overrides_dataset() {
        let yaml = "stop_time: 1h\nmining:\n  mode: native\n  rx_full_dataset: false\n";
        let g: GeneralConfig = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(g.mining.mode, MiningMode::Native);
        assert!(!g.mining.rx_full_dataset);
        assert!(g.mining.is_native());
    }

    #[test]
    fn mining_rejects_unknown_mode() {
        let yaml = "stop_time: 1h\nmining:\n  mode: socket\n";
        assert!(serde_yaml::from_str::<GeneralConfig>(yaml).is_err());
    }
}
```

- [ ] **Step 2: Run to verify they fail**

Run: `cargo test --lib mining_config_tests`
Expected: compile error (`MiningMode` not found).

- [ ] **Step 3: Implement**

Add to `src/config/types.rs` right after `TurnoverConfig`:

```rust
/// Block-production mode (see docs/NATIVE_MINING.md).
#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MiningMode {
    /// A Python agent per miner fires the `generateblocks` RPC on a seeded
    /// Poisson schedule (historical behaviour; `hashrate` is a weight).
    Generateblocks,
    /// monerod's own miner thread mines, throttled by
    /// `--sim-hash-interval-ms` (patches/monero-sim-mining.patch); `hashrate`
    /// is LITERAL hashes per second and monerod's difficulty algorithm drives
    /// block timing. Miners run `monerod-sim`.
    Native,
}

impl Default for MiningMode {
    fn default() -> Self {
        MiningMode::Generateblocks
    }
}

/// `general.mining` — how blocks get produced.
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct MiningConfig {
    #[serde(default)]
    pub mode: MiningMode,
    /// Native mode only: allocate the full ~2 GB RandomX dataset per miner
    /// (~1-2 ms/hash) instead of light mode (~20 ms/hash). Default true —
    /// with literal hashrates light mode is too slow (spec §7).
    #[serde(default = "default_rx_full_dataset")]
    pub rx_full_dataset: bool,
}

fn default_rx_full_dataset() -> bool {
    true
}

impl Default for MiningConfig {
    fn default() -> Self {
        Self {
            mode: MiningMode::default(),
            rx_full_dataset: default_rx_full_dataset(),
        }
    }
}

impl MiningConfig {
    pub fn is_native(&self) -> bool {
        self.mode == MiningMode::Native
    }
}
```

Add to `GeneralConfig` (after `experimental_cuprate_boot`):

```rust
    /// Block-production mode. Absent = `generateblocks` (historical). See
    /// docs/NATIVE_MINING.md and docs/superpowers/specs/2026-09-10-native-mining-design.md.
    #[serde(default)]
    pub mining: MiningConfig,
```

and `mining: MiningConfig::default(),` to `impl Default for GeneralConfig`. In `src/config/mod.rs`, add `MiningConfig, MiningMode` to the `pub use types::{...}` list (grep `pub use` in that file; if it re-exports `TurnoverConfig`, add next to it).

- [ ] **Step 4: Run tests**

Run: `cargo test --lib mining_config_tests && cargo test --test orchestrator_smoke`
Expected: 3 passed; golden unchanged (serde default does not alter output).

- [ ] **Step 5: Commit**

```bash
git add src/config/types.rs src/config/mod.rs
git commit -m "feat(native-mining): general.mining {mode, rx_full_dataset} config block"
```

---

### Task 4: Validation rules for literal hashrate

**Files:**
- Modify: `src/utils/validation.rs` (`validate_mining_config`, ~lines 140-203; tests module ~line 387+)
- Modify: `src/config_loader.rs` (call at ~line 33)

**Interfaces:**
- Consumes: `MiningMode` from Task 3.
- Produces: `pub fn validate_mining_config(agents: &BTreeMap<String, AgentConfig>, mode: MiningMode) -> Result<(), String>`.

- [ ] **Step 1: Write the failing tests** (append inside `mod tests` in `src/utils/validation.rs`; `base_agent()` and `single_agent()` helpers already exist there)

```rust
    fn miner(hashrate: u32) -> AgentConfig {
        let mut a = base_agent();
        a.hashrate = Some(hashrate);
        a.wallet = Some("monero-wallet-rpc".to_string());
        a.daemon = Some(DaemonConfig::Local("monerod".to_string()));
        a
    }

    #[test]
    fn generateblocks_mode_keeps_percentage_range() {
        use crate::config::MiningMode;
        assert!(validate_mining_config(&single_agent("m", miner(150)), MiningMode::Generateblocks).is_err());
        assert!(validate_mining_config(&single_agent("m", miner(100)), MiningMode::Generateblocks).is_ok());
    }

    #[test]
    fn native_mode_accepts_literal_hashrates_above_100() {
        use crate::config::MiningMode;
        assert!(validate_mining_config(&single_agent("m", miner(150)), MiningMode::Native).is_ok());
        assert!(validate_mining_config(&single_agent("m", miner(0)), MiningMode::Native).is_err());
    }

    #[test]
    fn native_mode_requires_at_least_one_miner() {
        use crate::config::MiningMode;
        let err = validate_mining_config(&single_agent("r", base_agent()), MiningMode::Native).unwrap_err();
        assert!(err.contains("no miners"), "{err}");
        assert!(validate_mining_config(&single_agent("r", base_agent()), MiningMode::Generateblocks).is_ok());
    }
```

- [ ] **Step 2: Run to verify they fail**

Run: `cargo test --lib validation::tests`
Expected: compile error (wrong arity).

- [ ] **Step 3: Implement**

Change the signature and body of `validate_mining_config`:

```rust
pub fn validate_mining_config(
    agents: &BTreeMap<String, AgentConfig>,
    mode: crate::config::MiningMode,
) -> Result<(), String> {
    use crate::config::MiningMode;
    let native = mode == MiningMode::Native;
    let mut total_hashrate = 0u64;
    let mut mining_agent_count = 0;

    for (agent_id, agent) in agents.iter() {
        if !agent.is_miner() {
            continue;
        }
        mining_agent_count += 1;

        if !agent.has_wallet() {
            return Err(format!(
                "Mining agent '{}' must have 'wallet' field for reward address",
                agent_id
            ));
        }

        let hashrate = agent.hashrate.ok_or_else(|| {
            format!(
                "Mining agent '{}' must have 'hashrate' field ({})",
                agent_id,
                if native { "hashes per second" } else { "percentage of network hashrate" }
            )
        })?;

        if native {
            if hashrate == 0 {
                return Err(format!(
                    "Mining agent '{}': hashrate must be >= 1 hash/second in native mode",
                    agent_id
                ));
            }
        } else if hashrate == 0 || hashrate > 100 {
            return Err(format!(
                "Mining agent '{}': hashrate {}% out of valid range (must be 1-100)",
                agent_id, hashrate
            ));
        }

        total_hashrate += hashrate as u64;
    }

    if native && mining_agent_count == 0 {
        return Err("general.mining.mode is native but the config has no miners \
                    (an agent with a hashrate field)"
            .to_string());
    }

    if !native && mining_agent_count > 0 && total_hashrate != 100 {
        log::warn!(
            "Total mining hashrate is {}% (expected 100%). Found {} mining agent(s).",
            total_hashrate,
            mining_agent_count
        );
    }

    Ok(())
}
```

Update the doc comment above it to say the range rule applies in generateblocks mode and that native mode reads literal hashes/second (>= 1, no sum rule). In `src/config_loader.rs` change the call to:

```rust
    validate_mining_config(&config.agents.agents, config.general.mining.mode)
        .map_err(|e| eyre!("Mining configuration error: {}", e))?;
```

Fix any other caller (`grep -rn validate_mining_config src/ tests/`).

- [ ] **Step 4: Run tests**

Run: `cargo test --lib validation && cargo test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/utils/validation.rs src/config_loader.rs
git commit -m "feat(native-mining): literal hashrate validation in native mode"
```

---

### Task 5: Pure helpers — interval, equilibrium difficulty, capability probe

**Files:**
- Create: `src/utils/mining.rs`
- Modify: `src/utils/mod.rs` (add `pub mod mining;`)

**Interfaces:**
- Produces:
  - `pub const SIM_HASH_INTERVAL_KNOB: &str = "sim-hash-interval-ms";`
  - `pub const SIM_RX_FULL_DATASET_KNOB: &str = "sim-rx-full-dataset";`
  - `pub fn hash_interval_ms(hashrate_hs: u32) -> u64`
  - `pub fn equilibrium_difficulty(total_hashrate_hs: u64) -> u64`
  - `pub fn args_mention_sim_knob(args: Option<&Vec<String>>) -> bool`
  - `pub fn binary_supports_sim_mining(path: &str, cache: &mut HashMap<String, bool>) -> bool`

- [ ] **Step 1: Write the failing tests** (in the new file)

```rust
//! Native-mining helpers (docs/NATIVE_MINING.md). Pure functions plus the
//! `--help` capability probe for patches/monero-sim-mining.patch.

use std::collections::HashMap;

/// monerod option added by patches/monero-sim-mining.patch: milliseconds of
/// blocking sleep before every hash attempt (0 = stock miner).
pub const SIM_HASH_INTERVAL_KNOB: &str = "sim-hash-interval-ms";
/// monerod option added by the same patch: allocate the full RandomX dataset.
pub const SIM_RX_FULL_DATASET_KNOB: &str = "sim-rx-full-dataset";
/// Monero's block-time target (seconds); D_eq = TARGET * total hashrate.
const DIFFICULTY_TARGET_SECS: u64 = 120;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interval_is_inverse_of_hashrate_rounded() {
        assert_eq!(hash_interval_ms(1), 1000);
        assert_eq!(hash_interval_ms(20), 50);
        assert_eq!(hash_interval_ms(3), 333);
        assert_eq!(hash_interval_ms(7), 143);
    }

    #[test]
    fn interval_never_below_one_ms() {
        assert_eq!(hash_interval_ms(5000), 1);
        assert_eq!(hash_interval_ms(u32::MAX), 1);
    }

    #[test]
    fn equilibrium_is_120_times_total() {
        assert_eq!(equilibrium_difficulty(100), 12_000);
        assert_eq!(equilibrium_difficulty(0), 0);
    }

    #[test]
    fn raw_args_detection() {
        let v = vec!["--sim-hash-interval-ms=50".to_string()];
        assert!(args_mention_sim_knob(Some(&v)));
        let w = vec!["--log-level=1".to_string()];
        assert!(!args_mention_sim_knob(Some(&w)));
        assert!(!args_mention_sim_knob(None));
    }

    #[test]
    fn probe_caches_and_handles_missing_binary() {
        let mut cache = HashMap::new();
        assert!(!binary_supports_sim_mining("/nonexistent/monerod", &mut cache));
        assert_eq!(cache.get("/nonexistent/monerod"), Some(&false));
    }
}
```

- [ ] **Step 2: Run to verify they fail**

Run: `cargo test --lib utils::mining`
Expected: compile errors (functions missing).

- [ ] **Step 3: Implement** (insert between the constants and the test module)

```rust
/// Sleep between hash attempts for a miner declaring `hashrate_hs` hashes per
/// second: round(1000 / H), floored at 1 ms.
pub fn hash_interval_ms(hashrate_hs: u32) -> u64 {
    if hashrate_hs == 0 {
        return 1000;
    }
    let ms = (1000.0_f64 / hashrate_hs as f64).round() as u64;
    ms.max(1)
}

/// Difficulty monerod's LWMA converges to when the network declares
/// `total_hashrate_hs` hashes per second and the target is 120 s.
pub fn equilibrium_difficulty(total_hashrate_hs: u64) -> u64 {
    DIFFICULTY_TARGET_SECS * total_hashrate_hs
}

/// True if any raw daemon arg sets --sim-hash-interval-ms (legacy
/// `daemon_args` or per-phase `daemon_N_args`).
pub fn args_mention_sim_knob(args: Option<&Vec<String>>) -> bool {
    args.map(|v| {
        v.iter()
            .any(|a| a.contains(&format!("--{}", SIM_HASH_INTERVAL_KNOB)))
    })
    .unwrap_or(false)
}

/// Capability probe: does `binary --help` list --sim-hash-interval-ms? A
/// version check can't tell — the patched build prints the same tag as
/// vanilla. Cached per path so a 300-agent config spawns the probe once per
/// distinct binary. Set MONEROSIM_SKIP_SIM_BINARY_CHECK=1 to force `true`
/// (tests / dev boxes without the binary).
pub fn binary_supports_sim_mining(path: &str, cache: &mut HashMap<String, bool>) -> bool {
    if std::env::var("MONEROSIM_SKIP_SIM_BINARY_CHECK").map(|v| v == "1").unwrap_or(false) {
        return true;
    }
    if let Some(v) = cache.get(path) {
        return *v;
    }
    let supported = std::process::Command::new(path)
        .arg("--help")
        .output()
        .map(|o| {
            let mut text = o.stdout;
            text.extend_from_slice(&o.stderr);
            String::from_utf8_lossy(&text).contains(SIM_HASH_INTERVAL_KNOB)
        })
        .unwrap_or(false);
    cache.insert(path.to_string(), supported);
    supported
}
```

Add `pub mod mining;` to `src/utils/mod.rs`.

- [ ] **Step 4: Run tests**

Run: `cargo test --lib utils::mining`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/utils/mining.rs src/utils/mod.rs
git commit -m "feat(native-mining): interval/equilibrium helpers and sim-mining capability probe"
```

---

### Task 6: Orchestrator wiring in user_agents.rs

**Files:**
- Modify: `src/agent/user_agents.rs` — the function containing the simple-daemon branch (~lines 1015-1075) and the merged-attributes block (~lines 1319-1330); the top-level guard area near line 559-577.

**Interfaces:**
- Consumes: `config.general.mining` (Task 3), helpers from Task 5.
- Produces: for miners in native mode the rendered daemon args contain `--sim-hash-interval-ms=<n>` (and `--sim-rx-full-dataset` unless disabled); the miner's binary resolves to `monerod-sim`; agent attributes include `mining_mode`, `hash_interval_ms`, `daemon_log_path`; generation log prints `Native mining: total hashrate H h/s, equilibrium difficulty ~D`.

Orientation for the implementer: `process_user_agents` (or the fn holding line ~1015) iterates agents; per agent it builds a merged `BTreeMap<String, OptionValue>` of daemon options (daemon_defaults + per-agent daemon_options) which it later passes as `daemon_options: &<map>` in a `NodeLaunchSpec { .. }` literal; `hf_in_options` is computed from that merged map (`grep -n "hf_in_options" src/agent/user_agents.rs`). The `general` config is reachable from this function (it already reads `turnover`, `node_implementations`); if it is not in scope as `config.general`, thread `&config.general.mining` in the same way `turnover` is threaded.

- [ ] **Step 1: Write the failing golden test**

Create `tests/fixtures/native.yaml`:

```yaml
general:
  stop_time: 30m
  simulation_seed: 12345
  enable_dns_server: true
  process_threads: 2
  mining:
    mode: native
  daemon_defaults:
    log-level: monitor
    no-zmq: true
    non-interactive: true
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  miner-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 20
    start_time: 0s
  miner-002:
    daemon: monerod-sim
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 3
    start_time: 0s
  relay-001:
    daemon: monerod
    start_time: 30s
```

Create `tests/orchestrator_native.rs` (copy the `normalize` fn verbatim from `tests/orchestrator_smoke.rs`, then):

```rust
#[test]
fn native_fixture_yaml_matches_golden() {
    // The capability probe needs a built monerod-sim; the golden covers
    // rendering, not the probe, so skip it here.
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/native.yaml"))
        .expect("native fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = normalize(&std::fs::read_to_string(&output_yaml).unwrap());

    // Structural assertions that do not depend on the golden file.
    assert!(actual.contains("--sim-hash-interval-ms=50"), "miner-001 (20 h/s) interval");
    assert!(actual.contains("--sim-hash-interval-ms=333"), "miner-002 (3 h/s) interval");
    assert!(actual.contains("--sim-rx-full-dataset"), "full dataset on by default");
    assert!(actual.contains("HOME/.monerosim/bin/monerod-sim"), "miners substituted to monerod-sim");
    assert_eq!(actual.matches("--sim-hash-interval-ms=").count(), 2, "only the two miners get the knob");
    assert!(actual.contains("mining_mode"), "mining_mode attribute passed to the miner agents");
    assert!(actual.contains("hash_interval_ms"), "hash_interval_ms attribute passed to the miner agents");
    assert!(actual.contains("daemon_log_path"), "daemon_log_path attribute passed to the miner agents");

    let golden_path = Path::new("tests/golden/native.yaml");
    if std::env::var("UPDATE_GOLDEN").is_ok() {
        std::fs::write(golden_path, &actual).unwrap();
        return;
    }
    let expected = std::fs::read_to_string(golden_path)
        .expect("tests/golden/native.yaml exists; run with UPDATE_GOLDEN=1 to refresh");
    assert_eq!(actual, expected, "regenerate with UPDATE_GOLDEN=1 cargo test --test orchestrator_native");
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test --test orchestrator_native`
Expected: FAIL on the first `assert!` (no `--sim-hash-interval-ms` in output).

- [ ] **Step 3: Implement the wiring**

In the function containing the simple-daemon branch, near where `hf_capability_cache` is created (after the hf/cuprate guard at ~line 559-577), add:

```rust
    use crate::utils::mining::{
        args_mention_sim_knob, binary_supports_sim_mining, equilibrium_difficulty,
        hash_interval_ms, SIM_HASH_INTERVAL_KNOB, SIM_RX_FULL_DATASET_KNOB,
    };
    let native_mining = general.mining.is_native();   // `general` = &config.general (see orientation)
    let mut sim_capability_cache: HashMap<String, bool> = HashMap::new();
    if native_mining {
        let total: u64 = user_agents
            .iter()
            .filter_map(|(_, cfg)| cfg.hashrate.map(|h| h as u64))
            .sum();
        log::info!(
            "Native mining: {} miner(s), total hashrate {} h/s, equilibrium difficulty ~{}",
            user_agents.iter().filter(|(_, c)| c.is_miner()).count(),
            total,
            equilibrium_difficulty(total)
        );
        println!(
            "  Native mining: total hashrate {} h/s -> equilibrium difficulty ~{}",
            total,
            equilibrium_difficulty(total)
        );
    }
```

Per agent, immediately after `hf_in_options` is computed, compute:

```rust
        let sim_in_options = merged_daemon_options.contains_key(SIM_HASH_INTERVAL_KNOB)
            || merged_daemon_options.contains_key(SIM_RX_FULL_DATASET_KNOB);
        let sim_in_raw_args = args_mention_sim_knob(user_agent_config.daemon_args.as_ref())
            || user_agent_config
                .daemon_phases
                .as_ref()
                .map(|phases| phases.values().any(|p| args_mention_sim_knob(p.args.as_ref())))
                .unwrap_or(false);
        if sim_in_options || sim_in_raw_args {
            return Err(color_eyre::eyre::eyre!(
                "Agent '{}': {} is set directly in daemon options/args. It is derived from \
                 general.mining (mode: native) and the agent's hashrate; remove it.",
                agent_id, SIM_HASH_INTERVAL_KNOB
            ));
        }
        if native_mining && user_agent_config.is_miner() && user_agent_config.has_daemon_phases() {
            return Err(color_eyre::eyre::eyre!(
                "Agent '{}': native mining does not support daemon phases on miners in this \
                 release (the mining knob is injected into the single daemon launch only).",
                agent_id
            ));
        }
```

(`merged_daemon_options` = whatever the merged map variable is called; use the existing name.)

In the simple-daemon branch, replace the `daemon_binary_path` computation's `else` arm (the monerod case, lines ~2037-2050 of the dossier) with:

```rust
            } else {
                let is_native_miner = native_mining && user_agent_config.is_miner();
                match &user_agent_config.daemon {
                    // Native miners on an unnamed/stock daemon run the patched build.
                    Some(DaemonConfig::Local(path)) if is_native_miner && (path == "monerod") => {
                        log::info!("Agent '{}': native mining -> daemon monerod-sim (was '{}')", agent_id, path);
                        resolve_binary_path_for_shadow("monerod-sim").map_err(|e| {
                            color_eyre::eyre::eyre!("Agent '{}': failed to resolve monerod-sim: {}", agent_id, e)
                        })?
                    }
                    Some(DaemonConfig::Local(path)) => {
                        resolve_binary_path_for_shadow(path).map_err(|e| {
                            color_eyre::eyre::eyre!(
                                "Agent '{}': failed to resolve daemon binary path '{}': {}",
                                agent_id,
                                path,
                                e
                            )
                        })?
                    }
                    _ if is_native_miner => {
                        log::info!("Agent '{}': native mining -> daemon monerod-sim (was unset)", agent_id);
                        resolve_binary_path_for_shadow("monerod-sim").map_err(|e| {
                            color_eyre::eyre::eyre!("Agent '{}': failed to resolve monerod-sim: {}", agent_id, e)
                        })?
                    }
                    _ => monerod_path.to_string(),
                }
            };
```

Immediately after the existing hard-fork capability check on `daemon_binary_path` (the `if (hf_in_options || ...) && !binary_supports_hf_schedule(...)` block), add:

```rust
            if native_mining
                && user_agent_config.is_miner()
                && !binary_supports_sim_mining(&daemon_binary_path, &mut sim_capability_cache)
            {
                return Err(color_eyre::eyre::eyre!(
                    "Agent '{}': general.mining.mode is native but '{}' does not support \
                     --sim-hash-interval-ms. Build the patched daemon with ./setup.sh --sim-binary \
                     (miners default to monerod-sim; an explicit daemon: must point at it).",
                    agent_id,
                    daemon_binary_path
                ));
            }
```

Then, before the `NodeLaunchSpec { .. }` literal for this branch, inject the knobs into the merged options map for native miners (clone the map if it is borrowed immutably):

```rust
            let mut daemon_options_for_launch = merged_daemon_options.clone();
            if native_mining && user_agent_config.is_miner() {
                let hs = user_agent_config.hashrate.unwrap_or(1);
                daemon_options_for_launch.insert(
                    SIM_HASH_INTERVAL_KNOB.to_string(),
                    OptionValue::Number(hash_interval_ms(hs) as i64),
                );
                if general.mining.rx_full_dataset {
                    daemon_options_for_launch.insert(
                        SIM_RX_FULL_DATASET_KNOB.to_string(),
                        OptionValue::Bool(true),
                    );
                }
            }
```

and pass `daemon_options: &daemon_options_for_launch` in the spec literal. (Cuprate-assigned nodes never reach this arm; cuprate miners are already rejected by `NodeCaps.can_mine`.)

In the merged-attributes block (~line 1319-1330, the one that inserts `hashrate`), add after the hashrate insert:

```rust
                if native_mining {
                    merged_attributes.insert("mining_mode".to_string(), "native".to_string());
                    if let Some(hs) = user_agent_config.hashrate {
                        merged_attributes.insert(
                            "hash_interval_ms".to_string(),
                            hash_interval_ms(hs).to_string(),
                        );
                    }
                    merged_attributes.insert(
                        "daemon_log_path".to_string(),
                        format!("{}/bitmonero.log", data_dir),
                    );
                }
```

where `data_dir` is the agent's daemon data dir string used for `--data-dir=` in this same function (grep `format!("--data-dir=` / the `data_dir` binding passed into `NodeLaunchSpec`).

- [ ] **Step 4: Run the tests, then create the golden**

Run: `cargo test --test orchestrator_native`
Expected: structural asserts pass; the golden read fails (file missing).

Run: `UPDATE_GOLDEN=1 cargo test --test orchestrator_native && cargo test`
Expected: golden written to `tests/golden/native.yaml`; full suite green; `tests/golden/smoke.yaml` and every other golden unchanged (`git status --short tests/golden` shows only the new file).

- [ ] **Step 5: Inspect the golden once by eye**

```bash
grep -nE "monerod-sim|sim-hash-interval|sim-rx-full|mining_mode|hash_interval_ms|daemon_log_path" tests/golden/native.yaml
```

Expected: miner-001 and miner-002 both run `HOME/.monerosim/bin/monerod-sim`, carry `--sim-hash-interval-ms=50` / `=333` and `--sim-rx-full-dataset`; relay-001 runs `HOME/.monerosim/bin/monerod` with neither; both miner agent processes carry the three attributes.

- [ ] **Step 6: Commit**

```bash
git add src/agent/user_agents.rs tests/fixtures/native.yaml tests/golden/native.yaml tests/orchestrator_native.rs
git commit -m "feat(native-mining): orchestrator wiring — monerod-sim substitution, knob injection, guards, agent attributes"
```

---

### Task 7: Python miner — native-mode loop

**Files:**
- Modify: `agents/autonomous_miner.py` (`__init__` ~line 28, `_setup_agent` ~line 83, `run_iteration` ~line 574, `_cleanup_agent` ~line 648)
- Test: `agents/test_autonomous_miner.py`

**Interfaces:**
- Consumes: attributes `mining_mode` (`"native"`), `hash_interval_ms`, `daemon_log_path` (Task 6); `MoneroRPC.start_mining(wallet_address, threads)`, `.stop_mining()`, `.mining_status()`, `.get_info()`.
- Produces: `AutonomousMinerAgent.native_mode: bool`, `_native_run_iteration() -> float`, `_native_try_start() -> bool`, `_native_scan_found_blocks() -> int`.

- [ ] **Step 1: Write the failing tests** (append to `agents/test_autonomous_miner.py`)

```python
import re


class _FakeDaemonRPC:
    """Scripted daemon RPC: start_mining answers from a queue, mining_status
    from a list, get_info is static."""

    def __init__(self, start_answers, status_answers, height=10, difficulty=1200):
        self.start_answers = list(start_answers)
        self.status_answers = list(status_answers)
        self.calls = []
        self._info = {"height": height, "difficulty": difficulty}

    def start_mining(self, wallet_address, threads=1):
        self.calls.append(("start_mining", wallet_address, threads))
        answer = self.start_answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def stop_mining(self):
        self.calls.append(("stop_mining",))
        return {"status": "OK"}

    def mining_status(self):
        self.calls.append(("mining_status",))
        return self.status_answers.pop(0)

    def get_info(self):
        return dict(self._info)


def _native_agent(shared_dir, tmp_path, rpc):
    log = tmp_path / "bitmonero.log"
    log.write_text("")
    agent = AutonomousMinerAgent(
        agent_id="miner-001",
        shared_dir=shared_dir,
        attributes=[["hashrate", "20"], ["is_miner", "true"],
                    ["mining_mode", "native"], ["hash_interval_ms", "50"],
                    ["daemon_log_path", str(log)]],
    )
    agent.daemon_rpc = rpc
    agent.wallet_address = "4AE8E3bcVm2hfdErzPbA3cNRvymbAfGWYXZX5oFk2dgwEi4BPKSJEZw237bRPPBdH2C5cSiTThV389ESmN3q3DSJ9zAgkc8"
    agent.mining_active = True
    return agent, log


def test_native_mode_is_detected_from_attributes(shared_dir, tmp_path):
    agent, _ = _native_agent(shared_dir, tmp_path, _FakeDaemonRPC([], []))
    assert agent.native_mode is True
    assert agent.hash_interval_ms == 50


def test_native_start_retries_while_busy_then_starts(shared_dir, tmp_path):
    from agents.monero_rpc import RPCError
    rpc = _FakeDaemonRPC(
        start_answers=[{"status": "BUSY"}, RPCError("Core is busy"), {"status": "OK"}],
        status_answers=[{"active": True, "speed": 20}],
    )
    agent, _ = _native_agent(shared_dir, tmp_path, rpc)
    assert agent._native_run_iteration() == 5.0      # BUSY -> retry soon
    assert agent._native_run_iteration() == 5.0      # RPCError -> retry soon
    assert agent.native_started is False
    assert agent._native_run_iteration() == agent.native_poll_interval   # OK -> started
    assert agent.native_started is True
    assert [c[0] for c in rpc.calls].count("start_mining") == 3
    assert rpc.calls[0][2] == 1                       # threads=1


def test_native_restarts_when_status_reports_inactive(shared_dir, tmp_path):
    rpc = _FakeDaemonRPC(
        start_answers=[{"status": "OK"}, {"status": "OK"}],
        status_answers=[{"active": True}, {"active": False}, {"active": True}],
    )
    agent, _ = _native_agent(shared_dir, tmp_path, rpc)
    agent._native_run_iteration()                     # start
    agent._native_run_iteration()                     # status active
    agent._native_run_iteration()                     # status inactive -> start again
    assert [c[0] for c in rpc.calls].count("start_mining") == 2


def test_native_scans_found_blocks_incrementally(shared_dir, tmp_path):
    rpc = _FakeDaemonRPC(start_answers=[{"status": "OK"}], status_answers=[{"active": True}] * 3)
    agent, log = _native_agent(shared_dir, tmp_path, rpc)
    agent._native_run_iteration()
    log.write_text(
        "2000-01-01 00:10:00.000\tI Found block abc123 at height 5 for difficulty: 1200\n"
        "2000-01-01 00:10:01.000\tI something else\n"
    )
    assert agent._native_scan_found_blocks() == 1
    assert agent.blocks_generated == 1
    with open(log, "a") as f:
        f.write("2000-01-01 00:12:00.000\tI Found block def456 at height 6 for difficulty: 1250\n")
    assert agent._native_scan_found_blocks() == 1     # only the new line
    assert agent.blocks_generated == 2
    assert agent.last_block_height == 6


def test_native_cleanup_stops_mining(shared_dir, tmp_path):
    rpc = _FakeDaemonRPC(start_answers=[{"status": "OK"}], status_answers=[{"active": True}])
    agent, _ = _native_agent(shared_dir, tmp_path, rpc)
    agent._native_run_iteration()
    agent.mining_start_time = 1.0
    agent._cleanup_agent()
    assert ("stop_mining",) in rpc.calls


def test_generateblocks_mode_unchanged_by_default(shared_dir):
    agent = AutonomousMinerAgent(agent_id="miner-002", shared_dir=shared_dir,
                                 attributes=[["hashrate", "20"], ["is_miner", "true"]])
    assert agent.native_mode is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/lever65/monerosim_scale/monerosim && source venv/bin/activate && pytest agents/test_autonomous_miner.py -q`
Expected: failures with `AttributeError: ... native_mode`.

- [ ] **Step 3: Implement**

In `__init__`, after the `# Mining control` block add:

```python
        # Native mining (docs/NATIVE_MINING.md): monerod's own miner thread,
        # throttled by --sim-hash-interval-ms, does the mining; this agent
        # only drives the lifecycle. Set by the orchestrator via attributes.
        self.native_mode = self.attributes.get('mining_mode') == 'native'
        self.hash_interval_ms = int(self.attributes.get('hash_interval_ms', '0') or 0)
        self.daemon_log_path = self.attributes.get('daemon_log_path')
        self.native_started = False
        self.native_poll_interval = float(os.getenv('NATIVE_POLL_INTERVAL', '30'))
        self._native_log_offset = 0
        self._native_polls = 0
        self._found_block_re = re.compile(
            r"Found block ([0-9a-f]{64}|\S+) at height (\d+) for difficulty: (\d+)")
```

and add `import re` to the module imports.

In `_setup_agent`, replace the three trailing `self.logger.info(...)` lines that mention "difficulty-only mode" / "Base expected block time" with:

```python
        if self.native_mode:
            self.logger.info(
                f"Native mining mode: monerod mines at {self.hashrate_pct:.0f} h/s "
                f"(hash interval {self.hash_interval_ms} ms); agent drives start/stop only")
        else:
            self.logger.info("Using difficulty-only mode: timing scales with LWMA difficulty adjustments")
            self.logger.info(f"Base expected block time: {120.0 / (self.hashrate_pct / 100.0):.1f}s "
                             f"(at baseline difficulty {self.baseline_difficulty})")
```

Add these methods to the class (after `_generate_block`):

```python
    # ------------------------------------------------------------------
    # Native mining mode
    # ------------------------------------------------------------------
    def _native_try_start(self) -> bool:
        """Issue start_mining once the daemon accepts it.

        monerod answers BUSY (or raises) until it considers itself
        synchronized, which needs at least one peer; keep retrying.
        """
        try:
            result = self.daemon_rpc.start_mining(self.wallet_address, threads=1)
        except RPCError as e:
            self.logger.info(f"start_mining not accepted yet ({e}); retrying")
            return False
        status = (result or {}).get('status', '')
        if status == 'OK':
            self.native_started = True
            self.mining_start_time = self.mining_start_time or time.time()
            self.logger.info("Native mining started (start_mining OK)")
            return True
        self.logger.info(f"start_mining returned status '{status}'; retrying")
        return False

    def _native_scan_found_blocks(self) -> int:
        """Tail the daemon log for 'Found block' lines written by the miner
        thread; count each once and mirror the generateblocks log line so
        log-based tooling keeps working. Returns the number of new blocks."""
        if not self.daemon_log_path:
            return 0
        new_blocks = 0
        try:
            with open(self.daemon_log_path, 'r', errors='replace') as f:
                f.seek(self._native_log_offset)
                for line in f:
                    m = self._found_block_re.search(line)
                    if not m:
                        continue
                    block_hash, height, difficulty = m.group(1), int(m.group(2)), int(m.group(3))
                    self.blocks_generated += 1
                    self.last_block_height = max(self.last_block_height, height + 1)
                    new_blocks += 1
                    self.logger.info(f"Block generated: {block_hash}")
                    self.logger.info(f"New height: {height + 1}, difficulty: {difficulty}")
                self._native_log_offset = f.tell()
        except OSError as e:
            self.logger.debug(f"Cannot read daemon log {self.daemon_log_path}: {e}")
        return new_blocks

    def _native_run_iteration(self) -> float:
        """One poll of the native mining lifecycle."""
        if not self.native_started:
            return self.native_poll_interval if self._native_try_start() else 5.0
        try:
            status = self.daemon_rpc.mining_status()
        except RPCError as e:
            self.logger.warning(f"mining_status failed: {e}")
            return self.native_poll_interval
        if not status.get('active', False):
            self.logger.warning("Daemon reports mining inactive; restarting")
            self.native_started = False
            self._native_try_start()
            return 5.0
        self._native_scan_found_blocks()
        self._native_polls += 1
        if self._native_polls % 10 == 0:
            self._update_statistics()
        return self.native_poll_interval
```

At the top of `run_iteration`, right after the `if not self.mining_active:` block, add:

```python
        if self.native_mode:
            return self._native_run_iteration()
```

In `_cleanup_agent`, before `# Log final statistics`, add:

```python
        if self.native_mode and self.daemon_rpc is not None:
            try:
                self._native_scan_found_blocks()
                self.daemon_rpc.stop_mining()
                self.logger.info("Native mining stopped (stop_mining)")
            except (RPCError, MethodNotAvailableError, OSError) as e:
                self.logger.warning(f"stop_mining during cleanup failed: {e}")
```

Note: `_get_current_difficulty()` (used by `_update_statistics`) reads `get_info` — it keeps working in native mode and reports the real difficulty.

- [ ] **Step 4: Run tests**

Run: `pytest agents/test_autonomous_miner.py agents/test_monero_rpc.py -q`
Expected: all pass (existing tests untouched).

- [ ] **Step 5: Commit**

```bash
git add agents/autonomous_miner.py agents/test_autonomous_miner.py
git commit -m "feat(native-mining): miner agent native-mode lifecycle loop (start/status/stop, log-based block attribution)"
```

---

### Task 8: Validation configs and the micro gate

**Files:**
- Create: `test_configs/native_micro.yaml`, `test_configs/native_5m_split.yaml`
- Create: `scripts/native_mining_check.py` (measurement helper used by the gates)

**Interfaces:**
- Produces: `python3 scripts/native_mining_check.py <run_dir> --expect-total-hashrate H --miners miner-001:20,miner-002:5` prints a table and exits 0 on PASS.

- [ ] **Step 1: Write `test_configs/native_micro.yaml`**

```yaml
# Native mining micro gate (docs/NATIVE_MINING.md §validation).
# Two miners declare LITERAL hashrates (20 + 5 = 25 h/s) -> monerod's own LWMA
# should settle near 120 x 25 = 3000; miner-001 should win ~80% of blocks; the
# two stock relays validate every block with real PoW. No Python Poisson
# scheduler, no synthetic DAA: the daemon mines.
general:
  stop_time: 3h
  simulation_seed: 12345
  bootstrap_end_time: 10m
  enable_dns_server: true
  shadow_log_level: warning
  progress: true
  process_threads: 2
  native_preemption: true
  mining:
    mode: native
  daemon_defaults:
    log-level: monitor
    max-log-file-size: 0
    db-sync-mode: fastest
    no-zmq: true
    non-interactive: true
  wallet_defaults:
    log-level: 1
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  miner-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 20
    start_time: 0s
  miner-002:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 5
    start_time: 0s
  relay-001:
    daemon: monerod
    start_time: 30s
  relay-002:
    daemon: monerod
    start_time: 60s
  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
```

- [ ] **Step 2: Write `test_configs/native_5m_split.yaml`**

Same `general`/`network` as above but `stop_time: 4h`, five miners `miner-001..005` each `hashrate: 20` (total 100 h/s, D_eq ~12000), two relays, the monitor. Header comment: "5-way equal split: each miner should win 20% ± 5 points."

- [ ] **Step 3: Write `scripts/native_mining_check.py`**

```python
#!/usr/bin/env python3
"""Native-mining gate checker (docs/NATIVE_MINING.md).

Reads every miner's daemon stdout under <run_dir>/shadow.data/hosts/<miner>/
and asserts: cadence, difficulty, block share, zero PoW rejections on relays.
Exit 0 = PASS, 1 = FAIL. Prints a table either way.
"""
import argparse
import glob
import re
import statistics
import sys
from datetime import datetime

FOUND = re.compile(r"^(\S+ \S+)\t.*Found block (\S+) at height (\d+) for difficulty: (\d+)")
REJECT = re.compile(r"does not have enough proof of work|verification failed")


def parse_found(path):
    out = []
    with open(path, errors="replace") as f:
        for line in f:
            m = FOUND.match(line)
            if m:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
                out.append((int(m.group(3)), ts, int(m.group(4))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--miners", required=True, help="id:hashrate,id:hashrate,...")
    ap.add_argument("--cadence-tol", type=float, default=0.15)
    ap.add_argument("--difficulty-tol", type=float, default=0.25)
    ap.add_argument("--share-tol", type=float, default=5.0)
    ap.add_argument("--last", type=int, default=30, help="blocks in the steady-state window")
    a = ap.parse_args()

    miners = dict(kv.split(":") for kv in a.miners.split(","))
    miners = {k: int(v) for k, v in miners.items()}
    total_hs = sum(miners.values())
    per_miner, all_blocks = {}, []
    for mid in miners:
        files = glob.glob(f"{a.run_dir}/shadow.data/hosts/{mid}/monerod*.stdout")
        blocks = [b for f in files for b in parse_found(f)]
        per_miner[mid] = blocks
        all_blocks += blocks
    all_blocks.sort()
    ok = True
    rows = []

    def check(name, value, target, tol, fmt="{:.1f}"):
        nonlocal ok
        good = abs(value - target) <= tol
        ok &= good
        rows.append((name, fmt.format(value), fmt.format(target), "PASS" if good else "FAIL"))

    n = len(all_blocks)
    rows.append(("blocks found (all miners)", str(n), ">= %d" % (a.last + 5), "PASS" if n >= a.last + 5 else "FAIL"))
    ok &= n >= a.last + 5
    if n >= a.last + 5:
        tail = all_blocks[-a.last:]
        intervals = [(t2 - t1).total_seconds() for (_, t1, _), (_, t2, _) in zip(tail, tail[1:])]
        check("mean interval, last %d (s)" % a.last, statistics.mean(intervals), 120.0, 120.0 * a.cadence_tol)
        d_eq = 120 * total_hs
        check("difficulty, last block", tail[-1][2], d_eq, d_eq * a.difficulty_tol, "{:.0f}")
        for mid, hs in miners.items():
            share = 100.0 * len(per_miner[mid]) / n
            check(f"share {mid} (%)", share, 100.0 * hs / total_hs, a.share_tol)
    rejects = 0
    for f in glob.glob(f"{a.run_dir}/shadow.data/hosts/relay-*/monerod*.stdout"):
        with open(f, errors="replace") as fh:
            rejects += sum(1 for line in fh if REJECT.search(line))
    rows.append(("PoW rejections on relays", str(rejects), "0", "PASS" if rejects == 0 else "FAIL"))
    ok &= rejects == 0

    w = max(len(r[0]) for r in rows)
    for r in rows:
        print(f"{r[0]:<{w}}  {r[1]:>10}  {r[2]:>10}  {r[3]}")
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the micro gate**

```bash
cd /home/lever65/monerosim_scale/monerosim
nice -n10 ./run_sim.sh --config test_configs/native_micro.yaml --name gate_native_micro --no-monitor 2>&1 | tail -3
RD=$(ls -dt archived_runs/*gate_native_micro | head -1)
python3 scripts/native_mining_check.py "$RD" --miners miner-001:20,miner-002:5
grep -E "PASS|FAIL|Result" "$RD/summary.txt"
```

Expected: checker `RESULT: PASS`; summary.txt shows `Blocks created PASS` and `Blocks propagated PASS` (miner wallets receive coinbase). If `Blocks propagated` fails, inspect `$RD/shadow.data/hosts/miner-001/*agent*.stdout` for `start_mining` retries and the wallet balance; do not relax the gate.

- [ ] **Step 5: Run the 5-way split**

```bash
nice -n10 ./run_sim.sh --config test_configs/native_5m_split.yaml --name gate_native_split --no-monitor 2>&1 | tail -3
RD=$(ls -dt archived_runs/*gate_native_split | head -1)
python3 scripts/native_mining_check.py "$RD" --miners miner-001:20,miner-002:20,miner-003:20,miner-004:20,miner-005:20
```

Expected: `RESULT: PASS`.

- [ ] **Step 6: Commit**

```bash
git add test_configs/native_micro.yaml test_configs/native_5m_split.yaml scripts/native_mining_check.py
git commit -m "test(native-mining): micro and 5-way split gate configs + checker"
```

---

### Task 9: Determinism, mixed-implementation, and cost gates

**Files:** none new (results go into the doc in Task 10). Reuse `scripts/compare_determinism.py` if it accepts two run dirs (`python3 scripts/compare_determinism.py --help`); otherwise use the inline comparison below.

- [ ] **Step 1: A/A determinism**

```bash
cd /home/lever65/monerosim_scale/monerosim
for i in 1 2; do nice -n10 ./run_sim.sh --config test_configs/native_micro.yaml --name gate_native_aa$i --no-monitor > /dev/null 2>&1; done
for i in 1 2; do RD=$(ls -dt archived_runs/*gate_native_aa$i | head -1); grep -h "Found block" $RD/shadow.data/hosts/miner-00*/monerod*.stdout | sed -E 's/.*Found block (\S+) at height ([0-9]+).*/\2 \1/' | sort -n > /tmp/aa$i.txt; done
diff /tmp/aa1.txt /tmp/aa2.txt && echo AA_IDENTICAL
```

Expected: `AA_IDENTICAL`. Note: `native_preemption: true` is set in the config; if the two runs differ, rerun both with `native_preemption: false` (preemption is documented as non-deterministic in `src/config/types.rs`) and record which setting was used.

- [ ] **Step 2: Mixed implementation — a cuprate relay validates native blocks**

Copy `test_configs/native_micro.yaml` to `/tmp/native_cuprate.yaml`, add under `general:`:

```yaml
  node_implementations:
    cuprated: 1.0
```

(so every eligible relay becomes cuprate; miners stay monerod-sim). Confirm `~/.monerosim/bin/cuprated` exists (`ls -la ~/.monerosim/bin/cuprated`; if missing, follow the build note at the top of `cuprate.pin`). Run:

```bash
nice -n10 ./run_sim.sh --config /tmp/native_cuprate.yaml --name gate_native_cuprate --no-monitor 2>&1 | tail -3
RD=$(ls -dt archived_runs/*gate_native_cuprate | head -1)
grep -l cuprated $RD/shadow_agents.yaml && grep -hoE "height[^,]*" $RD/shadow.data/hosts/relay-001/*.stdout | tail -3
```

Expected: the cuprate relay's log shows it adding blocks up to the miners' tip height (compare with `grep -c "Found block" $RD/shadow.data/hosts/miner-00*/monerod*.stdout`). Record the tip heights.

- [ ] **Step 3: Cost measurement — light vs full dataset**

```bash
sed 's/^    mode: native$/    mode: native\n    rx_full_dataset: false/' test_configs/native_micro.yaml > /tmp/native_light.yaml
nice -n10 ./run_sim.sh --config /tmp/native_light.yaml --name gate_native_light --no-monitor > /dev/null 2>&1
for n in gate_native_micro gate_native_light; do RD=$(ls -dt archived_runs/*$n | head -1); echo "$n: $(grep 'Wall time' $RD/summary.txt)  maxRSS(miner-001)=$(sort -t, -k3 -n $RD/memory_samples.csv 2>/dev/null | tail -1)"; done
```

Expected: full-dataset run is markedly faster in wall time than light; record both wall times and the miner RSS delta (~2 GB expected for full). If `memory_samples.csv` has a different layout, read its header first and adapt the column.

- [ ] **Step 4: Record results**

Write the numbers (A/A verdict, cuprate tip parity, light vs full wall/RSS) into `/tmp/native_gate_results.txt` for Task 10. No commit in this task.

---

### Task 10: Documentation and changelog

**Files:**
- Create: `docs/NATIVE_MINING.md`
- Modify: `docs/20260512_how_pow_works.md` (section "Aside: the `mininghook` branch")
- Modify: `docs/HARDFORK_TESTING.md` (§3 Install)
- Modify: `README.md` (feature list / docs index — grep for `HARDFORK_TESTING` and add a sibling line)
- Modify: `CHANGELOG.md` (`[Unreleased]`)

- [ ] **Step 1: Write `docs/NATIVE_MINING.md`** with these sections, filling numbers from Task 8/9 results:

```markdown
# Native Mining under Shadow

**Status:** shipped (opt-in) YYYY-MM-DD. Gates: micro, 5-way split, A/A determinism,
cuprate relay, light-vs-full cost (§7).

## 1. What it is
[monerod's own miner thread mines; one blocking sleep per hash attempt; real RandomX,
real LWMA; only miners run monerod-sim. 2-3 paragraphs from spec §2-§4.]

## 2. The three operating modes
[table from spec §1.1]

## 3. Install
./setup.sh --sim-binary   (monerod-sim + alias monerod-hf; ./update.sh --sim-binary --rebuild)

## 4. Config
[schema from spec §6.1; literal hashrate; rx_full_dataset; what the orchestrator injects;
the printed equilibrium difficulty; guards and their messages]

## 5. What the agent does in native mode
[spec §8]

## 6. Cost model
[spec §7 with the MEASURED light/full numbers from Task 9]

## 7. Validation results
[tables: micro (cadence, difficulty, share, rejections), split, A/A, cuprate, cost]

## 8. Fidelity notes and limits
[LWMA window grows to 720 → retargets over hours; warm-up transient at heights 1-4;
no daemon phases on native miners; cuprate cannot mine; phase 2 (adversarial) pointer
to the spec §10]
```

- [ ] **Step 2: Correct the PoW doc**

In `docs/20260512_how_pow_works.md`, replace the paragraph beginning `monerosim deliberately avoids patching monerod —` and the table's `(hypothetical)` column header with a short note:

```markdown
> **Update 2026-09:** monerosim now ships an alternative, `general.mining.mode: native`
> (docs/NATIVE_MINING.md): a vendored patch makes monerod's own miner thread sleep
> before every hash attempt, so the stock loop's "no syscalls" problem described above
> goes away while PoW and verification stay real. The socket-based `mininghook` branch
> described below was evaluated and rejected in favour of that design
> (docs/superpowers/specs/2026-09-10-native-mining-design.md §9). The table is kept for
> history.
```

- [ ] **Step 3: HARDFORK_TESTING.md §3**

Replace the install block with:

```bash
./setup.sh --sim-binary          # build + install ~/.monerosim/bin/monerod-sim (alias monerod-hf)
./update.sh --sim-binary --rebuild
```

and one sentence: "`monerod-hf` is now a symlink to `monerod-sim`, which also carries the native-mining patch (docs/NATIVE_MINING.md); `daemon: monerod-hf` keeps working."

- [ ] **Step 4: README pointer and CHANGELOG**

README: add a bullet next to the hard-fork testing pointer: `- **Native mining** — monerod mines for real under Shadow (opt-in): docs/NATIVE_MINING.md`.

CHANGELOG `[Unreleased]`:

```markdown
- **Native mining (opt-in)**: `general.mining.mode: native` makes miners run
  `monerod-sim`, whose miner thread mines with real RandomX throttled by
  `--sim-hash-interval-ms` (patches/monero-sim-mining.patch); monerod's own
  difficulty algorithm drives block timing and `hashrate` is read as literal
  hashes/second. Validators need no patch. Default stays `generateblocks`.
  See `docs/NATIVE_MINING.md`.
  **Change:** `./setup.sh --hardfork` now builds `monerod-sim` (hard-fork +
  mining patches) and installs `monerod-hf` as a symlink alias; `--sim-binary`
  is the new spelling.
```

- [ ] **Step 5: Commit**

```bash
git add docs/NATIVE_MINING.md docs/20260512_how_pow_works.md docs/HARDFORK_TESTING.md README.md CHANGELOG.md
git commit -m "docs(native-mining): NATIVE_MINING.md, PoW doc correction, install notes, changelog"
```

---

### Task 11: Final verification and merge readiness

- [ ] **Step 1: Full suites**

```bash
cd /home/lever65/monerosim_scale/monerosim
cargo test 2>&1 | tail -3
source venv/bin/activate && pytest -q 2>&1 | tail -3
git status --short tests/golden        # only tests/golden/native.yaml added
```

Expected: all green; no golden drift besides the new file.

- [ ] **Step 2: Mode-1 regression (vanilla + generateblocks untouched)**

```bash
nice -n10 ./run_sim.sh --config test_configs/quickstart.yaml --name final_mode1 --no-monitor 2>&1 | tail -2
grep -E "Result" archived_runs/*final_mode1/summary.txt
```

Expected: `Result: ALL CHECKS PASSED` (or whatever the quickstart's baseline prints today — compare with the most recent quickstart archive).

- [ ] **Step 3: Hand off**

Use `superpowers:finishing-a-development-branch` to merge `feat/native-mining` into `main` (squash not required; the per-task commits are the history), then push.
