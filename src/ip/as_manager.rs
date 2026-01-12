//! Autonomous System (AS) management.
//!
//! This file handles AS-aware IP allocation for GML-based network topologies,
//! ensuring agents are distributed appropriately across autonomous systems
//! according to the network topology.
//!
//! IP Allocation Scheme:
//! - Uses the 10.0.0.0/8 private range (16 million IPs)
//! - Each AS gets its own /24 subnet with up to 254 hosts
//! - AS number maps deterministically to subnet: 10.{AS/256}.{AS%256}.{host}
//! - This supports up to 65,536 ASes with 254 hosts each
//!
//! Geographic Distribution (simulated via AS ranges):
//! - AS 0-199:     "North America"  -> 10.0-0.0-199.x
//! - AS 200-499:   "Europe"         -> 10.0-1.200-255, 10.1.0-243.x
//! - AS 500-799:   "Asia"           -> 10.1.244-255, 10.2-3.x.x
//! - AS 800-999:   "South America"  -> 10.3.32-231.x
//! - AS 1000-1099: "Africa"         -> 10.3.232-255, 10.4.0-75.x
//! - AS 1100-1199: "Oceania"        -> 10.4.76-175.x

use std::collections::HashMap;

/// Region classification for AS numbers (for logging/debugging)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AsRegion {
    NorthAmerica,
    Europe,
    Asia,
    SouthAmerica,
    Africa,
    Oceania,
    Unknown,
}

impl AsRegion {
    /// Classify an AS number into a geographic region (simulated)
    pub fn from_as_number(as_num: u32) -> Self {
        match as_num {
            0..=199 => AsRegion::NorthAmerica,
            200..=499 => AsRegion::Europe,
            500..=799 => AsRegion::Asia,
            800..=999 => AsRegion::SouthAmerica,
            1000..=1099 => AsRegion::Africa,
            1100..=1199 => AsRegion::Oceania,
            _ => AsRegion::Unknown,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            AsRegion::NorthAmerica => "North America",
            AsRegion::Europe => "Europe",
            AsRegion::Asia => "Asia",
            AsRegion::SouthAmerica => "South America",
            AsRegion::Africa => "Africa",
            AsRegion::Oceania => "Oceania",
            AsRegion::Unknown => "Unknown",
        }
    }
}

/// Dynamic AS-aware subnet manager for GML topologies.
///
/// Handles any AS number by mapping it to a unique /24 subnet in the 10.0.0.0/8 range.
#[derive(Debug)]
pub struct AsSubnetManager {
    /// Maps AS number string to next available host number (1-254)
    host_counters: HashMap<String, u8>,
    /// Statistics for logging
    assignments_per_region: HashMap<AsRegion, u32>,
}

impl AsSubnetManager {
    pub fn new() -> Self {
        AsSubnetManager {
            host_counters: HashMap::new(),
            assignments_per_region: HashMap::new(),
        }
    }

    /// Parse AS number string to u32
    fn parse_as_number(as_str: &str) -> Option<u32> {
        as_str.parse::<u32>().ok()
    }

    /// Get the /24 subnet base for an AS number.
    ///
    /// Maps AS number to 10.{high_byte}.{low_byte} where:
    /// - high_byte = AS / 256 (0-255)
    /// - low_byte = AS % 256 (0-255)
    ///
    /// This gives each AS its own /24 subnet (up to 254 hosts).
    pub fn get_subnet_base(as_number: &str) -> Option<String> {
        let as_num = Self::parse_as_number(as_number)?;

        // Map AS number to subnet: 10.{AS/256}.{AS%256}
        let high_byte = (as_num / 256) as u8;
        let low_byte = (as_num % 256) as u8;

        Some(format!("10.{}.{}", high_byte, low_byte))
    }

    /// Assign an IP address based on AS number.
    ///
    /// Returns a unique IP within the AS's /24 subnet.
    /// Host addresses start at 10 to avoid reserved addresses (0, 1 for gateway, etc.)
    pub fn assign_as_aware_ip(&mut self, as_number: &str) -> Option<String> {
        let subnet_base = Self::get_subnet_base(as_number)?;

        // Get or initialize the host counter for this AS (start at 10)
        let counter = self.host_counters.entry(as_number.to_string()).or_insert(10);

        // Check if we've exhausted the subnet (max 254 for last octet)
        if *counter >= 255 {
            log::warn!("AS {} subnet exhausted (254 hosts assigned)", as_number);
            return None;
        }

        let ip = format!("{}.{}", subnet_base, counter);
        *counter = counter.saturating_add(1);

        // Track statistics
        if let Some(as_num) = Self::parse_as_number(as_number) {
            let region = AsRegion::from_as_number(as_num);
            *self.assignments_per_region.entry(region).or_insert(0) += 1;
        }

        Some(ip)
    }

