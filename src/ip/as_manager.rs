//! Autonomous System (AS) management.
//!
//! This file handles AS-aware IP allocation for GML-based network topologies,
//! ensuring agents are distributed appropriately across autonomous systems
//! according to the network topology.
//!
//! ## Why AS Numbers Are Remapped
//!
//! The GML topology uses synthetic AS numbers (0 to N-1) remapped from real Internet
//! AS numbers. Real AS numbers (e.g., Google AS 15169, Cloudflare AS 13335) range
//! from small values to 400,000+ with large gaps between them. We remap because:
//!
//! 1. **Shadow requires contiguous node IDs** - The network simulator needs sequential
//!    node IDs for efficient graph traversal and memory management.
//! 2. **Real AS numbers are sparse** - There are huge gaps between AS numbers
//!    (e.g., 3, 4, 12, 16, 24... 397695), making array indexing impractical.
//! 3. **Simplifies region mapping** - We can divide the 0-N range proportionally
//!    across geographic regions without needing external AS-to-country databases.
//!
//! ## IP Allocation Scheme
//!
//! - Uses the 10.0.0.0/8 private range (16 million IPs)
//! - Each AS gets its own /24 subnet with up to 254 hosts
//! - AS number maps deterministically to subnet: 10.{AS/256}.{AS%256}.{host}
//! - This supports up to 65,536 ASes with 254 hosts each
//!
//! ## Geographic Distribution
//!
//! Synthetic AS numbers are divided proportionally into 6 regions. The default
//! proportions roughly match real Internet AS distribution:
//!
//! | Region         | Proportion | Example (1200 nodes) |
//! |----------------|------------|----------------------|
//! | North America  | 16.67%     | AS 0-199             |
//! | Europe         | 25.00%     | AS 200-499           |
//! | Asia           | 25.00%     | AS 500-799           |
//! | South America  | 16.67%     | AS 800-999           |
//! | Africa         | 8.33%      | AS 1000-1099         |
//! | Oceania        | 8.33%      | AS 1100-1199         |

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

    /// Get the index of this region (0-5) for array indexing
    pub fn index(&self) -> usize {
        match self {
            AsRegion::NorthAmerica => 0,
            AsRegion::Europe => 1,
            AsRegion::Asia => 2,
            AsRegion::SouthAmerica => 3,
            AsRegion::Africa => 4,
            AsRegion::Oceania => 5,
            AsRegion::Unknown => 6,
        }
    }

    /// Get all regions in order (excluding Unknown)
    pub fn all() -> [AsRegion; 6] {
        [
            AsRegion::NorthAmerica,
            AsRegion::Europe,
            AsRegion::Asia,
            AsRegion::SouthAmerica,
            AsRegion::Africa,
            AsRegion::Oceania,
        ]
    }
}

/// Region boundary information: (region, start_node, end_node)
pub type RegionBoundary = (AsRegion, usize, usize);

/// Default proportions for each region (sum to 100.0)
/// These roughly match real Internet AS geographic distribution
pub const DEFAULT_REGION_PROPORTIONS: [(AsRegion, f64); 6] = [
    (AsRegion::NorthAmerica, 16.67),
    (AsRegion::Europe, 25.0),
    (AsRegion::Asia, 25.0),
    (AsRegion::SouthAmerica, 16.67),
    (AsRegion::Africa, 8.33),
    (AsRegion::Oceania, 8.33),
];

/// Calculate region boundaries proportionally for any topology size.
///
/// This function divides the node range 0..total_nodes into 6 geographic
/// regions based on the default proportions. This allows the same distribution
/// logic to work with GML topologies of any size (30, 150, 1200, etc.).
///
/// # Arguments
/// * `total_nodes` - Total number of nodes in the GML topology
///
/// # Returns
/// Array of 6 region boundaries, each containing (region, start_node, end_node)
///
/// # Example
/// ```
/// let boundaries = calculate_region_boundaries(1200);
/// // boundaries[0] = (NorthAmerica, 0, 199)    // ~16.67% of 1200
/// // boundaries[1] = (Europe, 200, 499)        // ~25% of 1200
/// // etc.
/// ```
pub fn calculate_region_boundaries(total_nodes: usize) -> [RegionBoundary; 6] {
    let mut boundaries: [RegionBoundary; 6] = [
        (AsRegion::NorthAmerica, 0, 0),
        (AsRegion::Europe, 0, 0),
        (AsRegion::Asia, 0, 0),
        (AsRegion::SouthAmerica, 0, 0),
        (AsRegion::Africa, 0, 0),
        (AsRegion::Oceania, 0, 0),
    ];

    if total_nodes == 0 {
        return boundaries;
    }

    let mut start = 0;
    for (i, (region, proportion)) in DEFAULT_REGION_PROPORTIONS.iter().enumerate() {
        let count = ((total_nodes as f64) * proportion / 100.0).round() as usize;
        let end = if i == 5 {
            // Last region gets all remaining nodes to avoid rounding errors
            total_nodes.saturating_sub(1)
        } else {
            (start + count).saturating_sub(1).min(total_nodes.saturating_sub(1))
        };
        boundaries[i] = (*region, start, end);
        start = end + 1;
    }

    boundaries
}

