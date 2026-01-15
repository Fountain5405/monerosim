# Monerosim Code Refactoring Plan

**Created**: 2026-01-15
**Branch**: `code-cleanup-analysis`
**Baseline Config**: `20260112_config.yaml` (3m 10s wall time, 157 blocks, 89 txs, SUCCESS)

## Baseline Metrics (for comparison after changes)

```
SUCCESS criteria analysis:
- Blocks Created: 157 blocks mined
- Blocks Propagated: 25 user nodes received blocks
- Transactions Created: 89 unique
- Transactions in Blocks: 89/89 (100%)
- Wall clock time: 3m 10s

Final simulation state:
- Height: 133-143 (avg 137)
- Miners: 5 active, 130 total blocks generated
- Connections: 713
- Difficulty: 2
```

Determinism fingerprint saved to: `docs/refactoring/determinism_fingerprint_20260115_203044.json`

---

## Priority 1: Remove Legacy UserAgentConfig (HIGHEST IMPACT)

### Analysis

The codebase has TWO nearly-identical config types:

| Type | Location | Status | Used By |
|------|----------|--------|---------|
| `AgentConfig` | config_v2.rs:110-221 | **ACTIVE** | Main code path via `AgentDefinitions` |
| `UserAgentConfig` | config_v2.rs:551-595 | **LEGACY** | Only validation.rs (tests & validators) |

**Key differences:**
- `AgentConfig`: Uses `#[derive(Deserialize)]`, has unified `script` field
- `UserAgentConfig`: Custom deserializer for flat phase fields (`daemon_0`, `daemon_0_args`), separate `user_script`/`mining_script` fields

**Finding**: The flat phase fields that `UserAgentConfig` specifically parses (`daemon_0`, `daemon_1`, etc.) are **NOT USED** in any config files. This entire subsystem is dead code.

### Files to Modify

1. **src/utils/validation.rs**
   - Lines 7, 150, 156, 174, 252: Import and use `AgentConfig` instead of `UserAgentConfig`
   - All test functions (lines 528-969): Update to use `AgentConfig`
   - May need to update field names (`user_script` → `script`)

2. **src/config_v2.rs**
   - Remove `UserAgentConfig` struct (lines 550-595) ~45 lines
   - Remove `UserAgentConfigRaw` struct (lines 597-625) ~28 lines
   - Remove custom `Deserialize` impl (lines 627-653) ~26 lines
   - Keep or refactor `parse_phase_fields` (see Priority 2)

### Risk Level: MEDIUM
The validation code uses the old schema. Need to verify all validation tests still pass after updating to `AgentConfig`.

---

## Priority 2: Deduplicate Phase Parsing (HIGH IMPACT)

### Analysis

`parse_phase_fields()` at config_v2.rs:656-809 has **extreme** code duplication:

```rust
// Lines 658-737: daemon phase parsing (~80 lines)
let daemon_re = Regex::new(r"^daemon_(\d+)$").unwrap();
let daemon_args_re = Regex::new(r"^daemon_(\d+)_args$").unwrap();
// ... identical pattern for 6 regex matchers
// ... identical parsing logic

// Lines 740-809: wallet phase parsing (~70 lines)
// EXACT SAME STRUCTURE, just s/daemon/wallet/
```

### Proposed Fix

Create a generic function:

```rust
fn parse_process_phases<T: ProcessPhase>(
    extra: &BTreeMap<String, serde_yaml::Value>,
    prefix: &str,  // "daemon" or "wallet"
) -> Option<BTreeMap<u32, T>> {
    // Single implementation for both daemon and wallet phases
}
```

**However**: If we remove `UserAgentConfig` (Priority 1), this function may become dead code since `AgentConfig` uses `#[derive(Deserialize)]` and expects structured YAML, not flat fields.

### Decision Point
- If Priority 1 removes `UserAgentConfig`, this function can be deleted entirely
- If we want to support flat phase fields in `AgentConfig`, we'd need to add a custom deserializer there too

**Recommendation**: Complete Priority 1 first. If flat phases aren't needed, delete `parse_phase_fields` entirely.

---

## Priority 3: Deduplicate Validation Functions (MEDIUM IMPACT)

### Analysis

`validation.rs` has two nearly-identical functions:

| Function | Lines | Purpose |
|----------|-------|---------|
| `validate_daemon_phases()` | 962-1052 | Validate daemon phase configs |
| `validate_wallet_phases()` | 1055-1145 | Validate wallet phase configs |

**93% identical code** - only field names differ.

### Proposed Fix

```rust
fn validate_phases<T: PhaseConfig>(
    phases: &BTreeMap<u32, T>,
    phase_type: &str,  // "daemon" or "wallet"
    agent_id: &str,
) -> Result<(), String> {
    // Single implementation with trait bounds
}

trait PhaseConfig {
    fn get_binary(&self) -> Option<&str>;
    fn get_args(&self) -> Option<&Vec<String>>;
    fn get_start(&self) -> Option<&str>;
    fn get_stop(&self) -> Option<&str>;
}
```

