use crate::config_v2::{
    Config, AgentDefinitions, UserAgentConfig, BlockControllerConfig, PureScriptAgentConfig,
};
use rand::seq::SliceRandom;
use serde_json;
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;
use std::process::Command;

#[derive(serde::Serialize, Debug)]
struct MinerInfo {
    ip_addr: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    wallet_address: Option<String>,
    weight: u32,
}

#[derive(serde::Serialize, Debug)]
struct MinerRegistry {
    miners: Vec<MinerInfo>,
}

#[derive(serde::Serialize, Debug)]
struct AgentInfo {
    id: String,
    ip_addr: String,
    daemon: bool,
    wallet: bool,
    user_script: Option<String>,
    attributes: HashMap<String, String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    wallet_rpc_port: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    daemon_rpc_port: Option<u16>,
}

#[derive(serde::Serialize, Debug)]
struct AgentRegistry {
    agents: Vec<AgentInfo>,
}

// Helper function to find agents by role
fn find_agent_by_role<'a>(agents: &'a [AgentInfo], role: &str) -> Option<&'a AgentInfo> {
    agents.iter().find(|a| a.attributes.get("role") == Some(&role.to_string()))
}


#[derive(serde::Serialize, Debug)]
struct ShadowConfig {
    general: ShadowGeneral,
    network: ShadowNetwork,
    experimental: ShadowExperimental,
    hosts: HashMap<String, ShadowHost>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGeneral {
    stop_time: String,
    model_unblocked_syscall_latency: bool,
    log_level: String,
}

#[derive(serde::Serialize, Debug)]
struct ShadowExperimental {
    #[serde(skip_serializing_if = "Option::is_none")]
    runahead: Option<String>,
    use_dynamic_runahead: bool,
}

#[derive(serde::Serialize, Debug)]
struct ShadowNetwork {
    graph: ShadowGraph,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGraph {
    #[serde(rename = "type")]
    graph_type: String,
}

#[derive(serde::Serialize, Debug)]
struct ShadowHost {
    network_node_id: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    ip_addr: Option<String>,
    processes: Vec<ShadowProcess>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowProcess {
    path: String,
    args: String,
    environment: HashMap<String, String>,
    start_time: String,
}

/// Generate a random start time between 1 and 180 seconds
fn generate_random_start_time() -> String {
    use rand::Rng;
    let mut rng = rand::thread_rng();
    let random_seconds = rng.gen_range(1..=180);
    format!("{}s", random_seconds)
}


/// Helper function to create a Python agent command
fn create_agent_command(current_dir: &str, script_path: &str, args: &[String]) -> String {
    // Build the python invocation without wrapping it in another "-c" so callers
    // can prepend their own "-c '... && {}'" safely.
    let python_cmd = if script_path.contains('.') && !script_path.contains('/') && !script_path.contains('\\') {
        // It's a module: use -m
        format!("python3 -m {} {}", script_path, args.join(" "))
    } else {
        // It's a file path
        format!("python3 {} {}", script_path, args.join(" "))
    };
    // Return a single bash -c command that cds into workspace, activates venv, then runs python_cmd.
    format!("cd {} && . ./venv/bin/activate && {}", current_dir, python_cmd)
}

/// Add a Monero daemon process to the processes list
fn add_daemon_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_port: u16,
    agent_rpc_port: u16,
    monerod_path: &str,
    monero_environment: &HashMap<String, String>,
    seed_agents: &[String],
    index: usize,
) {
    let mut daemon_args = vec![
        format!("--data-dir=/tmp/monero-{}", agent_id),
        "--log-file=/dev/stdout".to_string(),
        "--log-level=1".to_string(),
        "--simulation".to_string(),
        "--disable-dns-checkpoints".to_string(),
        "--out-peers=4".to_string(),
        "--in-peers=4".to_string(),
        "--disable-seed-nodes".to_string(),
        "--no-igd".to_string(),
        "--prep-blocks-threads=1".to_string(),
        "--max-concurrency=1".to_string(),
        "--no-zmq".to_string(),
        "--db-sync-mode=safe".to_string(),
        "--non-interactive".to_string(),
        "--max-connections-per-ip=50".to_string(),
        "--limit-rate-up=1024".to_string(),
        "--limit-rate-down=1024".to_string(),
        "--block-sync-size=1".to_string(),
        format!("--rpc-bind-ip={}", agent_ip),
        format!("--rpc-bind-port={}", agent_rpc_port),
        "--confirm-external-bind".to_string(),
        "--disable-rpc-ban".to_string(),
        "--rpc-access-control-origins=*".to_string(),
        "--regtest".to_string(),
        format!("--p2p-bind-ip={}", agent_ip),
        format!("--p2p-bind-port={}", agent_port),
        "--fixed-difficulty=200".to_string(),
        "--allow-local-ip".to_string(),
    ];

    // Add connections to seed agents using DAG pattern (only connect to nodes with lower index)
    for (j, seed) in seed_agents.iter().enumerate() {
        if j < index {
            daemon_args.push(format!("--add-exclusive-node={}", seed));
        }
    }
    
    // Special case for the first node (index 0) - connect to the second node if available
    if index == 0 && seed_agents.len() > 1 {
        daemon_args.push(format!("--add-exclusive-node={}", seed_agents[1]));
    }

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/monero-{} && {} {}'",
            agent_id, monerod_path, daemon_args.join(" ")
        ),
        environment: monero_environment.clone(),
        start_time: format!("{}s", 5 + index * 2), // Start daemons first
    });
}