/// Get the region for a node ID given the total topology size.
/// This is the dynamic version that works with any topology size.
pub fn get_region_for_node(node_id: usize, total_nodes: usize) -> AsRegion {
    let boundaries = calculate_region_boundaries(total_nodes);
    for (region, start, end) in boundaries {
        if node_id >= start && node_id <= end {
            return region;
        }
    }
    AsRegion::Unknown
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
    /// Maps AS numbers to region-appropriate IP ranges to simulate a realistic
    /// global Internet with diverse IP addresses:
    ///
    /// - North America (AS 0-199):     10.x.x.x or 192.168.x.x
    /// - Europe (AS 200-499):          172.16-31.x.x
    /// - Asia (AS 500-799):            203.x.x.x
    /// - South America (AS 800-999):   200.x.x.x
    /// - Africa (AS 1000-1099):        197.x.x.x
    /// - Oceania (AS 1100-1199):       202.x.x.x
    ///
    /// Each AS gets its own /24 subnet within its region's IP range.
    pub fn get_subnet_base(as_number: &str) -> Option<String> {
        let as_num = Self::parse_as_number(as_number)?;
        let region = AsRegion::from_as_number(as_num);

        // Calculate offset within the region for subnet variation
        let region_offset = match region {
            AsRegion::NorthAmerica => as_num,                    // 0-199
            AsRegion::Europe => as_num.saturating_sub(200),       // 0-299
            AsRegion::Asia => as_num.saturating_sub(500),         // 0-299
            AsRegion::SouthAmerica => as_num.saturating_sub(800), // 0-199
            AsRegion::Africa => as_num.saturating_sub(1000),      // 0-99
            AsRegion::Oceania => as_num.saturating_sub(1100),     // 0-99
            AsRegion::Unknown => as_num,
        };

        // Map to region-appropriate IP ranges based on real RIR allocations
        // Each region cycles through multiple first octets for diversity
        let offset = region_offset as usize;  // Convert to usize for array indexing
        let subnet = match region {
            AsRegion::NorthAmerica => {
                // ARIN allocations per IANA registry
                // Source: https://www.iana.org/assignments/ipv4-address-space
                const NA_OCTETS: [u8; 20] = [
                    3, 4, 6, 7, 8, 9, 13, 15, 16, 18,
                    20, 23, 24, 50, 63, 64, 65, 66, 67, 68
                ];
                let first = NA_OCTETS[offset % NA_OCTETS.len()];
                let second = (offset / NA_OCTETS.len()) % 256;
                let third = (offset / (NA_OCTETS.len() * 256)) % 256;
                format!("{}.{}.{}", first, second, third)
            }
            AsRegion::Europe => {
                // RIPE NCC allocations per IANA registry
                // Source: https://www.iana.org/assignments/ipv4-address-space
                const EU_OCTETS: [u8; 20] = [
                    2, 5, 25, 31, 37, 46, 51, 62, 77, 78,
                    79, 80, 81, 82, 83, 84, 85, 86, 87, 88
                ];
                let first = EU_OCTETS[offset % EU_OCTETS.len()];
                let second = (offset / EU_OCTETS.len()) % 256;
                let third = (offset / (EU_OCTETS.len() * 256)) % 256;
                format!("{}.{}.{}", first, second, third)
            }
            AsRegion::Asia => {
                // APNIC allocations per IANA registry
                // Source: https://www.iana.org/assignments/ipv4-address-space
                const ASIA_OCTETS: [u8; 20] = [
                    1, 14, 27, 36, 39, 42, 43, 49, 58, 59,
                    60, 61, 101, 103, 110, 111, 112, 113, 114, 115
                ];
                let first = ASIA_OCTETS[offset % ASIA_OCTETS.len()];
                let second = (offset / ASIA_OCTETS.len()) % 256;
                let third = (offset / (ASIA_OCTETS.len() * 256)) % 256;
                format!("{}.{}.{}", first, second, third)
            }
            AsRegion::SouthAmerica => {
                // LACNIC allocations per IANA registry
                // Source: https://www.iana.org/assignments/ipv4-address-space
                const SA_OCTETS: [u8; 10] = [
                    177, 179, 181, 186, 187, 189, 190, 191, 200, 201
                ];
                let first = SA_OCTETS[offset % SA_OCTETS.len()];
                let second = (offset / SA_OCTETS.len()) % 256;
                let third = (offset / (SA_OCTETS.len() * 256)) % 256;
                format!("{}.{}.{}", first, second, third)
            }
            AsRegion::Africa => {
                // AFRINIC allocations per IANA registry
                // Source: https://www.iana.org/assignments/ipv4-address-space
                const AF_OCTETS: [u8; 6] = [41, 102, 105, 154, 196, 197];
                let first = AF_OCTETS[offset % AF_OCTETS.len()];
                let second = (offset / AF_OCTETS.len()) % 256;
                let third = (offset / (AF_OCTETS.len() * 256)) % 256;
                format!("{}.{}.{}", first, second, third)
            }
            AsRegion::Oceania => {
                // APNIC/Oceania allocations per IANA registry
                // Source: https://www.iana.org/assignments/ipv4-address-space
                const OC_OCTETS: [u8; 8] = [101, 103, 121, 122, 139, 144, 202, 203];
                let first = OC_OCTETS[offset % OC_OCTETS.len()];
                let second = (offset / OC_OCTETS.len()) % 256;
                let third = (offset / (OC_OCTETS.len() * 256)) % 256;
                format!("{}.{}.{}", first, second, third)
            }
            AsRegion::Unknown => {
                // Fallback to diverse range
                let as_usize = as_num as usize;
                format!("{}.{}.{}",
                    100 + (as_usize % 50),
                    (as_usize / 50) % 256,
                    (as_usize / (50 * 256)) % 256
                )
            }
        };

        Some(subnet)
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