### Savings: ~90 lines of duplicated code

---

## Priority 4: Consolidate Function Parameters (MEDIUM IMPACT)

### Analysis

`process_user_agents()` in user_agents.rs has **17+ parameters**:

```rust
pub fn process_user_agents(
    agents: &AgentDefinitions,
    hosts: &mut BTreeMap<String, ShadowHost>,
    seed_agents: &mut Vec<String>,
    _effective_seed_nodes: &[String],  // UNUSED!
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    monerod_path: &str,
    wallet_path: &str,
    environment: &BTreeMap<String, String>,
    monero_environment: &BTreeMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    peer_mode: &PeerMode,
    topology: Option<&Topology>,
    enable_dns_server: bool,
    // ...
)
```

### Proposed Fix

```rust
struct ProcessingContext<'a> {
    pub paths: &'a PathConfig,
    pub ip_manager: &'a mut IpManager,
    pub topology: &'a TopologyConfig,
    pub environment: &'a EnvironmentConfig,
}

pub fn process_user_agents(
    agents: &AgentDefinitions,
    hosts: &mut BTreeMap<String, ShadowHost>,
    ctx: &mut ProcessingContext,
) -> Result<()>
```

### Risk Level: LOW
This is a refactoring that doesn't change behavior, just improves readability.

---

## Priority 5: Remove Dead Code (LOW IMPACT)

### Identified Dead Code

1. **`_effective_seed_nodes` parameter** (user_agents.rs)
   - Unused, prefixed with `_`

2. **`Graph` and `Node` legacy structs** (gml_parser.rs:104-113)
   - Comment says "for backward compatibility"
   - Check if `parse_gml()` is actually called anywhere

3. **`validate_simulation_seed()` function** (validation.rs:346-351)
   - Does nothing (u64 is always valid)
   - Has docblock explaining why it does nothing

4. **Various unused imports** scattered throughout

### Verification Required
Run `cargo build --release` and check for unused warnings before removing.

---

## Testing Strategy

After each priority is completed:

1. **Build check**: `cargo build --release`
2. **Run tests**: `cargo test`
3. **Generate config**: `./target/release/monerosim --config test_configs/20260112_config.yaml --output shadow_output_test/`
4. **Compare output**: `diff shadow_output/shadow_agents.yaml shadow_output_test/shadow_agents.yaml`
5. **Full simulation** (if config generation differs):
   ```bash
   shadow shadow_output_test/shadow_agents.yaml
   python3 scripts/analyze_success_criteria.py --log-dir shadow.data/hosts
   ```

---

## Execution Order

1. [x] **Priority 1**: Remove `UserAgentConfig` ✅ COMPLETED 2026-01-15
   - Removed `UserAgentConfig` struct (~45 lines)
   - Removed `UserAgentConfigRaw` struct (~28 lines)
   - Removed `impl UserAgentConfig` (~322 lines of duplicate methods)
   - Moved `parse_phase_fields` into `AgentConfig`'s custom deserializer
   - Updated validation functions to use `AgentConfig` directly
   - Rewrote all validation tests
   - Integrated validation into `config_loader.rs`
2. [x] **Priority 2**: N/A - phase parsing retained in `AgentConfig`
3. [x] **Priority 3**: Deduplicate validation functions (done in P1)
4. [x] **Priority 4**: SKIPPED - would add complexity without removing code
5. [x] **Priority 5**: Clean up dead code ✅ COMPLETED 2026-01-15
   - Removed unused `_effective_seed_nodes` parameter from `process_user_agents`
   - Fixed unused variable warnings with `_` prefix

---

## Notes for Future Context

If you're resuming this work after context loss:

1. We're on branch `code-cleanup-analysis`
2. Baseline data is in `docs/refactoring/`
3. Test config is `test_configs/20260112_config.yaml`
4. `UserAgentConfig` has been REMOVED - phase parsing is now built into `AgentConfig`
5. Flat phase fields (`daemon_0`, `daemon_1`) ARE supported via custom deserializer on `AgentConfig`
6. Validation functions now work with `BTreeMap<String, AgentConfig>` and are called in config_loader.rs

---

## Estimated Savings

| Priority | Lines Removed | Lines Added | Net Change |
|----------|---------------|-------------|------------|
| P1 | ~300 | ~50 | -250 |
| P2 | ~150 | 0 or ~30 | -120 to -150 |
| P3 | ~90 | ~40 | -50 |
| P4 | ~0 | ~30 | +30 (but cleaner) |
| P5 | ~30 | 0 | -30 |
| **Total** | **~570** | **~150** | **~-400 lines** |
