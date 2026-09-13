# Sim-Only Relay of Withheld Blocks (γ>0 selfish mining) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a default-off `monerod-sim` flag `--sim-relay-alt-blocks` so an attacker's bridge daemon relays a *locally-submitted, equal-height* block (which stock monerod refuses to do), removing the last structural barrier to measuring γ>0 selfish mining.

**Architecture:** A new monero C++ patch (`patches/monero-sim-selfish-relay.patch`) adds the flag to `cryptonote::core` via the 4-touch pattern and relaxes exactly one relay gate in `handle_block_found` (a local-submission-only path). Wiring is **config-only**: a bridge sets `daemon: monerod-hf` (the installed `monerod-sim` alias, a symlink) + `daemon_options: {sim-relay-alt-blocks: true}` — no Rust source change, so all four goldens stay byte-identical and only phase-4 configs opt in. A phase-4 experiment then combines the relay flag with the existing `topology_node` placement knob to measure realized γ.

**Tech Stack:** monero v0.18.5.1 C++ (patched via `setup.sh install_sim_monerod`); Rust orchestrator (config-gen tests via `config_loader` + `orchestrator` library APIs); Python apparatus (`agents.selfish_*`, `scripts/selfish_mining_analysis.py`) — unchanged; Shadow discrete-event sim.

**Spec:** `docs/superpowers/specs/2026-09-13-sim-relay-withheld-blocks-design.md` (read it alongside this plan — the plan argues from it).

## Global Constraints

- Branch `feat/native-mining`. **Local only — never push/merge without the user's explicit go.**
- Flag is **default-off, sim-only, `monerod-sim`-only, and relays only locally-submitted blocks** (`handle_block_found` is reached only from `submit_block` RPC + the miner thread — never P2P). Stock monerod and every non-opt-in config are unchanged.
- The four goldens `tests/golden/{smoke,quickstart,native,selfish}.yaml` MUST stay **byte-identical**. Verify with `cargo test` (goldens are separate test fns; `UPDATE_GOLDEN=1` is the regen escape hatch — do NOT set it unless a golden is *intended* to change, which here it is not).
- Run `cargo test` **WITHOUT** a global `MONEROSIM_SKIP_SIM_BINARY_CHECK=1` (it breaks `utils::mining::tests::probe_caches_and_handles_missing_binary`). Individual golden/integration tests set that var themselves.
- Python apparatus + `realized_gamma` analysis are already γ-ready — **do not modify** `agents/*.py`, `venv/`, or `scripts/selfish_mining_analysis.py`.
- **Shared box, two hazards:** (1) user1 runs their own monero workloads; (2) a *separate lever65 agent* may be running Shadow sims. So `-u lever65` scoping is **not** sufficient for kills. NEVER broad-kill shadow. Track only your OWN run (`run_sim.sh` PID / `archived_runs/<run_id>/.owner_pid`). `nice -n10` long runs. No `agents/*.py` or `venv/` edits while any sim is live.
- **Rebuilding `monerod-sim` overwrites `~/.monerosim/bin/monerod-sim`** (which `monerod-hf` symlinks to). A late-starting daemon in *another* run could `exec` the swapped binary. Pre-flight `pgrep -u lever65 -x shadow` MUST be empty before rebuilding; if busy, wait or ask.

---

## File Structure

- **Create `patches/monero-sim-selfish-relay.patch`** — the new monero patch (touches `src/cryptonote_core/cryptonote_core.cpp` + `src/cryptonote_core/cryptonote_core.h` only). Generated *on top of* the fakechain+mining patches so it applies as patch #3. (Task 1)
- **Modify `setup.sh`** (`install_sim_monerod`, ~line 1138) — add the new patch as the third `patches` array element; extend the comment block. (Task 2)
- **Create `tests/fixtures/selfish_relay.yaml`** — small config fixture (copy of `tests/fixtures/selfish.yaml`) whose bridges carry the relay flag; input for the config-gen test. (Task 4)
- **Create `tests/orchestrator_selfish_relay.rs`** — targeted config-gen test mirroring `tests/orchestrator_selfish.rs`; asserts the flag + `monerod-hf` binary path are emitted. (Task 4)
- **Create `test_configs/selfish_phase4/gamma_relay.yaml`** — the phase-4 experiment config (mirror of `test_configs/selfish_phase3/gamma_lift.yaml` with relay-enabled bridges). (Task 5)
- **Modify `docs/20260912_selfish_mining_results.md`** (phase-4 section) + **`docs/SELFISH_MINING.md`** (document the flag) — after the run. (Task 6)

**No production Rust source changes.** The only production-code edit outside the patch is one array line in `setup.sh`.

---

## Task 1: Author `patches/monero-sim-selfish-relay.patch`

