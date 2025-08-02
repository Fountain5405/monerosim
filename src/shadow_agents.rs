use crate::config_v2::Config;
use rand::seq::SliceRandom;
use serde_json;
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;

#[derive(serde::Serialize, Debug)]
struct MinerInfo {
    ip_addr: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    wallet_address: Option<String>,
    weight: u32,
    is_solo_miner: bool,
}

#[derive(serde::Serialize, Debug)]
struct MinerRegistry {
    miners: Vec<MinerInfo>,
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

/// Agent configuration for the simulation
#[derive(Debug)]
pub struct AgentConfig {
    pub regular_users: u32,
    pub marketplaces: u32,
    pub mining_pools: u32,
    pub transaction_frequency: f64,
    pub min_transaction_amount: f64,
    pub max_transaction_amount: f64,
}

impl Default for AgentConfig {
    fn default() -> Self {
        AgentConfig {
            regular_users: 10,
            marketplaces: 2,
            mining_pools: 2,
            transaction_frequency: 0.1,
            min_transaction_amount: 0.1,
            max_transaction_amount: 1.0,
        }
    }
}

/// Helper function to create a Python agent command
fn create_agent_command(current_dir: &str, agent_module: &str, args: &[String]) -> String {
    format!(
        "-c 'cd {} && . ./venv/bin/activate && python3 -m {} {}'",
        current_dir, agent_module, args.join(" ")
    )
}

/// Generate a Shadow configuration with agent support
pub fn generate_agent_shadow_config(
    config: &Config, 
    agent_config: &AgentConfig,
    output_dir: &Path
) -> color_eyre::eyre::Result<()> {
    let current_dir = std::env::current_dir()
        .expect("Failed to get current directory")
        .to_string_lossy()
        .to_string();

    let mut hosts: HashMap<String, ShadowHost> = HashMap::new();

    // Common environment variables
    let environment: HashMap<String, String> = [
        ("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string()),
        ("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string()),
        ("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string()),
        ("MALLOC_ARENA_MAX".to_string(), "1".to_string()),
    ].iter().cloned().collect();

    // Monero-specific environment variables
    let mut monero_environment = environment.clone();
    monero_environment.insert("MONERO_BLOCK_SYNC_SIZE".to_string(), "1".to_string());
    monero_environment.insert("MONERO_DISABLE_DNS".to_string(), "1".to_string());
    monero_environment.insert("MONERO_MAX_CONNECTIONS_PER_IP".to_string(), "20".to_string());

    // Base IP allocation
    let mut next_ip = 10;  // Start from 11.0.0.10

    // 1. Create Regular Users with their daemons, wallets, and agents
    for i in 0..agent_config.regular_users {
        let user_id = format!("user{:03}", i);
        let node_ip = format!("11.0.0.{}", next_ip);
        let node_port = 28080;
        let node_rpc_port = 28090 + (i * 10) as u16;
        let wallet_rpc_port = node_rpc_port + 1;
        let p2p_port = 28080;
        
        // Create processes for this user
        let mut processes = Vec::new();
        
        // 1. Monero daemon
        let mut daemon_args = vec![
            format!("--data-dir=/tmp/monero-{}", user_id),
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
            "--max-connections-per-ip=20".to_string(),
            "--limit-rate-up=1024".to_string(),
            "--limit-rate-down=1024".to_string(),
            "--block-sync-size=1".to_string(),
            format!("--rpc-bind-ip={}", node_ip),
            format!("--rpc-bind-port={}", node_rpc_port),
            "--confirm-external-bind".to_string(),
            "--disable-rpc-ban".to_string(),
            "--rpc-access-control-origins=*".to_string(),
            format!("--rpc-restricted-bind-port={}", node_rpc_port),
            "--regtest".to_string(),
            format!("--p2p-bind-ip={}", node_ip),
            format!("--p2p-bind-port={}", node_port),
            "--fixed-difficulty=200".to_string(),
            "--allow-local-ip".to_string(),
        ];
        
        // Add connections to seed nodes
        // All nodes should connect to the first two users as seed nodes for stability
        if i != 0 {
            daemon_args.push("--add-priority-node=11.0.0.10:28080".to_string());
        }
        if i != 1 && agent_config.regular_users > 1 {
            daemon_args.push("--add-priority-node=11.0.0.11:28080".to_string());
        }
        
        let monerod_path = std::fs::canonicalize("monerod")
            .expect("Failed to resolve absolute path to monerod")
            .to_string_lossy()
            .to_string();
            
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!(
                "-c 'rm -rf /tmp/monero-{} && {} {}'",
                user_id, monerod_path, daemon_args.join(" ")
            ),
            environment: monero_environment.clone(),
            start_time: format!("{}s", 5 + i * 2), // Start daemons first
        });
        
        // 2. Wallet RPC
        let wallet_path = std::fs::canonicalize("monero-wallet-rpc")
            .expect("Failed to resolve absolute path to monero-wallet-rpc")
            .to_string_lossy()
            .to_string();
            
        let wallet_args = format!(
            "--daemon-address={}:{} --rpc-bind-port={} --rpc-bind-ip={} \
             --disable-rpc-login --trusted-daemon --log-level=1 \
             --wallet-dir=/tmp/{}_wallet --non-interactive --confirm-external-bind \
             --allow-mismatched-daemon-version --max-concurrency=1 \
             --daemon-ssl-allow-any-cert",
            node_ip, node_rpc_port, wallet_rpc_port, node_ip, user_id
        );
        
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!(
                "-c 'rm -rf /tmp/{}_wallet && mkdir -p /tmp/{}_wallet && while ! nc -z {} {}; do echo \"Waiting for daemon at {}:{}...\"; sleep 2; done && {} {}'",
                user_id, user_id, node_ip, node_rpc_port, node_ip, node_rpc_port, wallet_path, wallet_args
            ),
            environment: environment.clone(),
            start_time: format!("{}s", 55 + i * 2), // Start wallets 5 seconds before agents
        });
        
        // 3. Regular user agent
        let mut agent_args = vec![
            format!("--id {}", user_id),
            format!("--shared-dir {}", output_dir.to_str().unwrap()),
            format!("--rpc-host {}", node_ip),
            format!("--node-rpc-port {}", node_rpc_port),
            format!("--wallet-rpc-port {}", wallet_rpc_port),
            format!("--p2p-port {}", p2p_port),
            format!("--log-level DEBUG"),
            format!("--tx-frequency {}", agent_config.transaction_frequency),
        ];
        
        // Check if this user should be a miner based on mining_distribution
        if let Some(mining_config) = &config.mining {
            if i < mining_config.number_of_mining_nodes {
                agent_args.push("--attributes mining".to_string());
                // Add hash rate for this miner
                if (i as usize) < mining_config.mining_distribution.len() {
                    let hash_rate = mining_config.mining_distribution[i as usize];
                    agent_args.push(format!("--hash-rate {}", hash_rate));
                }
            }
        }

        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: create_agent_command(&current_dir, "agents.regular_user", &agent_args),
            environment: environment.clone(),
            start_time: format!("{}s", 60 + i * 2), // Start agents after wallets
        });
        
        // Create host with all processes
        hosts.insert(user_id.clone(), ShadowHost {
            network_node_id: 0,
            ip_addr: Some(node_ip.clone()),
            processes,
        });

        
        next_ip += 1; // One IP per user (all processes share the same IP)
    }
    
    // Marketplace creation logic removed as per user request.
    
    // 3. Create Additional Nodes (formerly mining pools, now just regular nodes for network robustness)
    for i in 0..agent_config.mining_pools {
        let node_id = format!("node{:03}", i);
        let node_ip = format!("11.0.0.{}", next_ip);
        let node_port = 28080;
        let node_rpc_port = 29100 + (i * 10) as u16;
        
        let mut processes = Vec::new();
        
        // Regular daemon (no mining capabilities needed)
        let mut daemon_args = vec![
            format!("--data-dir=/tmp/monero-{}", node_id),
            "--log-file=/dev/stdout".to_string(),
            "--log-level=1".to_string(),
            "--simulation".to_string(),
            "--disable-dns-checkpoints".to_string(),
            "--out-peers=8".to_string(),
            "--in-peers=8".to_string(),
            "--disable-seed-nodes".to_string(),
            "--no-igd".to_string(),
            "--prep-blocks-threads=1".to_string(),
            "--max-concurrency=1".to_string(),
            "--no-zmq".to_string(),
            "--db-sync-mode=safe".to_string(),
            "--non-interactive".to_string(),
            "--max-connections-per-ip=20".to_string(),
            "--limit-rate-up=2048".to_string(),
            "--limit-rate-down=2048".to_string(),
            "--block-sync-size=1".to_string(),
            format!("--rpc-bind-ip={}", node_ip),
            format!("--rpc-bind-port={}", node_rpc_port),
            "--confirm-external-bind".to_string(),
            "--disable-rpc-ban".to_string(),
            "--rpc-access-control-origins=*".to_string(),
            format!("--rpc-restricted-bind-port={}", node_rpc_port),
            "--regtest".to_string(),
            format!("--p2p-bind-ip={}", node_ip),
            format!("--p2p-bind-port={}", node_port),
            "--fixed-difficulty=200".to_string(),
            "--allow-local-ip".to_string(),
            // Connect to actual user nodes
            "--add-priority-node=11.0.0.10:28080".to_string(),
        ];
        
        if agent_config.regular_users > 1 {
            daemon_args.push("--add-priority-node=11.0.0.11:28080".to_string());
        }
        
        let monerod_path = std::fs::canonicalize("monerod")
            .expect("Failed to resolve absolute path to monerod")
            .to_string_lossy()
            .to_string();
            
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!(
                "-c 'rm -rf /tmp/monero-{} && {} {}'",
                node_id, monerod_path, daemon_args.join(" ")
            ),
            environment: monero_environment.clone(),
            start_time: format!("{}s", 5 + i * 5), // Start daemons early (5s for first node, 10s for second, etc.)
        });
        
        // No agent needed for these additional nodes
        
        hosts.insert(node_id.clone(), ShadowHost {
            network_node_id: 0,
            ip_addr: Some(node_ip.clone()),
            processes,
        });

        
        next_ip += 1;
    }
    
    // 4. Add Block Controller with its own wallet
    let block_controller_id = "blockcontroller";
    let block_controller_ip = format!("11.0.0.{}", next_ip);
    let block_controller_wallet_port = 29200;
    let block_controller_daemon_port = 29100;
    
    let mut block_controller_processes = Vec::new();

    // Block controller wallet (connects to first user's daemon for simplicity)
    let wallet_path = std::fs::canonicalize("monero-wallet-rpc")
        .expect("Failed to resolve absolute path to monero-wallet-rpc")
        .to_string_lossy()
        .to_string();
        
    let wallet_args = format!(
        "--daemon-address=11.0.0.10:28090 --rpc-bind-port={} --rpc-bind-ip={} \
         --disable-rpc-login --trusted-daemon --log-level=1 \
         --wallet-dir=/tmp/{}_wallet --non-interactive --confirm-external-bind \
         --allow-mismatched-daemon-version --max-concurrency=1",
        block_controller_wallet_port, block_controller_ip, block_controller_id
    );
    
    block_controller_processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/{}_wallet && mkdir -p /tmp/{}_wallet && while ! nc -z 11.0.0.10 28090; do echo \"Waiting for daemon at 11.0.0.10:28090...\"; sleep 2; done && {} {}'",
            block_controller_id, block_controller_id, wallet_path, wallet_args
        ),
        environment: environment.clone(),
        start_time: "85s".to_string(), // Start 5 seconds before agent
    });
    
    // Block controller agent with wallet RPC info
    let agent_args = vec![
        "--id block_controller".to_string(),
        format!("--shared-dir {}", output_dir.to_str().unwrap()),
        format!("--rpc-host {}", block_controller_ip),
        format!("--wallet-rpc-port {}", block_controller_wallet_port),
        format!("--node-rpc-port 28090"),
        "--log-level DEBUG".to_string(),
    ];

    block_controller_processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: create_agent_command(&current_dir, "agents.block_controller", &agent_args),
        environment: environment.clone(),
        start_time: "90s".to_string(),
    });
    
    hosts.insert(block_controller_id.to_string(), ShadowHost {
        network_node_id: 0,
        ip_addr: Some(block_controller_ip),
        processes: block_controller_processes,
    });
    
    next_ip += 1;
    
    // 5. Add monitoring scripts (optional)
    let monitor_process = ShadowProcess {
        path: "/bin/bash".to_string(),
        args: create_agent_command(&current_dir, "scripts.monitor", &[]),
        environment: environment.clone(),
        start_time: "30s".to_string(),
    };
    
    hosts.insert("monitor".to_string(), ShadowHost {
        network_node_id: 0,
        ip_addr: None,
        processes: vec![monitor_process],
    });
    
    // Create final Shadow configuration
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
            model_unblocked_syscall_latency: true,
            log_level: "trace".to_string(),
        },
        experimental: ShadowExperimental {
            runahead: None,
            use_dynamic_runahead: true,
        },
        network: ShadowNetwork {
            graph: ShadowGraph {
                graph_type: "1_gbit_switch".to_string(),
            },
        },
        hosts,
    };
    
    // Step 6 has been removed to prevent race conditions. The agents themselves
    // will now be responsible for creating and managing the node_registry.json file.

    // Write configuration
    let shadow_config_path = output_dir.join("shadow_agents.yaml");
    let config_yaml = serde_yaml::to_string(&shadow_config)?;
    std::fs::write(&shadow_config_path, config_yaml)?;
    
    println!("Generated Agent-based Shadow configuration at {:?}", shadow_config_path);
    println!("  - Simulation time: {}", config.general.stop_time);
    println!("  - Regular users: {}", agent_config.regular_users);
    println!("  - Marketplaces: {}", agent_config.marketplaces);
    println!("  - Mining pools: {}", agent_config.mining_pools);
    println!("  - Total hosts: {}", shadow_config.hosts.len());
    
    Ok(())
}