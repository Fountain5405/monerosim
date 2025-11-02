//! Autonomous System (AS) management.
//!
//! This file handles AS-aware IP allocation for GML-based network topologies,
//! ensuring agents are distributed appropriately across autonomous systems
//! according to the network topology.

use std::collections::HashMap;

/// Legacy AS-aware subnet manager for backward compatibility with GML topologies
#[derive(Debug)]
pub struct AsSubnetManager {
    subnet_counters: HashMap<String, u8>,
}

impl AsSubnetManager {
    pub fn new() -> Self {
        let mut subnet_counters = HashMap::new();
        subnet_counters.insert("65001".to_string(), 100); // Start from 192.168.100.x for AS 65001
        subnet_counters.insert("65002".to_string(), 100); // Start from 192.168.101.x for AS 65002
        subnet_counters.insert("65003".to_string(), 100); // Start from 192.168.102.x for AS 65003
        AsSubnetManager { subnet_counters }
    }

    /// Get the subnet base for an AS number
    pub fn get_subnet_base(as_number: &str) -> Option<&'static str> {
        match as_number {
            "65001" => Some("192.168.100"),
            "65002" => Some("192.168.101"),
            "65003" => Some("192.168.102"),
            _ => None,
        }
    }

    /// Assign IP address based on AS number
    pub fn assign_as_aware_ip(&mut self, as_number: &str) -> Option<String> {
        if let Some(subnet_base) = Self::get_subnet_base(as_number) {
            let counter = self.subnet_counters.get_mut(as_number)?;
            // Check if we've exhausted the subnet (255 is the max for IPv4 last octet)
            if *counter >= 255 {
                return None; // Subnet exhausted
            }
            let ip = format!("{}.{}", subnet_base, counter);
            *counter = counter.checked_add(1).unwrap_or(255); // Use checked_add to prevent overflow
            Some(ip)
        } else {
            None
        }
    }
}