    /// Get the geographic region for an AS number
    pub fn get_region(&self, as_number: &str) -> AsRegion {
        Self::parse_as_number(as_number)
            .map(AsRegion::from_as_number)
            .unwrap_or(AsRegion::Unknown)
    }

    /// Get statistics about IP assignments
    pub fn get_stats(&self) -> String {
        let total: u32 = self.assignments_per_region.values().sum();
        let mut stats = format!("AS Subnet Manager Stats: {} total IPs assigned\n", total);

        for region in [
            AsRegion::NorthAmerica,
            AsRegion::Europe,
            AsRegion::Asia,
            AsRegion::SouthAmerica,
            AsRegion::Africa,
            AsRegion::Oceania,
            AsRegion::Unknown,
        ] {
            if let Some(&count) = self.assignments_per_region.get(&region) {
                if count > 0 {
                    stats.push_str(&format!("  {}: {} IPs\n", region.name(), count));
                }
            }
        }

        stats.push_str(&format!("  Unique ASes used: {}\n", self.host_counters.len()));
        stats
    }

    /// Get the number of unique ASes that have been assigned IPs
    pub fn unique_as_count(&self) -> usize {
        self.host_counters.len()
    }
}

impl Default for AsSubnetManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_subnet_base_calculation() {
        // AS 0 -> 10.0.0
        assert_eq!(AsSubnetManager::get_subnet_base("0"), Some("10.0.0".to_string()));

        // AS 1 -> 10.0.1
        assert_eq!(AsSubnetManager::get_subnet_base("1"), Some("10.0.1".to_string()));

        // AS 255 -> 10.0.255
        assert_eq!(AsSubnetManager::get_subnet_base("255"), Some("10.0.255".to_string()));

        // AS 256 -> 10.1.0
        assert_eq!(AsSubnetManager::get_subnet_base("256"), Some("10.1.0".to_string()));

        // AS 1199 -> 10.4.175 (1199 / 256 = 4, 1199 % 256 = 175)
        assert_eq!(AsSubnetManager::get_subnet_base("1199"), Some("10.4.175".to_string()));

        // AS 65535 -> 10.255.255
        assert_eq!(AsSubnetManager::get_subnet_base("65535"), Some("10.255.255".to_string()));
    }

    #[test]
    fn test_ip_assignment() {
        let mut manager = AsSubnetManager::new();

        // First agent in AS 0
        let ip1 = manager.assign_as_aware_ip("0").unwrap();
        assert_eq!(ip1, "10.0.0.10");

        // Second agent in AS 0
        let ip2 = manager.assign_as_aware_ip("0").unwrap();
        assert_eq!(ip2, "10.0.0.11");

        // First agent in AS 1
        let ip3 = manager.assign_as_aware_ip("1").unwrap();
        assert_eq!(ip3, "10.0.1.10");

        // First agent in AS 500 (Asia region)
        let ip4 = manager.assign_as_aware_ip("500").unwrap();
        assert_eq!(ip4, "10.1.244.10");
    }

    #[test]
    fn test_region_classification() {
        assert_eq!(AsRegion::from_as_number(0), AsRegion::NorthAmerica);
        assert_eq!(AsRegion::from_as_number(199), AsRegion::NorthAmerica);
        assert_eq!(AsRegion::from_as_number(200), AsRegion::Europe);
        assert_eq!(AsRegion::from_as_number(500), AsRegion::Asia);
        assert_eq!(AsRegion::from_as_number(800), AsRegion::SouthAmerica);
        assert_eq!(AsRegion::from_as_number(1000), AsRegion::Africa);
        assert_eq!(AsRegion::from_as_number(1100), AsRegion::Oceania);
        assert_eq!(AsRegion::from_as_number(5000), AsRegion::Unknown);
    }

    #[test]
    fn test_stats() {
        let mut manager = AsSubnetManager::new();

        // Assign IPs across different regions
        manager.assign_as_aware_ip("0");   // North America
        manager.assign_as_aware_ip("50");  // North America
        manager.assign_as_aware_ip("200"); // Europe
        manager.assign_as_aware_ip("500"); // Asia

        assert_eq!(manager.unique_as_count(), 4);

        let stats = manager.get_stats();
        assert!(stats.contains("North America: 2"));
        assert!(stats.contains("Europe: 1"));
        assert!(stats.contains("Asia: 1"));
    }
}
