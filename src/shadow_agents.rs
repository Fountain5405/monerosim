use crate::config::Config;
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;

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
fn create_agent_command(current_dir: &str, agent_script: &str, args: &str) -> String {
    // Remove .py extension if present for module execution
    let module_name = agent_script.trim_end_matches(".py");
    format!(
        "-c 'cd {} && . ./venv/bin/activate && python3 -m agents.{} {}'",
        current_dir, module_name, args
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
            "--regtest".to_string(),
            format!("--p2p-bind-ip={}", node_ip),
            format!("--p2p-bind-port={}", node_port),
            "--fixed-difficulty=200".to_string(),
            "--allow-local-ip".to_string(),
        ];
        
        // Add connections to seed nodes
        if i > 0 {
            daemon_args.push("--add-priority-node=11.0.0.1:28080".to_string());
            daemon_args.push("--add-priority-node=11.0.0.2:28080".to_string());
        }
        
        let monerod_path = std::fs::canonicalize("monerod")
            .expect("Failed to resolve absolute path to monerod")
            .to_string_lossy()
            .to_string();
            
        processes.push(ShadowProcess {
            path: monerod_path,
            args: daemon_args.join(" "),
            environment: monero_environment.clone(),
            start_time: format!("{}s", i * 2), // Stagger daemon starts
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
                "-c 'mkdir -p /tmp/{}_wallet && {} {}'",
                user_id, wallet_path, wallet_args
            ),
            environment: environment.clone(),
            start_time: format!("{}s", 30 + i * 2), // Start wallets after daemons
        });
        
        // 3. Regular user agent
        let agent_args = format!(
            "--id {} --node-rpc {} --wallet-rpc {} --tx-frequency {} --rpc-host {}",
            user_id, node_rpc_port, wallet_rpc_port, agent_config.transaction_frequency, node_ip
        );
        
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: create_agent_command(&current_dir, "regular_user.py", &agent_args),
            environment: environment.clone(),
            start_time: format!("{}s", 60 + i * 2), // Start agents after wallets
        });
        
        // Create host with all processes
        hosts.insert(user_id, ShadowHost {
            network_node_id: 0,
            ip_addr: Some(node_ip),
            processes,
        });
        
        next_ip += 1; // One IP per user (all processes share the same IP)
    }
    
    // 2. Create Marketplaces (wallet only + agent)
    for i in 0..agent_config.marketplaces {
        let marketplace_id = format!("marketplace{:03}", i);
        let marketplace_ip = format!("11.0.0.{}", next_ip);
        let wallet_rpc_port = 29000 + (i * 10) as u16;
        
        let mut processes = Vec::new();
        
        // Marketplace wallet (connects to first user's daemon)
        let wallet_path = std::fs::canonicalize("monero-wallet-rpc")
            .expect("Failed to resolve absolute path to monero-wallet-rpc")
            .to_string_lossy()
            .to_string();
            
        let wallet_args = format!(
            "--daemon-address=11.0.0.10:28090 --rpc-bind-port={} --rpc-bind-ip={} \
             --disable-rpc-login --trusted-daemon --log-level=1 \
             --wallet-dir=/tmp/{}_wallet --non-interactive --confirm-external-bind \
             --allow-mismatched-daemon-version --max-concurrency=1 \
             --daemon-ssl-allow-any-cert",
            wallet_rpc_port, marketplace_ip, marketplace_id
        );
        
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!(
                "-c 'mkdir -p /tmp/{}_wallet && {} {}'",
                marketplace_id, wallet_path, wallet_args
            ),
            environment: environment.clone(),
            start_time: "45s".to_string(),
        });
        
        // Marketplace agent
        let agent_args = format!(
            "--id {} --wallet-rpc {} --rpc-host {}",
            marketplace_id, wallet_rpc_port, marketplace_ip
        );
        
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: create_agent_command(&current_dir, "marketplace.py", &agent_args),
            environment: environment.clone(),
            start_time: "75s".to_string(),
        });
        
        hosts.insert(marketplace_id, ShadowHost {
            network_node_id: 0,
            ip_addr: Some(marketplace_ip),
            processes,
        });
        
        next_ip += 1;
    }
    
    // 3. Create Mining Pools (mining-enabled daemon + agent)
    for i in 0..agent_config.mining_pools {
        let pool_id = format!("pool{}", if i == 0 { "alpha" } else { "beta" });
        let node_ip = format!("11.0.0.{}", next_ip);
        let node_port = 28080;
        let node_rpc_port = 29100 + (i * 10) as u16;
        
        let mut processes = Vec::new();
        
        // Mining-enabled daemon
        let daemon_args = vec![
            format!("--data-dir=/tmp/monero-{}", pool_id),
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
            "--regtest".to_string(),
            format!("--p2p-bind-ip={}", node_ip),
            format!("--p2p-bind-port={}", node_port),
            "--fixed-difficulty=100".to_string(), // Lower difficulty for mining pools
            "--allow-local-ip".to_string(),
            "--add-priority-node=11.0.0.1:28080".to_string(),
            "--add-priority-node=11.0.0.2:28080".to_string(),
        ];
        
        let monerod_path = std::fs::canonicalize("monerod")
            .expect("Failed to resolve absolute path to monerod")
            .to_string_lossy()
            .to_string();
            
        processes.push(ShadowProcess {
            path: monerod_path,
            args: daemon_args.join(" "),
            environment: monero_environment.clone(),
            start_time: format!("{}s", 5 + i * 5),
        });
        
        // Mining pool agent
        let agent_args = format!(
            "--id {} --node-rpc {} --mining-threads 1 --rpc-host {}",
            pool_id, node_rpc_port, node_ip
        );
        
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: create_agent_command(&current_dir, "mining_pool.py", &agent_args),
            environment: environment.clone(),
            start_time: format!("{}s", 40 + i * 5),
        });
        
        hosts.insert(pool_id, ShadowHost {
            network_node_id: 0,
            ip_addr: Some(node_ip),
            processes,
        });
        
        next_ip += 1;
    }
    
    // 4. Add Block Controller Agent
    let block_controller_process = ShadowProcess {
        path: "/bin/bash".to_string(),
        args: create_agent_command(&current_dir, "block_controller.py", "--interval 120 --blocks 1"),
        environment: environment.clone(),
        start_time: "90s".to_string(),
    };
    
    hosts.insert("blockcontroller".to_string(), ShadowHost {
        network_node_id: 0,
        ip_addr: None,
        processes: vec![block_controller_process],
    });
    
    // 5. Add monitoring scripts (optional)
    let monitor_process = ShadowProcess {
        path: "/bin/bash".to_string(),
        args: create_agent_command(&current_dir, "../scripts/monitor.py", ""),
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