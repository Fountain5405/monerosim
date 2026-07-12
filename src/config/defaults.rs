//! Default-value functions for serde defaults on configuration fields.

pub(super) fn default_simulation_seed() -> u64 {
    12345
}

pub(super) fn default_parallelism() -> u32 {
    0 // Auto-detect CPU cores for best performance
}

pub(super) fn default_difficulty_cache_ttl() -> u32 {
    30 // 30 seconds - difficulty doesn't change frequently in simulation
}

pub(super) fn default_shadow_log_level() -> String {
    "info".to_string() // Reduced from "trace" to lower I/O overhead
}

pub(super) fn default_shared_dir() -> String {
    crate::shared_dir()
}

pub(super) fn default_daemon_data_dir() -> String {
    crate::default_daemon_data_dir()
}

pub(super) fn default_model_unblocked_syscall_latency() -> bool {
    true
}
