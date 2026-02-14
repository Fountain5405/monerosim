//! Configuration generator for Monero network simulations in Shadow.
//!
//! Takes a YAML config and produces Shadow-compatible YAML, wrapper scripts,
//! and Python agent configurations.
//!
//! ## Modules
//!
//! - `config_v2` / `config_loader`: YAML config parsing and loading
//! - `orchestrator`: High-level config generation coordination
//! - `shadow`: Shadow YAML data structures
//! - `ip`: IP address allocation with geographic distribution
//! - `topology`: Network topology (switch, GML) and peer connections
//! - `agent`: Agent config generation (miners, users, scripts)
//! - `process`: Process/wrapper script generation
//! - `analysis`: Post-simulation log analysis
//! - `utils`: Duration parsing, validation, seed extraction

/// Shared directory for inter-agent communication and registry files.
pub const SHARED_DIR: &str = "/tmp/monerosim_shared";

/// Shadow simulation epoch: 2000-01-01 00:00:00 UTC as Unix timestamp.
/// Shadow's simulated clock starts from this point; subtract it from
/// `time.time()` (Python) or log timestamps to get simulation-relative seconds.
pub const SHADOW_EPOCH: f64 = 946_684_800.0;

/// Monero P2P port (mainnet/regtest default).
pub const MONERO_P2P_PORT: u16 = 18080;
/// Monero daemon RPC port (mainnet/regtest default).
pub const MONERO_RPC_PORT: u16 = 18081;
/// Monero wallet RPC port (mainnet/regtest default).
pub const MONERO_WALLET_RPC_PORT: u16 = 18082;

/// Default host bandwidth in bits/sec (1 Gbit/s).
pub const DEFAULT_BANDWIDTH_BPS: &str = "1000000000";
/// glibc malloc mmap threshold for memory-constrained simulation hosts.
pub const MALLOC_THRESHOLD: &str = "131072";
/// Maximum inbound connections per IP for monerod.
pub const MAX_CONNECTIONS_PER_IP: &str = "20";
/// IP offset for miner-distributor agents to avoid collision with user agents.
pub const DISTRIBUTOR_IP_OFFSET: usize = 100;
/// IP offset for pure-script agents.
pub const SCRIPT_IP_OFFSET: usize = 200;
/// Delay (seconds) between daemon start and wallet start.
pub const WALLET_STARTUP_DELAY_SECS: u64 = 2;
/// Delay (seconds) between wallet start and agent script start.
pub const AGENT_STARTUP_DELAY_SECS: u64 = 3;
/// Max chars to preview when logging registry JSON.
pub const REGISTRY_PREVIEW_CHARS: usize = 500;
/// Monero coinbase maturity: 60 blocks at 120s each.
pub const BLOCK_MATURITY_SECONDS: u64 = 7200;

pub mod config_v2;
pub mod config_loader;
pub mod gml_parser;
pub mod shadow;
pub mod ip;
pub mod topology;
pub mod agent;
pub mod process;
pub mod utils;
pub mod orchestrator;
pub mod analysis;