> **⚠ MAIN-LOOP / NOT DELEGATED.** This is security-sensitive dual-use C++ (a selfish-mining relay enabler). Per frugal routing, security-sensitive changes stay in the main loop. The controller executes this task inline and spot-reads the generated diff before committing.

**Files:**
- Create: `patches/monero-sim-selfish-relay.patch`
- Transient edits (in a scratch worktree, NOT committed to monero): `sibling_repos/monero/src/cryptonote_core/cryptonote_core.cpp`, `sibling_repos/monero/src/cryptonote_core/cryptonote_core.h`

**Interfaces:**
- Consumes: monero v0.18.5.1 source at `sibling_repos/monero` (live vanilla checkout); `monero.pin`; the two existing patches in `patches/`.
- Produces: `patches/monero-sim-selfish-relay.patch` — adds core flag `--sim-relay-alt-blocks` (member `m_sim_relay_alt_blocks`, default `false`) and relaxes the `handle_block_found` relay gate. Consumed by Task 2 (setup.sh) and Task 3 (build).

**Background — the exact current source (monero v0.18.5.1, verified this session):**

`src/cryptonote_core/cryptonote_core.cpp`, `handle_block_found` (the gate, lines 1311–1337):
```cpp
    CHECK_AND_ASSERT_MES(!bvc.m_verifivation_failed, false, "mined block failed verification");
    if(bvc.m_added_to_main_chain)
    {
      cryptonote_connection_context exclude_context = {};
      NOTIFY_NEW_FLUFFY_BLOCK::request arg{};
      arg.current_blockchain_height = m_blockchain_storage.get_current_blockchain_height();
      std::vector<crypto::hash> missed_txs;
      for (const auto &tx_hash : b.tx_hashes)
      {
        if (m_blockchain_storage.have_tx(tx_hash))
          continue;
        missed_txs.push_back(tx_hash);
      }
      if(missed_txs.size() &&  m_blockchain_storage.get_block_id_by_height(get_block_height(b)) != get_block_hash(b))
      {
        LOG_PRINT_L1("Block found but, seems that reorganize just happened after that, do not relay this block");
        return true;
      }
      CHECK_AND_ASSERT_MES(!missed_txs.size(), false, "can't find some transactions in found block:" << get_block_hash(b)
        << " b.tx_hashes.size()=" << b.tx_hashes.size() << ", missed_txs.size()" << missed_txs.size());

      block_to_blob(b, arg.b.block);
      // Relay an empty fluffy block
      arg.b.txs.clear();

      m_pprotocol->relay_block(arg, exclude_context);
    }
    return true;
```

`block_verification_context` (`src/cryptonote_basic/verification_context.h:65-74`) — note the source typo `m_verifivation_failed`, and that there is **no** `m_added_to_alt_chain` field:
```cpp
  struct block_verification_context
  {
    bool m_added_to_main_chain;
    bool m_verifivation_failed; //bad block, should drop connection
    bool m_marked_as_orphaned;
    bool m_already_exists;
    bool m_partial_block_reward;
    bool m_bad_pow;
    bool m_missing_txs;
  };
```

**⚠ RULING — deviation from spec §1 (documented, narrowing):** The spec's Design §1 lists a *second* change — skipping the `missed_txs` reorg early-return (line ~1324) for the alt-relay case. **This plan implements the gate relaxation only** and leaves the `missed_txs` guard and the `CHECK_AND_ASSERT_MES(!missed_txs.size(), ...)` untouched. Rationale: phase-4 attacker blocks are **empty** (no tx agents → `b.tx_hashes` empty → `missed_txs` empty), so both the guard (line 1324) and the assert (line 1329) are provable no-ops; the gate change alone fully enables the experiment. Relaxing *only* the guard (as §1 says) would not actually enable tx-bearing alt-block relay either, because the assert at line 1329 independently returns `false` when txs are missing — so the guard-skip is unobservable given empty blocks and incomplete given tx-bearing blocks. Gate-only is the minimal, smallest-blast-radius change. Tx-bearing alt-block relay is therefore explicitly **out of scope** (matching the spec's own "unvalidated caveat / risk" framing); enabling it later would require relaxing *both* the guard and the assert. Record this ruling in the SDD ledger.

- [ ] **Step 1: Create the patch-generation worktree with fakechain+mining already applied**

The new patch must be diffed against source that already has the first two patches, because the fakechain patch also touches `cryptonote_core.cpp`; generating against vanilla could make patch #3 fail to apply after #1. Run:
```bash
cd /home/lever65/monerosim_scale/monerosim
PIN=$(tr -d '[:space:]' < monero.pin)
GEN=$(mktemp -d)/relay-gen
git -C sibling_repos/monero worktree add --detach "$GEN" "$PIN"
git -C "$GEN" apply "$PWD/patches/monero-fakechain-hardforks.patch"
git -C "$GEN" apply "$PWD/patches/monero-sim-mining.patch"
git -C "$GEN" add -A && git -C "$GEN" commit -q -m "base: fakechain+mining (patch-gen baseline)"
echo "GEN=$GEN"   # note this path; used by later steps
```
Expected: two clean `git apply`s and a commit. If either apply fails, the pin moved — stop and reconcile before continuing.