/// Add a wallet process to the processes list
fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    wallet_path: &str,
    environment: &HashMap<String, String>,
    index: usize,
) {
    let wallet_name = format!("{}_wallet", agent_id);
    
    // Create wallet JSON content
    let wallet_json_content = format!(
        r#"{{
  "version": 1,
  "filename": "{}",
  "scan_from_height": 0,
  "password": "",
  "viewkey": "",
  "spendkey": "",
  "seed": "",
  "seed_passphrase": "",
  "address": "",
  "restore_height": 0,
  "autosave_current": true
}}"#,
        wallet_name
    );

    // Get the absolute path to the wallet launcher script
    let launcher_path = std::env::current_dir()
        .unwrap()
        .join("scripts/wallet_launcher.sh")
        .to_string_lossy()
        .to_string();

    // First, create the wallet directory in a separate process
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'mkdir -p /tmp/monerosim_shared/{}_wallet'",
            agent_id
        ),
        environment: environment.clone(),
        start_time: format!("{}s", 54 + index * 2), // Start before wallet RPC
    });

    // Launch wallet RPC directly - it will create wallets on demand
    let wallet_path = std::fs::canonicalize("monero-wallet-rpc")
        .expect("Failed to resolve absolute path to monero-wallet-rpc")
        .to_string_lossy()
        .to_string();
        
    let wallet_args = format!(
        "--daemon-address=http://{}:{} --rpc-bind-port={} --rpc-bind-ip={} \
         --disable-rpc-login --trusted-daemon --log-level=1 \
         --wallet-dir=/tmp/monerosim_shared/{}_wallet --non-interactive --confirm-external-bind \
         --allow-mismatched-daemon-version --max-concurrency=1 \
         --daemon-ssl-allow-any-cert",
        agent_ip, agent_rpc_port, wallet_rpc_port, agent_ip, agent_id
    );
    
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c '{} {}'",
            wallet_path, wallet_args
        ),
        environment: environment.clone(),
        start_time: format!("{}s", 55 + index * 2),
    });
}

/// Add a user agent process to the processes list
fn add_user_agent_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    p2p_port: u16,
    script: &str,
    attributes: Option<&HashMap<String, String>>,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    index: usize,
) {
    let mut agent_args = vec![
        format!("--id {}", agent_id),
        format!("--shared-dir {}", shared_dir.to_str().unwrap()),
        format!("--rpc-host {}", agent_ip),
        format!("--agent-rpc-port {}", agent_rpc_port),
        format!("--wallet-rpc-port {}", wallet_rpc_port),
        format!("--p2p-port {}", p2p_port),
        format!("--log-level DEBUG"),
    ];

    // Add attributes from config as command-line arguments
    if let Some(attrs) = attributes {
        // Map specific attributes to their correct parameter names
        for (key, value) in attrs {
            if key == "transaction_interval" {
                agent_args.push(format!("--tx-frequency {}", value));
            } else if key == "min_transaction_amount" || key == "max_transaction_amount" || key == "is_miner" {
                // These should be passed as attributes
                agent_args.push(format!("--attributes {} {}", key, value));
            } else if key != "hashrate" {
                // Pass other attributes directly, but filter out hashrate only
                agent_args.push(format!("--{} {}", key, value));
            }
        }
    }

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'while ! nc -z {ip} {wport}; do echo \"Waiting for wallet RPC at {ip}:{wport}...\"; sleep 2; done && cd {cwd} && . ./venv/bin/activate && {cmd}'",
            ip = agent_ip,
            wport = wallet_rpc_port,
            cwd = current_dir,
            cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
                format!("python3 -m {} {}", script, agent_args.join(" "))
            } else {
                format!("python3 {} {}", script, agent_args.join(" "))
            }
        ),
        environment: environment.clone(),
        start_time: format!("{}s", 60 + index * 2), // Start agents after wallets
    });
}

