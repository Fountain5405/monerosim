use clap::Parser;
use color_eyre::eyre::WrapErr;
use color_eyre::Result;
use env_logger::Env;
use log::info;
use std::fs::File;
use std::path::PathBuf;
use std::time::Duration;

mod build;
mod config;
mod shadow;

use config::Config;

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
}

fn main() -> Result<()> {
    // Parse command-line arguments
    let args = Args::parse();
    
    // Initialize logging with default filter level of "info"
    env_logger::Builder::from_env(Env::default().default_filter_or("info")).init();
    
    info!("Starting MoneroSim configuration parser");
    info!("Configuration file: {:?}", args.config);
    info!("Output directory: {:?}", args.output);
    
    // Read and parse the configuration file
    let config = load_config(&args.config)?;
    
    // Prepare build directories and log the build plan
    let build_plans = build::prepare_builds(&config)?;
    
    // Build monero binaries for each node type
    build::build_monero_binaries(&build_plans)?;
    
    // Create output directory if it doesn't exist
    std::fs::create_dir_all(&args.output)?;
    
    // Generate Shadow configuration (EthShadow approach)
    shadow::generate_shadow_config(&config, &args.output)?;
    
    let shadow_config_path = args.output.join("shadow.yaml");
    info!("Generated Shadow configuration: {:?}", shadow_config_path);
    
    // Log the parsed configuration values
    info!("Successfully parsed configuration:");
    info!("  General stop time: {}", config.general.stop_time);
    info!("  Monero nodes:");
    for (i, node) in config.nodes.iter().enumerate() {
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
    
    info!("Configuration parsing completed successfully");
    info!("Ready to run Shadow simulation with: shadow --config={:?}", shadow_config_path);
    Ok(())
}

/// Load and parse the configuration from a YAML file
/// 
/// This function reads the specified YAML file and deserializes it into our Config struct.
/// It includes robust error handling for file reading and YAML parsing.
/// 
/// # Arguments
/// * `config_path` - Path to the YAML configuration file
/// 
/// # Returns
/// * `Result<Config>` - The parsed configuration or an error
fn load_config(config_path: &PathBuf) -> Result<Config> {
    // Open the configuration file
    let file = File::open(config_path)
        .wrap_err_with(|| format!("Unable to read configuration file: {:?}", config_path))?;
    
    // Parse the YAML content into our Config struct
    let config: Config = serde_yaml::from_reader(file)
        .wrap_err_with(|| format!("Failed to parse YAML configuration from: {:?}", config_path))?;
    
    Ok(config)
} 