- [ ] **Step 2: Edit A — declare the `arg_descriptor`** in `$GEN/src/cryptonote_core/cryptonote_core.cpp`

Find the existing `arg_fluffy_blocks` descriptor (a bool arg, ~line 177) and add the new descriptor immediately after it. Anchor:
```cpp
  static const command_line::arg_descriptor<bool> arg_fluffy_blocks  = {
    "fluffy-blocks"
  , "Relay blocks as fluffy blocks (obsolete, now default)"
  , true
  };
```
Insert after it:
```cpp
  // Simulation/research only (monerosim selfish-mining patch). Stock monerod never
  // relays alternative (equal-height) blocks ("never relay alternative blocks",
  // blockchain.cpp). This flag makes handle_block_found — reached ONLY from local
  // submission (submit_block RPC / miner thread), never from P2P — relay a
  // locally-submitted accepted alt-block, enabling gamma>0 selfish-mining
  // experiments. Off by default; no effect on stock behavior when absent.
  static const command_line::arg_descriptor<bool> arg_sim_relay_alt_blocks = {
    "sim-relay-alt-blocks"
  , "Simulation only: relay a locally-submitted block even when it is accepted as an alternative (equal-height) block instead of extending the main chain. Off by default. Only affects blocks submitted locally (submit_block RPC / miner), never P2P-received blocks."
  , false
  };
```

- [ ] **Step 3: Edit B — register the arg in `init_options`** (same file)

In `cryptonote::core::init_options(...)`, find the line `command_line::add_arg(desc, arg_regtest_on);` and add after it:
```cpp
    command_line::add_arg(desc, arg_sim_relay_alt_blocks);
```

- [ ] **Step 4: Edit C — read the arg in `init`** (same file)

In `cryptonote::core::init(...)`, find the line `bool keep_fakechain = command_line::get_arg(vm, arg_keep_fakechain);` and add after it:
```cpp
    m_sim_relay_alt_blocks = command_line::get_arg(vm, arg_sim_relay_alt_blocks);
    if (m_sim_relay_alt_blocks)
      MGINFO_RED("*** SIMULATION: --sim-relay-alt-blocks is ON. This daemon will relay locally-submitted alternative (equal-height) blocks. Simulation/research only. ***");
```

- [ ] **Step 5: Edit D — declare the member** in `$GEN/src/cryptonote_core/cryptonote_core.h`

