use clap::Parser;
use color_eyre::eyre::WrapErr;
use color_eyre::Result;
use env_logger::Env;
use log::{info, warn};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

// Use modules from the library instead of redeclaring them
use monerosim::orchestrator::generate_agent_shadow_config;
use monerosim::config_loader;

/// Recursively fix permissions on a directory tree to allow deletion.
/// This handles cases where monero-wallet-rpc creates directories with
/// restrictive permissions (d---------) that prevent normal rm -rf.
fn fix_permissions_recursive(path: &Path) -> std::io::Result<()> {
    if path.is_dir() {
        // First, ensure we can read and traverse this directory
        let mut perms = fs::metadata(path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(path, perms)?;

        // Then recursively fix children
        for entry in fs::read_dir(path)? {
            let entry = entry?;
            fix_permissions_recursive(&entry.path())?;
        }
    }
    Ok(())
}

/// Remove a directory tree, first fixing permissions if needed.
fn remove_dir_with_permissions(path: &Path) -> std::io::Result<()> {
    if path.exists() {
        // Try normal removal first
        if fs::remove_dir_all(path).is_err() {
            // If it fails, fix permissions and try again
            fix_permissions_recursive(path)?;
            fs::remove_dir_all(path)?;
        }
    }
    Ok(())
}

/// Configuration utility for Monero network simulations in Shadow
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Path to the simulation configuration YAML file
    #[arg(short, long)]
    config: PathBuf,
    
    /// Output directory for Shadow configuration and simulation files
    #[arg(short, long, default_value = "shadow_output")]
    output: PathBuf,

    /// Fraction of non-seed nodes that are reachable (advertise their P2P
    /// port), in [0.0, 1.0]. 1.0 = all reachable (default / perfect network);
    /// lower = mainnet-like NAT majority, with the complement getting
    /// --hide-my-port. Overrides `general.reachable_fraction` from the config.
    /// Seeds and miners are always reachable regardless.
    #[arg(long)]
    reachable: Option<f64>,

    /// Enable/override peer churn: mean ONLINE session length (e.g. "2h").
    /// If the config has no `[general.churn]`, passing this enables churn
    /// with sensible defaults (downtime 30m, all eligible relays + users).
    /// Overrides
    /// `general.churn.mean_session`. See --churn-downtime / --churn-max-session.
    #[arg(long)]
    churn_session: Option<String>,

    /// Mean OFFLINE gap between churn sessions (e.g. "30m"). See --churn-session.
    #[arg(long)]
    churn_downtime: Option<String>,

    /// Hard ceiling on any single churn session (e.g. "6h"); omit to let the
    /// exponential tail run free. See --churn-session.
    #[arg(long)]
    churn_max_session: Option<String>,
}

fn main() -> Result<()> {
    color_eyre::install()?;
    let args = Args::parse();
    env_logger::Builder::from_env(Env::default().default_filter_or("info")).init();
    
    info!("Starting MoneroSim configuration parser v2");
    info!("Configuration file: {:?}", args.config);
    info!("Output directory: {:?}", args.output);

    // Load configuration using new system
    let mut new_config = config_loader::load_config(&args.config)?;

    // CLI override: --reachable sets the global reachable fraction, beating
    // general.reachable_fraction from the config file.
    if let Some(r) = args.reachable {
        if !(0.0..=1.0).contains(&r) {
            color_eyre::eyre::bail!("--reachable must be in [0.0, 1.0], got {}", r);
        }
        info!("CLI override: reachable_fraction = {} (was {})", r, new_config.general.reachable_fraction);
        new_config.general.reachable_fraction = r;
    }

    // CLI: --churn-* enable or override peer churn. Any of these flags
    // switches churn on (with defaults) when the config has no [general.churn].
    if args.churn_session.is_some() || args.churn_downtime.is_some() || args.churn_max_session.is_some() {
        let c = new_config.general.churn.get_or_insert_with(|| monerosim::config::ChurnConfig {
            mean_session: "2h".to_string(),
            mean_downtime: "30m".to_string(),
            fraction: 1.0,
            min_session: None,
            max_session: None,
            min_downtime: None,
        });
        if let Some(s) = args.churn_session { c.mean_session = s; }
        if let Some(d) = args.churn_downtime { c.mean_downtime = d; }
        if let Some(m) = args.churn_max_session { c.max_session = Some(m); }
        info!(
            "CLI churn: mean_session={} mean_downtime={} max_session={:?} fraction={}",
            c.mean_session, c.mean_downtime, c.max_session, c.fraction
        );
    }

    // Determine output directory and final config path
    let (output_dir, shadow_config_path) = if args.output.extension().map_or(false, |ext| ext == "yaml") {
        (
            args.output.parent().unwrap_or_else(|| Path::new(".")).to_path_buf(),
            args.output.clone(),
        )
    } else {
        (
            args.output.clone(),
            args.output.join("shadow_agents.yaml"),
        )
    };

    // Clean up previous simulation state
    info!("Cleaning up previous simulation state");
    if output_dir.exists() {
        // Only clean if it's not the current directory
        if output_dir != Path::new(".") {
            remove_dir_with_permissions(&output_dir)
                .wrap_err_with(|| format!("Failed to remove output directory '{}'", output_dir.display()))?;
        }
    }
    let shared_dir = Path::new(&new_config.general.shared_dir);
    remove_dir_with_permissions(shared_dir).wrap_err("Failed to remove shared directory")?;

    // Clean up per-agent data directories from previous runs ({daemon_data_dir}/monero-*)
    // This replaces the per-agent `rm -rf {daemon_data_dir}/monero-{id}` that was previously
    // done inside each daemon's bash wrapper at simulation startup.
    let daemon_data_dir = Path::new(&new_config.general.daemon_data_dir);
    if let Ok(entries) = fs::read_dir(daemon_data_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name();
            let name_str = name.to_string_lossy();
            if name_str.starts_with("monero-") {
                info!("Removing stale daemon data directory: {}/{}", daemon_data_dir.display(), name_str);
                remove_dir_with_permissions(&entry.path())
                    .unwrap_or_else(|e| warn!("Failed to remove {}/{}: {}", daemon_data_dir.display(), name_str, e));
            }
        }
    }

    // Create fresh directories
    fs::create_dir_all(&output_dir)
        .wrap_err_with(|| format!("Failed to create output directory '{}'", output_dir.display()))?;
    fs::create_dir_all(shared_dir).wrap_err("Failed to create shared directory")?;

    // Generate agent-based Shadow configuration
    info!("Running in agent-based simulation mode");
    generate_agent_shadow_config(&new_config, &shadow_config_path)?;

    info!("Generated Agent-based Shadow configuration: {:?}", shadow_config_path);
    
    info!("Ready to run Shadow simulation with: shadow {:?}", shadow_config_path);
    
    info!("Configuration parsing completed successfully");
    Ok(())
}