/// Process user agents
fn process_user_agents(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    seed_agents: &mut Vec<String>,
    next_ip: &mut u8,
    monerod_path: &str,
    wallet_path: &str,
    environment: &HashMap<String, String>,
    monero_environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
) -> color_eyre::eyre::Result<()> {
    // First, build the seed_agents list
    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            let is_miner = user_agent_config.is_miner_value();
            let agent_ip = format!("11.0.0.{}", 10 + i as u8);
            let agent_port = 28080;

            // Add to seed agents if it's one of the first two users or a miner
            if i < 2 || is_miner {
                seed_agents.push(format!("{}:{}", agent_ip, agent_port));
            }
        }
    }

    // Now process all user agents
    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            // Check if this is a miner agent
            let is_miner = user_agent_config.is_miner_value();
            // Use consistent naming for all user agents
            let agent_id = format!("user{:03}", i);
            
            let agent_ip = format!("11.0.0.{}", next_ip);
            let agent_port = 28080;
            
            // Use standard RPC ports for all agents
            let agent_rpc_port = 28081;
            
            // Use standard wallet RPC port for all agents
            // Since each agent has its own IP address, they can all use the same port
            let wallet_rpc_port = 28082;
            let p2p_port = 28080;

            let mut processes = Vec::new();

            // Add Monero daemon process
            add_daemon_process(
                &mut processes,
                &agent_id,
                &agent_ip,
                agent_port,
                agent_rpc_port,
                monerod_path,
                monero_environment,
                seed_agents,
                i,
            );

            // Add wallet process if wallet is specified
            if user_agent_config.wallet.is_some() {
                add_wallet_process(
                    &mut processes,
                    &agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    wallet_rpc_port,
                    wallet_path,
                    environment,
                    i,
                );
            }

            // Add user agent script if specified
            let user_script = user_agent_config.user_script.clone().unwrap_or_else(|| {
                if is_miner {
                    "agents.regular_user".to_string()
                } else {
                    "agents.regular_user".to_string()
                }
            });

            if !user_script.is_empty() {
                add_user_agent_process(
                    &mut processes,
                    &agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    wallet_rpc_port,
                    p2p_port,
                    &user_script,
                    user_agent_config.attributes.as_ref(),
                    environment,
                    shared_dir,
                    current_dir,
                    i,
                );
            }

            // Only add the host if it has any processes
            if !processes.is_empty() {
                hosts.insert(agent_id.clone(), ShadowHost {
                    network_node_id: 0,
                    ip_addr: Some(agent_ip.clone()),
                    processes,
                });
                *next_ip += 1; // One IP per agent (all processes share the same IP)
            }
        }
    }

    Ok(())
}

/// Process block controller agent
fn process_block_controller(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    next_ip: &mut u8,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
) -> color_eyre::eyre::Result<()> {
    if let Some(block_controller_config) = &agents.block_controller {
        let block_controller_id = "blockcontroller";
        let block_controller_ip = format!("11.0.0.{}", next_ip);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id {}", block_controller_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        if let Some(args) = &block_controller_config.arguments {
            agent_args.extend(args.iter().cloned());
        }

        // Block controller will self-discover miners from agent_registry.json, so we only need Python env
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!(
                "-c 'cd {cwd} && . ./venv/bin/activate && {cmd}'",
                cwd = current_dir,
                cmd = if block_controller_config.script.contains('.') && !block_controller_config.script.contains('/') && !block_controller_config.script.contains('\\') {
                    format!("python3 -m {} {}", block_controller_config.script, agent_args.join(" "))
                } else {
                    format!("python3 {} {}", block_controller_config.script, agent_args.join(" "))
                }
            ),
            environment: environment.clone(),
            start_time: "90s".to_string(), // Fixed start time for block controller
        });

        hosts.insert(block_controller_id.to_string(), ShadowHost {
            network_node_id: 0,
            ip_addr: Some(block_controller_ip),
            processes,
        });
        *next_ip += 1;
    }

    Ok(())
}