Find the private member `bool m_offline;` (~line 1125) and add after it (in-class default initializer, matching the file's style, e.g. `m_test_drop_download = true;` at line 1069):
```cpp
     bool m_sim_relay_alt_blocks = false; //!< simulation only: relay locally-submitted alternative (equal-height) blocks (monerosim selfish-mining patch)
```
(Indentation is 5 leading spaces, matching `m_offline`.)

- [ ] **Step 6: Edit E — relax the relay gate** in `$GEN/src/cryptonote_core/cryptonote_core.cpp`

In `handle_block_found`, change the single gate line:
```cpp
    if(bvc.m_added_to_main_chain)
```
to:
```cpp
    if(bvc.m_added_to_main_chain ||
       (m_sim_relay_alt_blocks && !bvc.m_verifivation_failed && !bvc.m_already_exists))
```
(Preserve the typo `m_verifivation_failed` — it is the real field name. An accepted alt-block is signalled by *absence* of failure/exists, since there is no `m_added_to_alt_chain` field.)

- [ ] **Step 7: Generate the patch**
```bash
git -C "$GEN" diff HEAD -- src/cryptonote_core/cryptonote_core.cpp src/cryptonote_core/cryptonote_core.h \
  > "$PWD/patches/monero-sim-selfish-relay.patch"
wc -l "$PWD/patches/monero-sim-selfish-relay.patch"   # sanity: non-empty, ~40-60 lines
```
Spot-read the patch: it must contain exactly the five edits above and nothing else (no fakechain/mining lines — those are in the baseline commit, so `diff HEAD` excludes them).

- [ ] **Step 8: Verify it applies as patch #3 in the real order**
```bash
V=$(mktemp -d)/verify
git -C sibling_repos/monero worktree add --detach "$V" "$PIN"
git -C "$V" apply --check "$PWD/patches/monero-fakechain-hardforks.patch" && git -C "$V" apply "$PWD/patches/monero-fakechain-hardforks.patch"
git -C "$V" apply --check "$PWD/patches/monero-sim-mining.patch"          && git -C "$V" apply "$PWD/patches/monero-sim-mining.patch"
git -C "$V" apply --check "$PWD/patches/monero-sim-selfish-relay.patch"   && echo "PATCH #3 APPLIES CLEAN"
```
Expected: `PATCH #3 APPLIES CLEAN`. This is the same `git apply --check` the setup.sh tripwire runs, so a pass here means the build tripwire will pass.

- [ ] **Step 9: Clean up the scratch worktrees**
```bash
git -C sibling_repos/monero worktree remove --force "$GEN"
git -C sibling_repos/monero worktree remove --force "$V"
git -C sibling_repos/monero worktree prune
git -C sibling_repos/monero status --short   # expect clean: sibling monero stays vanilla
```

- [ ] **Step 10: Commit the patch**
```bash
git add patches/monero-sim-selfish-relay.patch
git commit -m "feat(patch): sim-only --sim-relay-alt-blocks for gamma>0 selfish mining

New monero patch relaxing the handle_block_found relay gate (local-submission
path only) so a bridge relays a locally-submitted equal-height alt-block, which
stock monerod refuses. Default off, monerod-sim only. Gate-only change (empty
experiment blocks make the missed_txs guard/assert no-ops; tx-bearing alt-relay
left out of scope). Applies as patch #3 after fakechain+mining."
```

---

## Task 2: Wire the patch into `setup.sh`

**Files:**
- Modify: `setup.sh` (`install_sim_monerod`, the `patches=(...)` array ~line 1138 and the comment block ~line 1132)

**Interfaces:**
- Consumes: `patches/monero-sim-selfish-relay.patch` (Task 1).
- Produces: `install_sim_monerod` now applies three patches in order; the existing `git apply --check` tripwire (lines ~1178-1185) gates the new one automatically. Consumed by Task 3 (build).

- [ ] **Step 1: Add the patch to the array**

Find (setup.sh ~line 1138):
```bash
    local patches=(
        "$SCRIPT_DIR/patches/monero-fakechain-hardforks.patch"
        "$SCRIPT_DIR/patches/monero-sim-mining.patch"
    )
```
Change to:
```bash
    local patches=(
        "$SCRIPT_DIR/patches/monero-fakechain-hardforks.patch"
        "$SCRIPT_DIR/patches/monero-sim-mining.patch"
        "$SCRIPT_DIR/patches/monero-sim-selfish-relay.patch"
    )
```

- [ ] **Step 2: Extend the comment block**

Find (setup.sh ~line 1134-1135):
```bash
    #   patches/monero-fakechain-hardforks.patch  --fakechain-hard-forks
    #   patches/monero-sim-mining.patch           --sim-hash-interval-ms / --sim-rx-full-dataset
```
Add a third line after them:
```bash
    #   patches/monero-sim-selfish-relay.patch    --sim-relay-alt-blocks (sim-only, gamma>0)
```

- [ ] **Step 3: Verify setup.sh still parses and the array is correct**
```bash
cd /home/lever65/monerosim_scale/monerosim
bash -n setup.sh && echo "SYNTAX OK"
grep -c "monerosim-scale\|SCRIPT_DIR/patches/monero-" setup.sh >/dev/null; \
grep -n "SCRIPT_DIR/patches/monero-sim-selfish-relay.patch" setup.sh
```
Expected: `SYNTAX OK` and exactly one grep hit for the new patch line inside the array.

- [ ] **Step 4: Commit**
```bash
git add setup.sh
git commit -m "build(setup): apply monero-sim-selfish-relay.patch in install_sim_monerod

Third vendored patch; the existing git-apply --check tripwire gates it. No
behavior change until a config opts in via --sim-relay-alt-blocks."
```

---

## Task 3: Rebuild `monerod-sim` + smoke-test the flag

> **⚠ MAIN-LOOP / NOT DELEGATED — shared-resource build.** Overwrites `~/.monerosim/bin/monerod-sim`. Pre-flight the live-sim check; a subagent must not run this blindly on a shared box.

**Files:** none (produces the installed binary `~/.monerosim/bin/monerod-sim` + `monerod-hf` symlink)

**Interfaces:**
- Consumes: the patched build pipeline (Tasks 1-2).
- Produces: a `monerod-sim` whose `--help` lists `--sim-relay-alt-blocks` (plus the pre-existing `--sim-hash-interval-ms` / `--fakechain-hard-forks`). Consumed by Task 6 (the run).

- [ ] **Step 1: Pre-flight — confirm the box is free of ALL live sims**
```bash
pgrep -u lever65 -x shadow && echo "BUSY — do NOT rebuild" || echo "clear to build"
```
Expected: `clear to build`. If BUSY (mine or the other lever65 agent's), STOP — wait or ask the user. Do not proceed.

- [ ] **Step 2: Build (nice'd; the tripwire gates the patch)**
```bash
cd /home/lever65/monerosim_scale/monerosim
nice -n10 ./setup.sh --sim-binary 2>&1 | tail -40
```
Expected: reaches `Installed monerod-sim to .../monerod-sim (alias monerod-hf)`. If a `git apply --check` tripwire fails for the new patch, Task 1's patch is stale — return to Task 1. (Build takes several minutes; ccache keeps it cheap.)

- [ ] **Step 3: Smoke-test the flag on both the binary and the alias**
```bash
~/.monerosim/bin/monerod-sim --help 2>&1 | grep -- "--sim-relay-alt-blocks" && echo "FLAG PRESENT (monerod-sim)"
~/.monerosim/bin/monerod-hf  --help 2>&1 | grep -- "--sim-relay-alt-blocks" && echo "FLAG PRESENT (monerod-hf symlink)"
# regression: the other two sim flags must still be present in the combined build
~/.monerosim/bin/monerod-sim --help 2>&1 | grep -- "--sim-hash-interval-ms" && echo "mining flag still present"
~/.monerosim/bin/monerod-sim --help 2>&1 | grep -- "--fakechain-hard-forks" && echo "fakechain flag still present"
```
Expected: all four echoes fire. (No commit — this task produces a binary, not tracked files. Record the smoke result in the SDD ledger.)

---

## Task 4: Targeted config-gen test + goldens byte-identical

**Files:**
- Create: `tests/fixtures/selfish_relay.yaml`
- Create: `tests/orchestrator_selfish_relay.rs`

**Interfaces:**
- Consumes: `config_loader::load_config(&Path) -> Result<Config>` and `orchestrator::generate_agent_shadow_config(&Config, &Path) -> Result<()>` (the same library APIs `tests/orchestrator_selfish.rs` uses); `config.general.shared_dir: String` (overridable field).
- Produces: a passing test proving `daemon: monerod-hf` + `daemon_options: {sim-relay-alt-blocks: true}` emits `--sim-relay-alt-blocks` and the `monerod-hf` binary path in the generated Shadow YAML.

- [ ] **Step 1: Create the fixture from the known-valid selfish fixture**

Copy `tests/fixtures/selfish.yaml` to `tests/fixtures/selfish_relay.yaml`, then edit the copy: for **every** agent whose `script:` is `agents.selfish_bridge`, set `daemon: monerod-hf` and add a `daemon_options:` entry `sim-relay-alt-blocks: true` (create the `daemon_options:` map if the bridge doesn't already have one; if it does, add the key alongside the existing options). Leave the miners (`agents.selfish_miner` / `agents.autonomous_miner`) and everything else untouched. Run:
```bash
cp tests/fixtures/selfish.yaml tests/fixtures/selfish_relay.yaml
# then apply the edits above, and confirm the bridges changed:
grep -nA6 "selfish_bridge" tests/fixtures/selfish_relay.yaml
grep -c "monerod-hf" tests/fixtures/selfish_relay.yaml            # == number of bridge agents
grep -c "sim-relay-alt-blocks" tests/fixtures/selfish_relay.yaml  # == number of bridge agents
```
Expected: the two counts are equal and match the bridge count in the fixture.

- [ ] **Step 2: Write the failing test** — create `tests/orchestrator_selfish_relay.rs`:
```rust
// tests/orchestrator_selfish_relay.rs
// Proves the config-only wiring for the sim-relay-alt-blocks flag: a bridge with
// `daemon: monerod-hf` + `daemon_options: {sim-relay-alt-blocks: true}` emits the
// flag and resolves to the patched monerod-hf binary in the generated Shadow YAML.
use monerosim::{config_loader, orchestrator};
use std::path::Path;
use tempfile::TempDir;

#[test]
fn selfish_relay_bridge_emits_flag_and_patched_binary() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/selfish_relay.yaml"))
        .expect("selfish_relay fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = std::fs::read_to_string(&output_yaml).unwrap();

    // The relay flag is rendered as a bare flag by options_to_args (Bool(true)).
    let flag_count = actual.matches("--sim-relay-alt-blocks").count();
    assert!(flag_count >= 1, "relay flag emitted for at least one bridge");

    // Bridges resolve to the patched binary via the monerod-hf symlink alias.
    assert!(actual.contains(".monerosim/bin/monerod-hf"),
            "relay bridge daemon resolves to the monerod-hf (monerod-sim) binary");

    // Exactly the bridges get the flag: count matches monerod-hf daemon occurrences.
    let hf_count = actual.matches(".monerosim/bin/monerod-hf").count();
    assert_eq!(flag_count, hf_count,
               "the relay flag appears on exactly the monerod-hf (bridge) daemons, nowhere else");
}
```

- [ ] **Step 3: Run it to see it pass (wiring already exists in the orchestrator)**
```bash
cargo test --test orchestrator_selfish_relay -- --nocapture
```
Expected: PASS. The generic wiring (`options_to_args` → bare flag; `resolve_binary_path_for_shadow` → `~/.monerosim/bin/monerod-hf`) already exists, so this test should pass on first run. If it FAILS on the flag assertion, inspect the generated `shadow_agents.yaml` — a filter may be stripping `sim-*` flags (would need investigation, not expected). If it fails to load the fixture, revisit Step 1.

- [ ] **Step 4: Confirm the four goldens are byte-identical (no regression)**
```bash
cargo test --test orchestrator_selfish --test orchestrator_native 2>&1 | tail -5
cargo test smoke quickstart 2>&1 | tail -5
```
Expected: all golden tests PASS (no `UPDATE_GOLDEN`). Because no production Rust changed and phase-4 uses a new config, the goldens cannot have changed.

- [ ] **Step 5: Full suite green**
```bash
cargo test 2>&1 | tail -15   # NOTE: no global MONEROSIM_SKIP_SIM_BINARY_CHECK
```
Expected: all Rust tests pass, including `probe_caches_and_handles_missing_binary`.

- [ ] **Step 6: Commit**
```bash
git add tests/fixtures/selfish_relay.yaml tests/orchestrator_selfish_relay.rs
git commit -m "test(selfish): config-gen test for --sim-relay-alt-blocks wiring

Proves a bridge with daemon: monerod-hf + daemon_options{sim-relay-alt-blocks}
emits the bare flag and resolves to the patched monerod-hf binary. Goldens
unchanged (config-only, opt-in)."
```

---

## Task 5: Phase-4 experiment config

**Files:**
- Create: `test_configs/selfish_phase4/gamma_relay.yaml`

**Interfaces:**
- Consumes: the `topology_node` placement knob (already shipped); the relay flag wiring (Tasks 1-4); the 1200-node GML `gml_processing/1200_nodes_caida_with_loops.gml`.
- Produces: a runnable phase-4 config combining relay + placement. Consumed by Task 6.

- [ ] **Step 1: Author the config** — mirror `test_configs/selfish_phase3/gamma_lift.yaml` exactly, with ONE class of change: every bridge (`bridge-1`..`bridge-5`) gets `daemon: monerod-hf` and its `daemon_options` gains `sim-relay-alt-blocks: true` (keeping `out-peers: 16`). Miners, honest nodes, relays, topology_node placements, `reaction_delay_ms: 10`, `alpha`/hashrates, `fixed-difficulty: 1200`, `eyal_sirer`, seed, stop_time all stay identical to phase 3. Write:
```yaml
# Selfish-mining PHASE 4: gamma vs RELAY (the sim-only --sim-relay-alt-blocks flag)
# + per-agent placement (topology_node). Phase 3 proved placement alone can't lift
# gamma because stock monerod never relays the attacker's withheld tie-block. This
# config removes that barrier: the bridges run monerod-hf (= patched monerod-sim)
# with --sim-relay-alt-blocks, so a locally-submitted equal-height block IS relayed
# one hop into the honest network. Same placement as gamma_lift.yaml so RELAY is the
# only variable added vs phase 3.
#
# Placement (1200-node CAIDA GML; node id == index):
#   honest-001 -> 100, honest-002 -> 500, honest-003 -> 900  [spread far apart]
#   attacker-miner + bridge-1 (DETECTOR) -> 500 (central)
#   bridge-2 -> 100, bridge-3 -> 900, bridge-4 -> 300, bridge-5 -> 1100  [publishers near honest nodes]
# alpha=0.40, fixed-difficulty:1200, eyal_sirer, reaction 10ms.
general:
  stop_time: 6h
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
    fixed-difficulty: 1200
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
  honest-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 2
    start_time: 0s
    topology_node: 100
  honest-002:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 2
    start_time: 0s
    topology_node: 500
  honest-003:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 2
    start_time: 0s
    topology_node: 900
  attacker-miner:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.selfish_miner
    hashrate: 4
    start_time: 0s
    topology_node: 500
    daemon_options:
      offline: true
    attributes:
      strategy: eyal_sirer
      bridges: "bridge-1,bridge-2,bridge-3,bridge-4,bridge-5"
      attack_start_height: "0"
      reaction_delay_ms: "10"
  bridge-1:                      # DETECTOR: bridges[0], central; RELAY-ENABLED
    daemon: monerod-hf
    script: agents.selfish_bridge
    daemon_options:
      out-peers: 16
      sim-relay-alt-blocks: true
    start_time: 0s
    topology_node: 500
  bridge-2:                      # publisher near honest-001; RELAY-ENABLED
    daemon: monerod-hf
    script: agents.selfish_bridge
    daemon_options:
      out-peers: 16
      sim-relay-alt-blocks: true
    start_time: 0s
    topology_node: 100
  bridge-3:                      # publisher near honest-003; RELAY-ENABLED
    daemon: monerod-hf
    script: agents.selfish_bridge
    daemon_options:
      out-peers: 16
      sim-relay-alt-blocks: true
    start_time: 0s
    topology_node: 900
  bridge-4:                      # publisher in region 1; RELAY-ENABLED
    daemon: monerod-hf
    script: agents.selfish_bridge
    daemon_options:
      out-peers: 16
      sim-relay-alt-blocks: true
    start_time: 0s
    topology_node: 300
  bridge-5:                      # publisher in region 5; RELAY-ENABLED
    daemon: monerod-hf
    script: agents.selfish_bridge
    daemon_options:
      out-peers: 16
      sim-relay-alt-blocks: true
    start_time: 0s
    topology_node: 1100
  relay-001:
    daemon: monerod
    start_time: 30s
  relay-002:
    daemon: monerod
    start_time: 40s
  relay-003:
    daemon: monerod
    start_time: 50s
  relay-004:
    daemon: monerod
    start_time: 60s
  relay-005:
    daemon: monerod
    start_time: 70s
  relay-006:
    daemon: monerod
    start_time: 80s
  relay-007:
    daemon: monerod
    start_time: 90s
  relay-008:
    daemon: monerod
    start_time: 100s
  relay-009:
    daemon: monerod
    start_time: 110s
  relay-010:
    daemon: monerod
    start_time: 120s
  relay-011:
    daemon: monerod
    start_time: 130s
  relay-012:
    daemon: monerod
    start_time: 140s
  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
```

- [ ] **Step 2: Validate it generates + carries the flag on exactly the bridges**
```bash
cd /home/lever65/monerosim_scale/monerosim
cargo build --release 2>&1 | tail -3
OUT=$(mktemp -d)/phase4
MONEROSIM_SKIP_SIM_BINARY_CHECK=1 ./target/release/monerosim \
  --config test_configs/selfish_phase4/gamma_relay.yaml --output "$OUT" 2>&1 | tail -20 || true
# The generated Shadow YAML (name may be shadow_agents.yaml / shadow.yaml under $OUT):
GENYAML=$(find "$OUT" -name "*.yaml" | head -1)
grep -c -- "--sim-relay-alt-blocks" "$GENYAML"   # expect 5 (five bridges)
grep -c ".monerosim/bin/monerod-hf" "$GENYAML"   # expect 5
grep -c ".monerosim/bin/monerod-sim" "$GENYAML"  # expect 5 (2 miners via native-mining substitution + ... verify count)
```
Expected: `--sim-relay-alt-blocks` appears exactly 5 times (bridges only); `monerod-hf` appears 5 times. NOTE: the bare binary may print a non-fatal error removing a pre-existing shared dir *after* generating — the YAML under `$OUT` is what matters (per the known monerosim-generate quirk); the `|| true` tolerates it. Do NOT point `--output` at a shared/default path on this shared box; the `mktemp -d` keeps it isolated.

- [ ] **Step 3: Commit**
```bash
git add test_configs/selfish_phase4/gamma_relay.yaml
git commit -m "exp(selfish): phase-4 config — relay flag + placement (gamma vs relay)

Mirrors phase-3 gamma_lift.yaml; only change is bridges run monerod-hf with
--sim-relay-alt-blocks so the withheld tie-block is relayed one hop. Measures
whether relay (barrier 2 removed) + placement lifts realized gamma above ~0."
```

---

## Task 6: Run phase-4, measure realized γ, document

> **⚠ MAIN-LOOP / NOT DELEGATED — long run on a shared box + result judgment.** Pre-flight the live-sim check; `nice` the run; track only your own run dir.

**Files:**
- Modify: `docs/20260912_selfish_mining_results.md` (add a phase-4 section)
- Modify: `docs/SELFISH_MINING.md` (document the `--sim-relay-alt-blocks` flag)

**Interfaces:**
- Consumes: the built `monerod-sim` (Task 3), the phase-4 config (Task 5), `scripts/selfish_mining_analysis.py` (unchanged).
- Produces: a realized-γ measurement + honest write-up.

- [ ] **Step 1: Pre-flight**
```bash
pgrep -u lever65 -x shadow && echo "BUSY — wait" || echo "clear to run"
```
Expected: `clear to run`. If another lever65 agent's sim is live, wait or ask before launching (co-tenancy just adds wall-clock noise to a running sim, but launching a heavy 1200-node run alongside theirs is a courtesy check).

- [ ] **Step 2: Launch the run (nice'd, named, own run dir)**
```bash
cd /home/lever65/monerosim_scale/monerosim
nice -n10 ./run_sim.sh --config test_configs/selfish_phase4/gamma_relay.yaml --name selfish_phase4_relay --analyze
# capture the run_id / owner pid for scoped management:
ls -t archived_runs | head -1
```
Run this in the background (it's long). Track the run via `archived_runs/<run_id>/.owner_pid` — manage ONLY that PID. Check progress via the run's own `monerosim.log` / `shadow_output/*.log` (backgrounded `| tail` may show nothing until exit).

- [ ] **Step 3: Measure realized γ + attacker share**
```bash
RUN=$(ls -t archived_runs | head -1)
python3 scripts/selfish_mining_analysis.py archived_runs/"$RUN"/... 2>&1 | tail -40
```
(Use the same invocation phase-3 used; the analysis already computes attacker share + honest-resolved tie wins = realized γ. No analysis change.)

- [ ] **Step 4: Forensic — did the withheld block actually reach honest daemons?**

Phase-2's forensic found 0/8 tie-blocks reaching honest daemons (stock never relays). With the flag, the attacker's relayed alt-block should now appear in honest daemon logs. Grep honest daemon logs (honest-001/002/003) for the attacker's block hashes / alt-block acceptance around tie heights. Report the count reached (expect > 0 now).

- [ ] **Step 5: Write it up honestly**

In `docs/20260912_selfish_mining_results.md`, add a **Phase 4** section: the realized γ, attacker share vs the Eyal–Sirer γ curve, the forensic (blocks now reaching honest nodes), and the conclusion — whether relay + placement lifts γ above the phase-1/2/3 ≈0. **Report either outcome faithfully**: if relay works but the reactive attacker still can't win first-seen races, that itself is the result (relay necessary, timing still binds). In `docs/SELFISH_MINING.md`, document the `--sim-relay-alt-blocks` flag (what it does, default-off, sim-only, the local-submission-only safety property, config-only wiring).

- [ ] **Step 6: Commit + update memory**
```bash
git add docs/20260912_selfish_mining_results.md docs/SELFISH_MINING.md
git commit -m "exp(selfish): phase-4 result — gamma vs relay (realized gamma = <VALUE>)

<one-line finding>. Relay removes barrier 2 (withheld block now reaches honest
daemons: <N> observed vs phase-2's 0/8). Placement + reaction decide the race."
```
Then update `project_selfish_mining_apparatus` memory + `.claude/HANDOFF.md` with the phase-4 outcome. (Do NOT push/merge — local only until the user says.)

---

## Self-Review

**1. Spec coverage** (checked against `2026-09-13-sim-relay-withheld-blocks-design.md`):
- Spec §Design 1 (patch: flag via 4-touch + gate relaxation) → Task 1 (Steps 2-6). ✓ (Reorg-guard skip in §1 deliberately dropped per the documented ruling — narrowing, empty-block no-op.)
- Spec §Design 2 (wiring, config-only preferred) → Tasks 4-5; the wiring scout confirmed config-only works (monerod-hf symlink resolves; `options_to_args` emits the bare flag), so the substitution fallback is **not needed** — no `user_agents.rs`/`is_native_miner_script` change. ✓
- Spec §Design 3 (phase-4 experiment) → Tasks 5-6. ✓
- Spec §Testing (patch builds/smoke; targeted config-gen test; goldens byte-identical; end-to-end) → Tasks 3, 4, 4, 6. ✓
- Spec §Global constraints, §Risks → this plan's Global Constraints + Task 1 ruling (tx-bearing caveat) + Task 3/6 shared-box pre-flights. ✓

**2. Placeholder scan:** The only intentional fill-ins are the *results* in Task 6's commit message (`<VALUE>`, `<N>`, `<one-line finding>`) — these are empirical outputs of the run, not code placeholders. All code/edits/commands are concrete. ✓

**3. Type/name consistency:** `m_sim_relay_alt_blocks` (member, Edit D) matches its use in Edit C (get_arg assignment) and Edit E (gate). `arg_sim_relay_alt_blocks` (descriptor, Edit A) matches add_arg (Edit B) + get_arg (Edit C). Field `m_verifivation_failed` / `m_already_exists` match `verification_context.h` verbatim (typo preserved). Library APIs `config_loader::load_config` / `orchestrator::generate_agent_shadow_config` / `config.general.shared_dir` match `tests/orchestrator_selfish.rs`. Flag string `sim-relay-alt-blocks` / rendered `--sim-relay-alt-blocks` consistent across Tasks 1/4/5. ✓

**Dispatch note for the controller:** Tasks 1, 3, 6 are **main-loop / not delegated** (security-sensitive C++, shared-resource build, long run + judgment). Tasks 2, 4, 5 are delegatable to `mechanic`/`builder` (scoped mechanical edits + a test from a template). Task 3 gates Task 6; Task 1 gates Tasks 2-3.
