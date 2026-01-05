# Multi-Binary Support Specification

## Overview

This feature enables monerosim to run different versions of Monero binaries (monerod, monero-wallet-rpc) within the same simulation. Primary use cases:

1. **Fork/compatibility testing**: New monerod version joining a network of old versions
2. **Upgrade simulation**: Nodes upgrading mid-simulation, including database migration scenarios
3. **Mixed version networks**: Testing how different client versions interact

## Design Principles

- **Flat config**: No nested schemas or type-switching magic. Explicit and readable.
- **Self-contained**: monerosim.yaml files contain full paths, no external references.
- **Validate early**: Check binary paths exist before launching Shadow.

## Configuration Schema

### Simple Case (Single Binary)

For agents running one binary for the entire simulation:

```yaml
agents:
  user_agents:
    - daemon: monerod                          # Shorthand -> ~/.monerosim/bin/monerod
      daemon_args: ["--prune-blockchain"]
      daemon_env:
        MONERO_LOG: "1"
      wallet: ~/.monerosim/bin/wallet-v18      # Explicit path
      wallet_args: ["--log-level=2"]
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `daemon` | string | Path to monerod binary, or shorthand name |
| `daemon_args` | string[] | Additional CLI arguments (appended to generated args) |
| `daemon_env` | map | Environment variables for the daemon process |
| `wallet` | string | Path to wallet-rpc binary, or shorthand name |
| `wallet_args` | string[] | Additional CLI arguments |
| `wallet_env` | map | Environment variables for the wallet process |

### Upgrade Case (Multiple Phases)

For agents that switch binaries during simulation:

```yaml
agents:
  user_agents:
    - daemon_0: ~/.monerosim/bin/monerod-v18
      daemon_0_args: ["--prune-blockchain"]
      daemon_0_stop: "1h"

      daemon_1: ~/.monerosim/bin/monerod-v19
      daemon_1_start: "1h 30s"    # 30s gap for clean shutdown
      daemon_1_args: ["--log-level=2"]

      wallet: monero-wallet-rpc
```

**Phase fields (N = 0, 1, 2, ...):**
| Field | Type | Description |
|-------|------|-------------|
| `daemon_N` | string | Path to monerod binary for phase N |
| `daemon_N_args` | string[] | CLI arguments for phase N |
| `daemon_N_env` | map | Environment variables for phase N |
| `daemon_N_start` | string | Start time (default: "0s" for phase 0) |
| `daemon_N_stop` | string | Stop time (default: simulation end) |

Same pattern applies for wallet: `wallet_N`, `wallet_N_args`, `wallet_N_start`, etc.

### Path Resolution

1. If path contains `/` or `~`: use as-is (with `~` expansion)
2. Otherwise: expand shorthand to `~/.monerosim/bin/{name}`

Examples:
- `monerod` -> `~/.monerosim/bin/monerod`
- `monerod-v18` -> `~/.monerosim/bin/monerod-v18`
- `~/.local/bin/monerod` -> `~/.local/bin/monerod`
- `/opt/monero/monerod` -> `/opt/monero/monerod`

## Validation Rules

### Startup Validation

Before launching Shadow, monerosim validates:

1. **Binary exists**: Each resolved path points to an existing file
2. **Binary executable**: File has execute permission
3. **No mixed patterns**: Cannot use both `daemon` and `daemon_0` on same agent

### Phase Validation

For multi-phase configs:

1. **Sequential numbering**: Phases must be 0, 1, 2, ... (gaps in numbering are errors)
2. **No overlap**: `daemon_N_stop` must be < `daemon_N+1_start` (strict less-than)
3. **Gap required**: Time between `daemon_N_stop` and `daemon_N+1_start` allows for clean shutdown (database flush, port release, lock cleanup). Recommend 30-60s minimum.
4. **Phase 0 defaults**: If `daemon_0_start` not specified, defaults to "0s"
5. **Final phase**: If `daemon_N_stop` not specified, runs until simulation end

## Shadow Process Generation

### Simple Case

```yaml
# monerosim.yaml
daemon: ~/.monerosim/bin/monerod
daemon_args: ["--prune-blockchain"]
```

Generates Shadow process:
```yaml
processes:
  - path: ~/.monerosim/bin/monerod
    args: "--regtest --p2p-bind-port=18080 ... --prune-blockchain"
    start_time: "50s"
    environment: { ... }
