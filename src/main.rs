use clap::Parser;
use color_eyre::eyre::WrapErr;
use color_eyre::Result;
use env_logger::Env;
use log::{info, warn};
use std::fs;
use std::path::{Path, PathBuf};

mod build;
mod config_v2;
mod config_loader;
mod shadow_agents;

use config_v2::Config as NewConfig;
use shadow_agents::generate_agent_shadow_config;

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
            fs::remove_dir_all(&output_dir)
                .wrap_err_with(|| format!("Failed to remove output directory '{}'", output_dir.display()))?;
        }
    }
    let shared_dir = Path::new("/tmp/monerosim_shared");
    if shared_dir.exists() {
        fs::remove_dir_all(shared_dir).wrap_err("Failed to remove shared directory")?;
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;
    
    #[test]
    fn test_cli_parsing() {
        let args = Args::parse_from(&[
            "monerosim",
            "--config", "test.yaml",
        ]);
        
        assert_eq!(args.config, PathBuf::from("test.yaml"));
        assert_eq!(args.output, PathBuf::from("shadow_output"));
    }
    
    #[test]
    fn test_migration_args() {
        let args = Args::parse_from(&[
            "monerosim",
            "--config", "test.yaml",
            "--migrate",
            "--migrate-output", "test_migrated.yaml",
        ]);
        
        assert!(args.migrate);
        assert_eq!(args.migrate_output, Some(PathBuf::from("test_migrated.yaml")));
    }
}