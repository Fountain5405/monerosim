use clap::Parser;
use color_eyre::eyre::WrapErr;
use color_eyre::Result;
use env_logger::Env;
use log::{info, warn};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

// Use modules from the library instead of redeclaring them
use monerosim::config_loader;
use monerosim::orchestrator::generate_agent_shadow_config;

/// Refuse to touch a directory we don't own. Shared multi-user boxes may
/// have another user's directory sitting at a path we'd otherwise default
/// to (e.g. a stale `/tmp/monerosim_shared`); chmod'ing or rm -rf'ing it
/// out from under them would be a disaster, and normal permissions won't
/// always stop us (e.g. a world-writable sticky-bit tmp dir they created).
fn check_owned_by_us(path: &Path) -> std::io::Result<()> {
    use std::os::unix::fs::MetadataExt;
    let meta = fs::metadata(path)?;
    let owner_uid = meta.uid();
    let our_uid = unsafe { libc::getuid() };
    if owner_uid != our_uid {
        return Err(std::io::Error::new(
            std::io::ErrorKind::PermissionDenied,
            format!(
                "refusing to modify or delete '{}': owned by uid {}, not us (uid {})",
                path.display(),
                owner_uid,
                our_uid
            ),
        ));
    }
    Ok(())
}

/// Recursively fix permissions on a directory tree to allow deletion.
/// This handles cases where monero-wallet-rpc creates directories with
/// restrictive permissions (d---------) that prevent normal rm -rf.
fn fix_permissions_recursive(path: &Path) -> std::io::Result<()> {
    if path.is_dir() {
        check_owned_by_us(path)?;

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

/// Remove a directory tree, first fixing permissions if needed. Skips
/// silently if the path doesn't exist; refuses (PermissionDenied) if it
/// exists but isn't owned by us.
fn remove_dir_with_permissions(path: &Path) -> std::io::Result<()> {
    if path.exists() {
        check_owned_by_us(path)?;
        // Try normal removal first
        if fs::remove_dir_all(path).is_err() {
            // If it fails, fix permissions and try again
            fix_permissions_recursive(path)?;
            fs::remove_dir_all(path)?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod ownership_guard_tests {
    use super::*;

    /// If `/tmp/monerosim_shared` happens to exist on this box and is owned
    /// by someone else, prove the guard refuses to touch it and leaves it
    /// intact. This is the exact near-miss the guard exists to prevent, so
    /// we use it opportunistically instead of a synthetic other-uid path
    /// (which we can't create without root). Skips (does not fail) if no
    /// such path is available in the sandbox.
    #[test]
    fn refuses_to_remove_a_directory_we_do_not_own() {
        use std::os::unix::fs::MetadataExt;

        let candidate = Path::new("/tmp/monerosim_shared");
        let meta = match fs::metadata(candidate) {
            Ok(m) => m,
            Err(_) => {
                eprintln!("skip: {} does not exist here", candidate.display());
                return;
            }
        };
        let our_uid = unsafe { libc::getuid() };
        if meta.uid() == our_uid {
            eprintln!(
                "skip: {} is owned by us (uid {}); no other-uid dir available to test against",
                candidate.display(),
                our_uid
            );
            return;
        }

        let err = remove_dir_with_permissions(candidate)
            .expect_err("must refuse to remove a directory we don't own");
        assert_eq!(err.kind(), std::io::ErrorKind::PermissionDenied);
        assert!(
            candidate.exists(),
            "directory must still exist after the refused removal"
        );
    }
}

/// Configuration utility for Monero network simulations in Shadow
#[derive(Parser, Debug)]
#[command(author, about, long_about = None,
    version = concat!(env!("CARGO_PKG_VERSION"), " (", env!("MONEROSIM_GIT_HASH"), ")"))]
struct Args {
    /// Path to the simulation configuration YAML file
    #[arg(short, long)]
    config: PathBuf,

    /// Output directory for Shadow configuration and simulation files
    #[arg(short, long, default_value = "shadow_output")]
    output: PathBuf,

    /// Fraction of non-seed nodes that are reachable through the physical
    /// inbound firewall, in [0.0, 1.0]. 1.0 = all reachable (default /
    /// perfect network); lower = mainnet-like NAT majority, with the
    /// complement having their P2P port blocked (Shadow
    /// `blocked_inbound_ports`), simulating a NAT/firewall that drops
    /// unsolicited inbound connections. Overrides `general.reachable_fraction`
    /// from the config. Seeds and miners are always reachable regardless.
    #[arg(long)]
    reachable: Option<f64>,

    /// Enable/override peer turnover: mean ONLINE session length (e.g. "2h").
    /// If the config has no `[general.turnover]`, passing this enables turnover
    /// with sensible defaults (downtime 30m, all eligible relays + users).
    /// Overrides
    /// `general.turnover.mean_session`. See --turnover-downtime / --turnover-max-session.
    #[arg(long)]
    turnover_session: Option<String>,

    /// Mean OFFLINE gap between turnover sessions (e.g. "30m"). See --turnover-session.
    #[arg(long)]
    turnover_downtime: Option<String>,

    /// Hard ceiling on any single turnover session (e.g. "6h"); omit to let the
    /// exponential tail run free. See --turnover-session.
    #[arg(long)]
    turnover_max_session: Option<String>,

    /// Fast process starts, nothing else changed: clock reads keep Shadow's
    /// 10 ns charge except in a busy loop on the clock (more than 10,000 reads
    /// in a row with no other syscall), where each further read is charged
    /// 1 us. Ends monero's start-up calibration loop in ~0.2 s instead of ~16 s.
    /// Needs shadowformonero >= v0.2.5. Overrides
    /// `performance.unblocked_vdso_busy_threshold` / `unblocked_vdso_busy_latency`.
    #[arg(long, conflicts_with = "allfast")]
    bootfast: bool,

    /// Charge 1 us of simulated time for every clock read in every process
    /// for the whole run (Shadow's default: 10 ns). Overrides
    /// `performance.unblocked_vdso_latency`.
    #[arg(long)]
    allfast: bool,
}

/// `--bootfast`: clock reads in a row after which the busy charge applies. In a
/// full quickstart no monerod made more than 371 in a row; monero's start-up
/// calibration loop makes 10 million (docs/20261003_startup_cost.md).
const BOOTFAST_BUSY_THRESHOLD: u64 = 10_000;

/// Clock-read charge for `--bootfast` (past the threshold) and `--allfast`.
const FAST_VDSO_LATENCY: &str = "1 us";

/// Applies `--bootfast` / `--allfast` over the config's `performance` knobs
/// (clap rejects the two together).
fn apply_clock_flags(
    performance: &mut monerosim::config::PerformanceConfig,
    bootfast: bool,
    allfast: bool,
) {
    if bootfast {
        performance.unblocked_vdso_busy_threshold = Some(BOOTFAST_BUSY_THRESHOLD);
        performance.unblocked_vdso_busy_latency = Some(FAST_VDSO_LATENCY.to_string());
        info!(
            "CLI --bootfast: clock reads past {} in a row charge {}",
            BOOTFAST_BUSY_THRESHOLD, FAST_VDSO_LATENCY
        );
    }
    if allfast {
        performance.unblocked_vdso_latency = Some(FAST_VDSO_LATENCY.to_string());
        info!(
            "CLI --allfast: every clock read charges {}",
            FAST_VDSO_LATENCY
        );
    }
}

#[cfg(test)]
mod clock_flag_tests {
    use super::*;
    use monerosim::config::PerformanceConfig;

    #[test]
    fn bootfast_sets_only_the_busy_loop_charge() {
        let mut p = PerformanceConfig::default();
        apply_clock_flags(&mut p, true, false);
        assert_eq!(p.unblocked_vdso_busy_threshold, Some(10_000));
        assert_eq!(p.unblocked_vdso_busy_latency.as_deref(), Some("1 us"));
        assert_eq!(p.unblocked_vdso_latency, None);
    }

    #[test]
    fn allfast_sets_only_the_plain_charge() {
        let mut p = PerformanceConfig::default();
        apply_clock_flags(&mut p, false, true);
        assert_eq!(p.unblocked_vdso_latency.as_deref(), Some("1 us"));
        assert_eq!(p.unblocked_vdso_busy_threshold, None);
        assert_eq!(p.unblocked_vdso_busy_latency, None);
    }

    #[test]
    fn neither_flag_keeps_the_config() {
        let mut p = PerformanceConfig::default();
        p.unblocked_vdso_latency = Some("100 ns".to_string());
        apply_clock_flags(&mut p, false, false);
        assert_eq!(p.unblocked_vdso_latency.as_deref(), Some("100 ns"));
        assert_eq!(p.unblocked_vdso_busy_threshold, None);
    }

    #[test]
    fn flags_are_mutually_exclusive() {
        let r =
            Args::try_parse_from(["monerosim", "--config", "x.yaml", "--bootfast", "--allfast"]);
        assert!(r.is_err());
    }
}

fn main() -> Result<()> {
    color_eyre::install()?;
    let args = Args::parse();
    env_logger::Builder::from_env(Env::default().default_filter_or("info")).init();

    info!("Starting MoneroSim configuration parser v2");
    info!("Configuration file: {:?}", args.config);
    info!("Output directory: {:?}", args.output);

    // Record the config stem before any config defaults resolve, so a bare
    // invocation (no MONEROSIM_SHARED_DIR / MONEROSIM_DAEMON_DATA_DIR) gets
    // its own /tmp/monerosim-<timestamp>_<stem>_<pid> namespace instead of
    // colliding with other users/runs on a shared /tmp.
    let config_stem = args
        .config
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("config");
    monerosim::set_run_context(config_stem);

    // Load configuration using new system
    let mut new_config = config_loader::load_config(&args.config)?;

    info!(
        "Per-run tmp namespace: {}",
        monerosim::run_namespace_source()
    );
    info!("Shared dir: {}", new_config.general.shared_dir);
    info!("Daemon data dir: {}", new_config.general.daemon_data_dir);

    // CLI override: --reachable sets the global reachable fraction, beating
    // general.reachable_fraction from the config file.
    if let Some(r) = args.reachable {
        if !(0.0..=1.0).contains(&r) {
            color_eyre::eyre::bail!("--reachable must be in [0.0, 1.0], got {}", r);
        }
        info!(
            "CLI override: reachable_fraction = {} (was {})",
            r, new_config.general.reachable_fraction
        );
        new_config.general.reachable_fraction = r;
    }

    // CLI: --turnover-* enable or override peer turnover. Any of these flags
    // switches turnover on (with defaults) when the config has no [general.turnover].
    if args.turnover_session.is_some()
        || args.turnover_downtime.is_some()
        || args.turnover_max_session.is_some()
    {
        let c =
            new_config
                .general
                .turnover
                .get_or_insert_with(|| monerosim::config::TurnoverConfig {
                    mean_session: "2h".to_string(),
                    mean_downtime: "30m".to_string(),
                    fraction: 1.0,
                    min_session: None,
                    max_session: None,
                    min_downtime: None,
                });
        if let Some(s) = args.turnover_session {
            c.mean_session = s;
        }
        if let Some(d) = args.turnover_downtime {
            c.mean_downtime = d;
        }
        if let Some(m) = args.turnover_max_session {
            c.max_session = Some(m);
        }
        info!(
            "CLI turnover: mean_session={} mean_downtime={} max_session={:?} fraction={}",
            c.mean_session, c.mean_downtime, c.max_session, c.fraction
        );
    }

    // CLI: --bootfast / --allfast set how much simulated time a clock read
    // costs (docs/20261003_startup_cost.md).
    apply_clock_flags(&mut new_config.performance, args.bootfast, args.allfast);

    // Determine output directory and final config path
    let (output_dir, shadow_config_path) =
        if args.output.extension().map_or(false, |ext| ext == "yaml") {
            (
                args.output
                    .parent()
                    .unwrap_or_else(|| Path::new("."))
                    .to_path_buf(),
                args.output.clone(),
            )
        } else {
            (args.output.clone(), args.output.join("shadow_agents.yaml"))
        };

    // Clean up previous simulation state
    info!("Cleaning up previous simulation state");
    if output_dir.exists() {
        // Only clean if it's not the current directory
        if output_dir != Path::new(".") {
            remove_dir_with_permissions(&output_dir).wrap_err_with(|| {
                format!(
                    "Failed to remove output directory '{}'",
                    output_dir.display()
                )
            })?;
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
                info!(
                    "Removing stale daemon data directory: {}/{}",
                    daemon_data_dir.display(),
                    name_str
                );
                remove_dir_with_permissions(&entry.path()).unwrap_or_else(|e| {
                    warn!(
                        "Failed to remove {}/{}: {}",
                        daemon_data_dir.display(),
                        name_str,
                        e
                    )
                });
            }
        }
    }

    // Create fresh directories
    fs::create_dir_all(&output_dir).wrap_err_with(|| {
        format!(
            "Failed to create output directory '{}'",
            output_dir.display()
        )
    })?;
    fs::create_dir_all(shared_dir).wrap_err("Failed to create shared directory")?;

    // A bare invocation (no MONEROSIM_DAEMON_DATA_DIR, no YAML override) got
    // its own /tmp/monerosim-<ts>_<stem>_<pid> namespace above. Nothing
    // writes an .owner_pid there — this process is gone the moment the
    // config is generated — so leave a breadcrumb that lets run_sim.sh's
    // launch report and scripts/sweep_stale_runs.sh tell "generator
    // namespace" apart from "dir we know nothing about".
    if std::env::var("MONEROSIM_DAEMON_DATA_DIR").is_err()
        && new_config.general.daemon_data_dir == monerosim::default_daemon_data_dir()
    {
        let marker = daemon_data_dir.join(".generated_by");
        let note = format!(
            "monerosim {} pid {} {} config {}\n",
            env!("CARGO_PKG_VERSION"),
            std::process::id(),
            chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ"),
            args.config.display()
        );
        if let Err(e) = fs::write(&marker, note) {
            warn!("Could not write {}: {}", marker.display(), e);
        }
    }

    // Generate agent-based Shadow configuration
    info!("Running in agent-based simulation mode");
    generate_agent_shadow_config(&new_config, &shadow_config_path)?;

    info!(
        "Generated Agent-based Shadow configuration: {:?}",
        shadow_config_path
    );

    info!(
        "Ready to run Shadow simulation with: shadow {:?}",
        shadow_config_path
    );

    info!("Configuration parsing completed successfully");
    Ok(())
}