```

### Upgrade Case

```yaml
# monerosim.yaml
daemon_0: ~/.monerosim/bin/monerod-v18
daemon_0_stop: "1h"
daemon_1: ~/.monerosim/bin/monerod-v19
daemon_1_start: "1h 30s"   # 30s gap for clean shutdown
```

Generates Shadow processes:
```yaml
processes:
  - path: ~/.monerosim/bin/monerod-v18
    args: "--regtest --p2p-bind-port=18080 ..."
    start_time: "50s"
    shutdown_time: "1h"
    expected_final_state: { signaled: SIGTERM }
    environment: { ... }
  - path: ~/.monerosim/bin/monerod-v19
    args: "--regtest --p2p-bind-port=18080 ..."
    start_time: "1h 30s"
    environment: { ... }
```

## Implementation Changes

### 1. Shadow Types (`src/shadow/types.rs`)

Add to `ShadowProcess`:
```rust
pub struct ShadowProcess {
    pub path: String,
    pub args: String,
    pub environment: BTreeMap<String, String>,
    pub start_time: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub shutdown_time: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expected_final_state: Option<ExpectedFinalState>,
}

pub enum ExpectedFinalState {
    Exited(i32),
    Signaled(String),
    Running,
}
```

### 2. Config V2 (`src/config_v2.rs`)

Update `UserAgentConfig`:
```rust
pub struct UserAgentConfig {
    // Simple case
    pub daemon: Option<String>,
    pub daemon_args: Option<Vec<String>>,
    pub daemon_env: Option<BTreeMap<String, String>>,

    // Phase case - stored in a BTreeMap keyed by phase number
    pub daemon_phases: Option<BTreeMap<u32, DaemonPhase>>,

    // Same for wallet...
    pub wallet: Option<String>,
    pub wallet_args: Option<Vec<String>>,
    pub wallet_env: Option<BTreeMap<String, String>>,
    pub wallet_phases: Option<BTreeMap<u32, WalletPhase>>,

    // Existing fields...
}

pub struct DaemonPhase {
    pub path: String,
    pub args: Option<Vec<String>>,
    pub env: Option<BTreeMap<String, String>>,
    pub start: Option<String>,
    pub stop: Option<String>,
}
```

Note: The flat YAML fields (`daemon_0`, `daemon_0_args`, etc.) will need custom deserialization to populate `daemon_phases`.

### 3. Binary Resolution (`src/utils/`)

New module for path resolution and validation:
```rust
pub fn resolve_binary_path(name: &str) -> PathBuf;
pub fn validate_binary(path: &Path) -> Result<(), BinaryError>;
pub fn validate_agent_binaries(config: &Config) -> Result<(), Vec<BinaryError>>;
```

### 4. Orchestrator (`src/orchestrator.rs`)

Update process generation to:
- Use resolved paths instead of hardcoded `$HOME/.monerosim/bin/...`
- Handle phase-based configs
- Set `shutdown_time` and `expected_final_state` for upgrade scenarios

### 5. Wallet Process (`src/process/wallet.rs`)

Update `add_wallet_process` and `add_remote_wallet_process` to:
- Accept path parameter instead of hardcoding
- Accept optional args and env parameters

## Migration Scenario Example

Testing v18 -> v19 upgrade with database migration:

```yaml
general:
  stop_time: "4h"

agents:
  user_agents:
    # Miners that upgrade at 1h mark
    - daemon_0: ~/.monerosim/bin/monerod-v18
      daemon_0_stop: "1h"
      daemon_1: ~/.monerosim/bin/monerod-v19
      daemon_1_start: "1h 30s"    # 30s for clean shutdown
      wallet: monero-wallet-rpc
      mining_script: agents.autonomous_miner
      attributes:
        is_miner: "true"
        hashrate: "20"

    # Nodes that stay on v18 (control group)
    - daemon: ~/.monerosim/bin/monerod-v18
      wallet: monero-wallet-rpc
      user_script: agents.regular_user
```

What this tests:
1. v18 nodes build blockchain for 1 hour
2. At 1h, some nodes receive SIGTERM, begin clean shutdown
3. At 1h 30s, v19 starts on those nodes, reads v18 database
4. v19 performs migration (in simulated time), catches up with network
5. Mixed v18/v19 network operates for remaining ~2.5 hours

## Future Considerations (Out of Scope)

- **Global config file**: `~/.monerosim/config` with default paths and aliases
- **Binary version detection**: Auto-detect version from binary
- **Configurator integration**: High-level DSL that expands to this format
- **Staggered upgrades**: Helper syntax for "upgrade 10 nodes per hour"

## Status

Branch: `multi_bin`
Status: Specification complete, ready for implementation
