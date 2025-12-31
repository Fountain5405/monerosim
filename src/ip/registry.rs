//! IP address registry.
//!
//! This file manages a registry of allocated IP addresses to ensure
//! uniqueness and track which addresses are assigned to which agents
//! in the simulation.

use std::collections::{HashMap, HashSet};

/// Agent type classification for IP allocation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AgentType {
    UserAgent,
    BlockController,
    PureScriptAgent,
    Infrastructure,  // DNS servers, monitors, and other infrastructure agents
}

/// Subnet allocation configuration
#[derive(Debug)]
pub struct SubnetAllocation {
    pub base_subnet: String,
    pub start_ip: u8,
    pub end_ip: u8,
    pub spacing: u8, // Minimum spacing between agent types
}

/// Global IP Registry for centralized IP management across all agent types
#[derive(Debug)]
pub struct GlobalIpRegistry {
    /// Tracks all assigned IP addresses to prevent collisions
    assigned_ips: HashMap<String, String>, // IP -> Agent ID
    /// Fast lookup for IP uniqueness checking
    used_ips: HashSet<String>,
    /// Next available IP counters for each subnet
    subnet_counters: HashMap<String, u8>,
}

impl GlobalIpRegistry {
    pub fn new() -> Self {
        let mut subnet_counters = HashMap::new();

        // Initialize counters for the base subnet
        subnet_counters.insert("192.168".to_string(), 10);

        GlobalIpRegistry {
            assigned_ips: HashMap::new(),
            used_ips: HashSet::new(),
            subnet_counters,
        }
    }

    /// Assign a unique IP address for the given agent type and ID
    /// Distributes agents across different IP ranges to simulate global internet distribution
    pub fn assign_ip(&mut self, _agent_type: AgentType, agent_id: &str) -> Result<String, String> {
        // Extract numeric part from agent_id (e.g., "user005" -> 5)
        let agent_number = if let Some(num_str) = agent_id.strip_prefix("user") {
            num_str.parse::<u32>().unwrap_or(0)
        } else if let Some(num_str) = agent_id.strip_prefix("script") {
            100 + num_str.parse::<u32>().unwrap_or(0) // Offset script agents
        } else {
            // For blockcontroller and other special cases
            match agent_id {
                "blockcontroller" => 200,
                _ => 0,
            }
        };

        // Global IP distribution - simulate different geographic regions across multiple /16 subnets
        // North America: 10.x.x.x, 192.168.x.x
        // Europe: 172.16-31.x.x
        // Asia: 203.x.x.x
        // South America: 200.x.x.x
        // Africa: 197.x.x.x
        // Oceania: 202.x.x.x

        let region = agent_number % 6;
        let subnet_offset = agent_number / 6;
        let (octet1, octet2, _region_name) = match region {
            0 => (10, subnet_offset % 256, "North America"),          // 10.x.x.x (/16 subnets)
            1 => (172, 16 + (subnet_offset % 16), "Europe"),          // 172.16-31.x.x (/16 subnets)
            2 => (203, subnet_offset % 256, "Asia"),                  // 203.x.x.x (/16 subnets)
            3 => (200, subnet_offset % 256, "South America"),         // 200.x.x.x (/16 subnets)
            4 => (197, subnet_offset % 256, "Africa"),                // 197.x.x.x (/16 subnets)
            5 => (202, subnet_offset % 256, "Oceania"),               // 202.x.x.x (/16 subnets)
            _ => (10, 0, "Default"),
        };

        // For North America, also use 192.168.x.x range occasionally
        let (final_octet1, final_octet2) = if octet1 == 10 && (agent_number % 12) == 0 {
            (192, 168) // Occasionally use 192.168.x.x for North America
        } else {
            (octet1, octet2)
        };

        // Create unique subnet and host
        let subnet_octet3 = agent_number % 256;
        let host_octet4 = 10 + (agent_number / 256) % 246; // Keep host part in valid range

        let ip = format!("{}.{}.{}.{}", final_octet1, final_octet2, subnet_octet3, host_octet4);

        // Check if this IP is already assigned using HashSet for fast lookup
        if !self.used_ips.contains(&ip) {
            self.used_ips.insert(ip.clone());
            self.assigned_ips.insert(ip.clone(), agent_id.to_string());
            Ok(ip)
        } else {
            // Check if it's assigned to the same agent (shouldn't happen with HashSet, but being safe)
            if self.assigned_ips.get(&ip) == Some(&agent_id.to_string()) {
                Ok(ip)
            } else {
                // Fallback: try a different host IP
                let fallback_ip = format!("{}.{}.{}.{}", final_octet1, final_octet2, subnet_octet3, host_octet4 + 100);
                if !self.used_ips.contains(&fallback_ip) {
                    self.used_ips.insert(fallback_ip.clone());
                    self.assigned_ips.insert(fallback_ip.clone(), agent_id.to_string());
                    Ok(fallback_ip)
                } else {
                    Err(format!("Could not assign unique IP for agent {}", agent_id))
                }
            }
        }
    }

    /// Check if an IP is already assigned (fast HashSet lookup)
    pub fn is_ip_assigned(&self, ip: &str) -> bool {
        self.used_ips.contains(ip)
    }

    /// Register a pre-allocated IP from GML file
    pub fn register_pre_allocated_ip(&mut self, ip: &str, agent_id: &str) -> Result<(), String> {
        if self.used_ips.contains(ip) {
            if let Some(existing_agent) = self.assigned_ips.get(ip) {
                if existing_agent != agent_id {
                    return Err(format!("IP {} already assigned to agent {}", ip, existing_agent));
                }
            }
            // If same agent, it's OK
            Ok(())
        } else {
            self.used_ips.insert(ip.to_string());
            self.assigned_ips.insert(ip.to_string(), agent_id.to_string());
            Ok(())
        }
    }

    /// Get the agent ID that owns a given IP
    pub fn get_agent_for_ip(&self, ip: &str) -> Option<&String> {
        self.assigned_ips.get(ip)
    }

    /// Get all assigned IPs for debugging
    pub fn get_all_assigned_ips(&self) -> &HashMap<String, String> {
        &self.assigned_ips
    }

    /// Get statistics about IP allocation
    pub fn get_allocation_stats(&self) -> HashMap<String, usize> {
        let mut stats = HashMap::new();
        for (subnet, _) in &self.subnet_counters {
            let count = self.assigned_ips.keys()
                .filter(|ip| ip.starts_with(&format!("{}.", subnet)))
                .count();
            stats.insert(subnet.clone(), count);
        }
        stats
    }
}