/// Process pure script agents
fn process_pure_script_agents(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    next_ip: &mut u8,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
) -> color_eyre::eyre::Result<()> {
    if let Some(pure_script_agents) = &agents.pure_script_agents {
        for (i, pure_script_config) in pure_script_agents.iter().enumerate() {
            let script_id = format!("script{:03}", i);
            let script_ip = format!("11.0.0.{}", next_ip);
            let mut processes = Vec::new();

            let mut script_args = vec![
                format!("--id {}", script_id),
                format!("--shared-dir {}", shared_dir.to_str().unwrap()),
                format!("--log-level DEBUG"),
            ];

            if let Some(args) = &pure_script_config.arguments {
                script_args.extend(args.iter().cloned());
            }

            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!(
                    "-c 'cd {cwd} && . ./venv/bin/activate && {cmd}'",
                    cwd = current_dir,
                    cmd = if pure_script_config.script.contains('.') && !pure_script_config.script.contains('/') && !pure_script_config.script.contains('\\') {
                        format!("python3 -m {} {}", pure_script_config.script, script_args.join(" "))
                    } else {
                        format!("python3 {} {}", pure_script_config.script, script_args.join(" "))
                    }
                ),
                environment: environment.clone(),
                start_time: format!("{}s", 30 + i * 5), // Staggered start times
            });

            hosts.insert(script_id.clone(), ShadowHost {
                network_node_id: 0,
                ip_addr: Some(script_ip),
                processes,
            });
            *next_ip += 1;
        }
    }

    Ok(())
}

