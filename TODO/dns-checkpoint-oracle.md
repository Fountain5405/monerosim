# TODO: DNS Checkpoint Oracle for Malicious Fork Testing

## Goal

Enable testing whether Monero's `--enforce-dns-checkpointing` protects against malicious forks by having a simulated checkpoint oracle that publishes block hashes via DNS TXT records during the simulation.

## Background

Monero queries 4 `checkpoints.moneropulse.*` domains for TXT records containing `HEIGHT:HASH` pairs. When `--enforce-dns-checkpointing` is enabled, the node rolls back if its chain conflicts with a DNS checkpoint. This requires:

- DNSSEC validation (simulated — `secure=1` in `unbound_interpose.c`, done)
- Majority agreement (3/4 domains must return the same records — our DNS server returns the same data for all 4, so this is satisfied)
- At least 2 valid DNSSEC responses (satisfied since all 4 return `secure=1`)

Monero refreshes DNS checkpoints every **3600 seconds (1 hour)** of simulated time.

## Design: Honest Oracle

One designated node is the "oracle" — it periodically reads its own blockchain state and publishes checkpoints to the DNS server. In a malicious fork scenario, this oracle represents the honest network's view of the canonical chain.

### Components

**1. Checkpoint publisher agent** (new agent or extension of simulation-monitor)

- Configured with a reference daemon RPC endpoint (the oracle node)
- Periodically (every N blocks or M minutes of sim time):
  - Queries `get_block_header_by_height(h)` for checkpoint heights
  - Writes `{height: block_hash}` entries to `/tmp/monerosim_shared/dns_checkpoints.json`
- Checkpoint heights could be:
  - Every N blocks (e.g., every 100 blocks)
  - At specific configured heights
  - At the current height minus some confirmation depth (e.g., current_height - 10)

**2. DNS server** (already implemented)

- Already reads `dns_checkpoints.json` and serves TXT records
- Already handles the `checkpoints.moneropulse.*` domains
- No changes needed

**3. Monerod configuration**

- `--enforce-dns-checkpointing` needs to be passed to nodes that should be protected
- Could be per-agent: honest nodes get it, attacker nodes don't
- The orchestrator already omits `--disable-dns-checkpoints` when DNS is enabled

### Scenario Configuration

Example scenario config for a fork attack test:

```yaml
general:
  enable_dns_server: true
  dns_checkpoint_oracle: miner-001  # Which node is the oracle
  dns_checkpoint_interval: 100      # Checkpoint every 100 blocks
  dns_checkpoint_depth: 10          # Checkpoint blocks that are 10-deep

agents:
  - id: miner-001
    role: miner
    hashrate: 60
    daemon_args:
      enforce-dns-checkpointing: true

  - id: attacker-001
    role: miner
    hashrate: 40
    daemon_args:
      enforce-dns-checkpointing: false  # Attacker ignores checkpoints
```

### Attack Scenarios to Test

1. **51% attack with checkpoints**: Attacker has majority hashrate but honest nodes have DNS checkpoints. Can the attacker reorg past a checkpoint?

2. **Minority attack with checkpoints**: Attacker has <50% hashrate and tries to create a longer fork. Do checkpointed nodes reject it?

3. **Checkpoint timing**: What happens if the attacker forks before a checkpoint is published vs. after?

4. **Late-joining nodes**: A new node bootstraps after a fork — does it follow the checkpointed chain or the attacker's chain?

## Implementation Steps

### Phase 1: Checkpoint publisher

- [ ] Create `agents/checkpoint_publisher.py` (or add to simulation-monitor)
- [ ] Accept config: oracle daemon RPC endpoint, checkpoint interval, confirmation depth
- [ ] Periodically query block headers and write `dns_checkpoints.json`
- [ ] Use file locking (consistent with existing shared state pattern)

### Phase 2: Orchestrator integration

- [ ] Add `dns_checkpoint_oracle` config option
- [ ] Add `dns_checkpoint_interval` and `dns_checkpoint_depth` options
- [ ] Pass `--enforce-dns-checkpointing` to appropriate agents
- [ ] Launch checkpoint publisher agent with the oracle node's RPC endpoint

### Phase 3: Test scenarios

- [ ] Create scenario configs for the attack scenarios above
- [ ] Add success criteria to `analyze_success_criteria.py` for checkpoint enforcement
- [ ] Verify honest nodes reject the attacker's fork
- [ ] Verify honest nodes stay on the checkpointed chain

## Prerequisites (Done)

- [x] DNS resolution works in Shadow (libunbound interposer)
- [x] DNS server serves TXT records for checkpoint domains
- [x] DNSSEC simulation (`secure=1` in ub_result)
- [x] DNS server reads from `dns_checkpoints.json`
- [x] Dual-protocol DNS server (TCP + UDP)

## Relevant Files

### Monerosim
- `agents/dns_server.py` — Already serves checkpoint TXT records
- `agents/simulation_monitor.py` — Has RPC access, could be extended
- `src/agent/user_agents.rs` — Controls `--disable-dns-checkpoints` flag

### Monero (read-only reference)
- `src/checkpoints/checkpoints.cpp:312` — `load_checkpoints_from_dns()` parses TXT records
- `src/common/dns_utils.cpp:478` — `load_txt_records_from_dns()` DNSSEC + majority voting
- `src/cryptonote_core/blockchain.cpp:4548` — `check_against_checkpoints()` enforces/warns
- `src/cryptonote_core/cryptonote_core.cpp:272` — Refresh interval (3600s DNS, 600s JSON)

### Shadow
- `src/lib/preload-libc/unbound_interpose.c` — DNSSEC simulation (secure=1)
