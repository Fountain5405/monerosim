//! Tail-emission helpers (docs/TAIL_EMISSION.md): the switch height and the
//! `--help` capability probe for patches/monero-sim-tail-emission.patch.

use std::collections::HashMap;

use crate::config::{EmissionConfig, EmissionHeight};

/// monerod option added by patches/monero-sim-tail-emission.patch: from this
/// block height on, the base reward is the tail subsidy (0.6 XMR).
/// Consensus-relevant — every daemon in a run must get the same value.
pub const SIM_TAIL_EMISSION_KNOB: &str = "sim-tail-emission-height";

/// Base reward of a fresh chain's first blocks, in whole XMR
/// ((2^64 - 1) >> 19 atomic units ≈ 35.18 XMR). It decays by well under 1%
/// over the few hundred blocks `auto` covers.
const FRESH_CHAIN_REWARD_XMR: f64 = 35.18;
/// What miner_distributor pays each user: md_out_per_tx (2) x
/// md_output_amount (5.0 XMR); agents/miner_distributor/agent.py.
const FUNDING_PER_USER_XMR: f64 = 10.0;
/// Headroom for fees, coins stranded in non-distributor-selected wallets and
/// change locked in flight.
const FUNDING_MARGIN: f64 = 1.5;
/// Never switch before the first coinbases could have matured (60 blocks).
const MIN_AUTO_HEIGHT: u64 = 60;

/// `auto` switch height: enough full-emission blocks to mint every user's
/// funding (with margin). Coins minted before the switch stay spendable after
/// it, so only the total supply matters, not when funding happens.
pub fn auto_tail_height(funded_users: usize) -> u64 {
    let xmr = funded_users as f64 * FUNDING_PER_USER_XMR * FUNDING_MARGIN;
    ((xmr / FRESH_CHAIN_REWARD_XMR).ceil() as u64).max(MIN_AUTO_HEIGHT)
}

/// The tail switch height for this run, or None for stock emission.
/// `chain_start` = tip height of a grafted chain snapshot (0 = fresh chain).
/// The snapshot's coinbases belong to the generator run's wallets, so users
/// are funded only from blocks mined live: `auto` counts from the tip. A
/// literal `from_height` stays absolute.
pub fn resolve_tail_height(
    cfg: &EmissionConfig,
    funded_users: usize,
    chain_start: u64,
) -> Result<Option<u64>, String> {
    if !cfg.is_tail() {
        if cfg.from_height.is_some() {
            return Err("general.emission.from_height is set but mode is not 'tail'".into());
        }
        return Ok(None);
    }
    match &cfg.from_height {
        None => Ok(Some(chain_start + auto_tail_height(funded_users))),
        Some(EmissionHeight::Height(h)) => Ok(Some(*h)),
        Some(EmissionHeight::Keyword(k)) if k == "auto" => {
            Ok(Some(chain_start + auto_tail_height(funded_users)))
        }
        Some(EmissionHeight::Keyword(k)) => Err(format!(
            "general.emission.from_height must be a block height or 'auto', got '{}'",
            k
        )),
    }
}

/// True if any raw daemon arg sets --sim-tail-emission-height.
pub fn args_mention_tail_knob(args: Option<&Vec<String>>) -> bool {
    args.map(|v| v.iter().any(|a| a.contains(&format!("--{}", SIM_TAIL_EMISSION_KNOB))))
        .unwrap_or(false)
}

/// Capability probe: does `binary --help` list --sim-tail-emission-height?
/// Cached per path. MONEROSIM_SKIP_SIM_BINARY_CHECK=1 forces `true`.
pub fn binary_supports_tail_emission(path: &str, cache: &mut HashMap<String, bool>) -> bool {
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
            String::from_utf8_lossy(&text).contains(SIM_TAIL_EMISSION_KNOB)
        })
        .unwrap_or(false);
    cache.insert(path.to_string(), supported);
    supported
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::EmissionMode;

    fn tail(h: Option<EmissionHeight>) -> EmissionConfig {
        EmissionConfig { mode: EmissionMode::Tail, from_height: h }
    }

    #[test]
    fn auto_height_covers_funding() {
        // 600 users x 10 XMR x 1.5 / 35.18 = 255.8 -> 256
        assert_eq!(auto_tail_height(600), 256);
        assert_eq!(auto_tail_height(0), MIN_AUTO_HEIGHT);
        assert_eq!(auto_tail_height(10), MIN_AUTO_HEIGHT);
    }

    #[test]
    fn resolve() {
        assert_eq!(resolve_tail_height(&EmissionConfig::default(), 600, 0), Ok(None));
        assert_eq!(resolve_tail_height(&tail(None), 600, 0), Ok(Some(256)));
        assert_eq!(
            resolve_tail_height(&tail(Some(EmissionHeight::Keyword("auto".into()))), 600, 0),
            Ok(Some(256))
        );
        // grafted snapshot: auto counts from its tip, a literal height stays absolute
        assert_eq!(resolve_tail_height(&tail(None), 600, 1535), Ok(Some(1791)));
        assert_eq!(
            resolve_tail_height(&tail(Some(EmissionHeight::Height(100))), 600, 1535),
            Ok(Some(100))
        );
        assert_eq!(resolve_tail_height(&tail(Some(EmissionHeight::Height(0))), 600, 0), Ok(Some(0)));
        assert!(resolve_tail_height(&tail(Some(EmissionHeight::Keyword("soon".into()))), 1, 0).is_err());
        let stray = EmissionConfig { mode: EmissionMode::Stock, from_height: Some(EmissionHeight::Height(5)) };
        assert!(resolve_tail_height(&stray, 1, 0).is_err());
    }

    #[test]
    fn yaml_forms() {
        let c: EmissionConfig = serde_yaml::from_str("mode: tail\nfrom_height: 300").unwrap();
        assert_eq!(c.from_height, Some(EmissionHeight::Height(300)));
        let c: EmissionConfig = serde_yaml::from_str("mode: tail\nfrom_height: auto").unwrap();
        assert_eq!(c.from_height, Some(EmissionHeight::Keyword("auto".into())));
        let c: EmissionConfig = serde_yaml::from_str("mode: tail").unwrap();
        assert!(c.is_tail() && c.from_height.is_none());
    }
}