/// Generate a Shadow configuration with agent support
pub fn generate_agent_shadow_config(
    config: &Config,
    output_path: &Path,
) -> color_eyre::eyre::Result<()> {
    const SHARED_DIR: &str = "/tmp/monerosim_shared";
    let shared_dir_path = Path::new(SHARED_DIR);

    let current_dir = std::env::current_dir()
        .map_err(|e| color_eyre::eyre::eyre!("Failed to get current directory: {}", e))?
        .to_string_lossy()
        .to_string();

    let mut hosts: HashMap<String, ShadowHost> = HashMap::new();

    // Common environment variables
    let mut environment: HashMap<String, String> = [
        ("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string()),
        ("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string()),
        ("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string()),
        ("MALLOC_ARENA_MAX".to_string(), "1".to_string()),
        ("PYTHONUNBUFFERED".to_string(), "1".to_string()), // Ensure Python output is unbuffered
    ].iter().cloned().collect();

    // Add MONEROSIM_LOG_LEVEL if specified in config
    if let Some(log_level) = &config.general.log_level {
        environment.insert("MONEROSIM_LOG_LEVEL".to_string(), log_level.to_uppercase());
    }

    // Monero-specific environment variables
    let mut monero_environment = environment.clone();
    monero_environment.insert("MONERO_BLOCK_SYNC_SIZE".to_string(), "1".to_string());
    monero_environment.insert("MONERO_DISABLE_DNS".to_string(), "1".to_string());
    monero_environment.insert("MONERO_MAX_CONNECTIONS_PER_IP".to_string(), "20".to_string());

    // Base IP allocation
    let mut next_ip = 10; // Start from 11.0.0.10

    // Helper to get absolute path for binaries
    let monerod_path = std::fs::canonicalize("builds/A/monero/bin/monerod")
        .map_err(|e| color_eyre::eyre::eyre!("Failed to resolve absolute path to monerod: {}", e))?
        .to_string_lossy()
        .to_string();
    let wallet_path = std::fs::canonicalize("builds/A/monero/bin/monero-wallet-rpc")
        .map_err(|e| color_eyre::eyre::eyre!("Failed to resolve absolute path to monero-wallet-rpc: {}", e))?
        .to_string_lossy()
        .to_string();

    // Store seed nodes for P2P connections
    let mut seed_nodes: Vec<String> = Vec::new();

    // Process all agent types from the configuration
    process_user_agents(
        &config.agents,
        &mut hosts,
        &mut seed_nodes,
        &mut next_ip,
        &monerod_path,
        &wallet_path,
        &environment,
        &monero_environment,
        shared_dir_path,
        &current_dir,
    )?;

    process_block_controller(
        &config.agents,
        &mut hosts,
        &mut next_ip,
        &environment,
        shared_dir_path,
        &current_dir,
    )?;

    process_pure_script_agents(
        &config.agents,
        &mut hosts,
        &mut next_ip,
        &environment,
        shared_dir_path,
        &current_dir,
    )?;

    // Create agent registry
    let mut agent_registry = AgentRegistry {
        agents: Vec::new(),
    };

    // Populate agent registry from user_agents
    if let Some(user_agents) = &config.agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            let is_miner = user_agent_config.is_miner_value();
            // Use consistent naming for all user agents
            let agent_id = format!("user{:03}", i);
            
            let agent_ip = format!("11.0.0.{}", 10 + i as u8);
            
            let attributes = user_agent_config.attributes.clone().unwrap_or_default();

            let agent_info = AgentInfo {
                id: agent_id,
                ip_addr: agent_ip,
                daemon: true, // Daemon is now required
                wallet: user_agent_config.wallet.is_some(),
                user_script: user_agent_config.user_script.clone(),
                attributes,
                wallet_rpc_port: if user_agent_config.wallet.is_some() { Some(28082) } else { None },
                daemon_rpc_port: Some(28081),
            };
            
            agent_registry.agents.push(agent_info);
        }
    }
    
    // Write agent registry to file
    let agent_registry_path = shared_dir_path.join("agent_registry.json");
    let agent_registry_json = serde_json::to_string_pretty(&agent_registry)?;
    std::fs::write(&agent_registry_path, &agent_registry_json)?;
    
    // Create miner registry
    let mut miner_registry = MinerRegistry {
        miners: Vec::new(),
    };
    
    // Populate miner registry from user_agents that are miners
    if let Some(user_agents) = &config.agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            if user_agent_config.is_miner_value() {
                let agent_id = format!("user{:03}", i);
                let agent_ip = format!("11.0.0.{}", 10 + i as u8);
                
                let miner_info = MinerInfo {
                    ip_addr: agent_ip,
                    wallet_address: None, // Will be populated by the block controller
                    weight: user_agent_config.attributes
                        .as_ref()
                        .and_then(|attrs| attrs.get("hashrate"))
                        .and_then(|h| h.parse::<u32>().ok())
                        .unwrap_or(0),
                };
                
                miner_registry.miners.push(miner_info);
            }
        }
    }
    
    // Write miner registry to file
    let miner_registry_path = shared_dir_path.join("miners.json");
    let miner_registry_json = serde_json::to_string_pretty(&miner_registry)?;
    std::fs::write(&miner_registry_path, &miner_registry_json)?;

    // Sort hosts by key to ensure consistent ordering in the output file
    let mut sorted_hosts: Vec<(String, ShadowHost)> = hosts.into_iter().collect();
    sorted_hosts.sort_by(|(a, _), (b, _)| a.cmp(b));
    let sorted_hosts_map: HashMap<String, ShadowHost> = sorted_hosts.into_iter().collect();

    // Create final Shadow configuration
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            // Force to 1h as requested if longer than 1h
            stop_time: if config.general.stop_time.ends_with('h') || config.general.stop_time.ends_with('m') {
                "1h".to_string()
            } else {
                "1h".to_string()
            },
            model_unblocked_syscall_latency: true,
            log_level: config.general.log_level.clone().unwrap_or("trace".to_string()),
        },
        experimental: ShadowExperimental {
            runahead: None,
            use_dynamic_runahead: true,
        },
        network: ShadowNetwork {
            graph: ShadowGraph {
                graph_type: config.network.as_ref().map_or("1_gbit_switch".to_string(), |n| n.network_type.clone()),
            },
        },
        hosts: sorted_hosts_map,
    };

    // Write configuration
    let config_yaml = serde_yaml::to_string(&shadow_config)?;
    std::fs::write(output_path, config_yaml)?;

    println!("Generated Agent-based Shadow configuration at {:?}", output_path);
    println!("  - Simulation time: {}", config.general.stop_time);
    println!("  - Total hosts: {}", shadow_config.hosts.len());
    println!("  - Agent registry created at {:?}", agent_registry_path);

    Ok(())
}
