use clap::Parser;
use color_eyre::eyre::WrapErr;
use color_eyre::Result;
use env_logger::Env;
use log::{info, warn};
use std::path::PathBuf;

mod build;
mod config;
mod config_v2;
mod config_loader;
mod config_compat;
mod shadow;
mod shadow_agents;

use config::Config as OldConfig;
use config_v2::Config as NewConfig;
use shadow_agents::{AgentConfig, generate_agent_shadow_config};

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
    
    // Determine if we should use agent mode based on configuration structure
    let use_agent_mode = config_compat::should_use_agent_mode(&new_config, false);
    
    if use_agent_mode {
        // Extract agent configuration
        let agent_config = config_compat::extract_agent_config(&new_config)
            .ok_or_else(|| color_eyre::eyre::eyre!("Failed to extract agent configuration"))?;
        
        // Convert to old format for compatibility with existing functions
        let old_config = config_compat::convert_to_old_format(&new_config)?;
        
        // Create output directory if it doesn't exist
        std::fs::create_dir_all(&args.output)?;
        
        // Generate agent-based Shadow configuration
        info!("Running in agent-based simulation mode");
        generate_agent_shadow_config(&old_config, &agent_config, &args.output)?;
        
        let shadow_config_path = args.output.join("shadow_agents.yaml");
        info!("Generated Agent-based Shadow configuration: {:?}", shadow_config_path);
        info!("Agent configuration:");
        info!("  Regular users: {}", agent_config.regular_users);
        info!("  Marketplaces: {}", agent_config.marketplaces);
        info!("  Mining pools: {}", agent_config.mining_pools);
        info!("  Transaction frequency: {}", agent_config.transaction_frequency);
        
        info!("Ready to run Shadow simulation with: shadow {:?}", shadow_config_path);
    } else {
        // Traditional simulation mode
        info!("Running in traditional simulation mode");
        
        // Convert to old format for compatibility
        let old_config = config_compat::convert_to_old_format(&new_config)?;
        
        // Create output directory if it doesn't exist
        std::fs::create_dir_all(&args.output)?;
        
        // Prepare build directories and log the build plan
        let build_plans = build::prepare_builds(&old_config)?;
        
        // Build monero binaries for each node type
        build::build_monero_binaries(&build_plans)?;
        
        // Generate Shadow configuration (traditional approach)
        shadow::generate_shadow_config(&old_config, &args.output)?;
        
        let shadow_config_path = args.output.join("shadow.yaml");
        info!("Generated Shadow configuration: {:?}", shadow_config_path);
        
        // Log the parsed configuration values
        info!("Successfully parsed configuration:");
        info!("  General stop time: {}", old_config.general.stop_time);
        info!("  Monero nodes:");
        for (i, node) in old_config.nodes.iter().enumerate() {
            info!("    Node {} (name: {}):", i + 1, node.name);
            info!("      IP: {}", node.ip);
            info!("      Port: {}", node.port);
            if let Some(start_time) = &node.start_time {
                info!("      Start time: {}", start_time);
            }
            if let Some(mining) = node.mining {
                info!("      Mining: {}", mining);
            }
            if let Some(difficulty) = node.fixed_difficulty {
                info!("      Fixed difficulty: {}", difficulty);
            }
        }
        
        info!("Ready to run Shadow simulation with: shadow {:?}", shadow_config_path);
    }
    
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