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

/// Sleep between hash attempts for a miner declaring `hashrate_hs` hashes per
/// second: round(1000 / H), floored at 1 ms. Contract: `hashrate_hs` must be
/// in `1..=1000` (enforced by `validate_mining_config` in native mode) —
/// above 1000 this floor silently caps the miner at 1000 h/s while the
/// logged `D_eq` still reports the larger declared value.
pub fn hash_interval_ms(hashrate_hs: u32) -> u64 {
    if hashrate_hs == 0 {
        return 1000;
    }
    let ms = (1000.0_f64 / hashrate_hs as f64).round() as u64;
    ms.max(1)
}

/// True if `script` is one of the native-mining agent scripts that need the
/// miner wallet-hybrid path in user_agents.rs (autonomous or selfish miner).
/// selfish_bridge is intentionally excluded — it is a relay, not a miner.
pub fn is_native_miner_script(script: &str) -> bool {
    script.contains("autonomous_miner") || script.contains("selfish_miner")
}

/// Difficulty monerod's LWMA converges to when the network declares
/// `total_hashrate_hs` hashes per second and the target is 120 s.
pub fn equilibrium_difficulty(total_hashrate_hs: u64) -> u64 {
    DIFFICULTY_TARGET_SECS * total_hashrate_hs
}

/// True if any raw daemon arg sets --sim-hash-interval-ms OR
/// --sim-rx-full-dataset (legacy `daemon_args` or per-phase `daemon_N_args`).
pub fn args_mention_sim_knob(args: Option<&Vec<String>>) -> bool {
    args.map(|v| {
        v.iter().any(|a| {
            a.contains(&format!("--{}", SIM_HASH_INTERVAL_KNOB))
                || a.contains(&format!("--{}", SIM_RX_FULL_DATASET_KNOB))
        })
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
        let u = vec!["--sim-rx-full-dataset".to_string()];
        assert!(args_mention_sim_knob(Some(&u)));
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

    #[test]
    fn native_miner_scripts_recognised() {
        assert!(is_native_miner_script("agents.autonomous_miner"));
        assert!(is_native_miner_script("agents.selfish_miner"));
        assert!(!is_native_miner_script("agents.regular_user"));
        assert!(!is_native_miner_script("agents.selfish_bridge"));
    }
}
