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
    
    /// Migrate configuration to new format
    #[arg(long)]
    migrate: bool,
    
    /// Output path for migrated configuration
    #[arg(long, requires = "migrate")]
    migrate_output: Option<PathBuf>,
}

fn main() -> Result<()> {
    // Initialize error handling
    color_eyre::install()?;
    
    // Parse command-line arguments
    let args = Args::parse();
    
    // Initialize logging with default filter level of "info"
    env_logger::Builder::from_env(Env::default().default_filter_or("info")).init();
    
    info!("Starting MoneroSim configuration parser v2");
    info!("Configuration file: {:?}", args.config);
    info!("Output directory: {:?}", args.output);
    
    // Handle migration if requested
    if args.migrate {
        let output_path = args.migrate_output.unwrap_or_else(|| {
            let mut path = args.config.clone();
            path.set_extension("migrated.yaml");
            path
        });
        
        config_loader::migrate_config(&args.config, &output_path)?;
        info!("Configuration migrated successfully to: {:?}", output_path);
        return Ok(());
    }
    
    // Check configuration compatibility
    config_loader::check_config_compatibility(&args.config)?;
    
    // Load configuration using new system
    let new_config = config_loader::load_config(&args.config)?;
    
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
    let shared_dir = Path::new("/tmp/monerosim_shared");
    remove_dir_with_permissions(shared_dir).wrap_err("Failed to remove shared directory")?;

    // Clean up per-agent data directories from previous runs (/tmp/monero-*)
    // This replaces the per-agent `rm -rf /tmp/monero-{id}` that was previously
    // done inside each daemon's bash wrapper at simulation startup.
    if let Ok(entries) = fs::read_dir("/tmp") {
        for entry in entries.flatten() {
            let name = entry.file_name();
            let name_str = name.to_string_lossy();
            if name_str.starts_with("monero-") {
                info!("Removing stale daemon data directory: /tmp/{}", name_str);
                remove_dir_with_permissions(&entry.path())
                    .unwrap_or_else(|e| warn!("Failed to remove /tmp/{}: {}", name_str, e));
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
