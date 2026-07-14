//! IP address registry.
//!
//! This file manages a registry of allocated IP addresses to ensure
//! uniqueness and track which addresses are assigned to which agents
//! in the simulation.

use std::collections::{HashMap, HashSet};

/// First octet per geographic region for the dynamic/fallback IP path in
/// `assign_ip`, indexed by `agent_number % 6`
/// (0=NA, 1=Europe, 2=Asia, 3=South America, 4=Africa, 5=Oceania).
///
/// INVARIANT: every octet here MUST be absent from all of `as_manager.rs`'s
/// per-region octet tables (NA/EU/ASIA/SA/AF/OC_OCTETS) and distinct from each
/// other. The two IP-realism systems run side by side in GML+Dynamic mode; a
/// shared first octet lets them mint the same /24 for different agents (a
/// collision that today is silently diverted to a fallback host). Enforced by
/// the `region_octet_tables_are_pairwise_disjoint` test in `as_manager.rs`.
///
/// All octets are public (outside epee::is_ip_local's 10/8, 172.16/12,
/// 192.168/16) and avoid the /8s of Monero's hardcoded fallback seeds
/// (5, 37, 88, 176, 192.99), so no --allow-local-ip is needed and the
/// dedicated seed hosts never collide with these geographic assignments.
pub(crate) const REGISTRY_REGION_OCTETS: [u8; 6] = [72, 91, 116, 45, 156, 210];

/// Agent type classification for IP allocation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AgentType {
    UserAgent,
    MinerDistributor,
    PureScriptAgent,
    Infrastructure, // DNS servers, monitors, and other infrastructure agents
}

/// Global IP Registry for centralized IP management across all agent types
#[derive(Debug)]
pub struct GlobalIpRegistry {
    /// Tracks all assigned IP addresses to prevent collisions
    assigned_ips: HashMap<String, String>, // IP -> Agent ID
    /// Reverse lookup: agent_id -> IP. Lets `get_agent_ip()` find an IP that
    /// was pre-registered (e.g., a Monero fallback seed IP pinned to a
    /// specific agent before the main allocation loop runs).
    agent_to_ip: HashMap<String, String>,
    /// Fast lookup for IP uniqueness checking
    used_ips: HashSet<String>,
    /// Subnet group allocations: group_name -> (subnet_prefix, next_host)
    /// Each subnet group gets a unique /24 subnet in the 10.100.x.0 range
    subnet_groups: HashMap<String, (String, u8)>,
    /// Next available subnet ID for new groups
    next_subnet_group_id: u8,
}

impl GlobalIpRegistry {
    pub fn new() -> Self {
        GlobalIpRegistry {
            assigned_ips: HashMap::new(),
            agent_to_ip: HashMap::new(),
            used_ips: HashSet::new(),
            subnet_groups: HashMap::new(),
            next_subnet_group_id: 0,
        }
    }

    /// Look up the IP previously assigned to `agent_id`, if any.
    /// Used by `get_agent_ip()` Priority 0 to honor pre-registered pinnings.
    pub fn get_ip_for_agent(&self, agent_id: &str) -> Option<&String> {
        self.agent_to_ip.get(agent_id)
    }

    /// Assign a unique IP address for the given agent type and ID.
    /// Distributes agents across different IP ranges to simulate global
    /// internet distribution.
    ///
    /// agent_number assignment by ID prefix (collision-free ranges so
    /// agents in different categories don't fight for the same IP):
    ///   user-NNN          -> 0..999       (index = NNN)
    ///   miner-NNN         -> 1000..1999   (1000 + NNN)
    ///   relay-NNN         -> 2000..2999   (2000 + NNN)
    ///   script-NNN        -> 3000..3999   (3000 + NNN)
    ///   miner-distributor -> 50           (singleton)
    ///   simulation-monitor -> 51          (singleton)
    ///   everything else   -> 0            (will collide → fallback path)
    ///
    /// The trailing digit run is parsed regardless of separator so both
    /// `user-001` and `user001` work.
    pub fn assign_ip(&mut self, _agent_type: AgentType, agent_id: &str) -> Result<String, String> {
        fn trailing_num(s: &str) -> u32 {
            let digits: String = s.chars().rev().take_while(|c| c.is_ascii_digit()).collect();
            digits
                .chars()
                .rev()
                .collect::<String>()
                .parse()
                .unwrap_or(0)
        }

        let agent_number = if agent_id == "miner-distributor" {
            50
        } else if agent_id == "simulation-monitor" {
            51
        } else if agent_id.starts_with("user") {
            trailing_num(agent_id)
        } else if agent_id.starts_with("miner-") {
            1000 + trailing_num(agent_id)
        } else if agent_id.starts_with("relay-") {
            2000 + trailing_num(agent_id)
        } else if agent_id.starts_with("script") {
            3000 + trailing_num(agent_id)
        } else {
            0
        };

        // Global IP distribution - simulate different geographic regions across
        // multiple /16 subnets. The per-region first octet comes from
        // REGISTRY_REGION_OCTETS (see that const for the public-range and
        // disjoint-with-as_manager rationale):
        //   0 NA=72  1 EU=91  2 Asia=116  3 SA=45  4 Africa=156  5 Oceania=210
        let region = (agent_number % 6) as usize; // always 0..=5
        let subnet_offset = agent_number / 6;
        let octet1 = REGISTRY_REGION_OCTETS[region];
        let octet2 = subnet_offset % 256;

        // Create unique subnet and host
        let subnet_octet3 = agent_number % 256;
        let host_octet4 = 10 + (agent_number / 256) % 246; // Keep host part in valid range

        let ip = format!("{}.{}.{}.{}", octet1, octet2, subnet_octet3, host_octet4);

        // Check if this IP is already assigned using HashSet for fast lookup
        if !self.used_ips.contains(&ip) {
            self.used_ips.insert(ip.clone());
            self.assigned_ips.insert(ip.clone(), agent_id.to_string());
            self.agent_to_ip.insert(agent_id.to_string(), ip.clone());
            Ok(ip)
        } else {
            // Check if it's assigned to the same agent (shouldn't happen with HashSet, but being safe)
            if self.assigned_ips.get(&ip) == Some(&agent_id.to_string()) {
                Ok(ip)
            } else {
                // Fallback: try a different host IP in the same /24. host_octet4
                // is at most 254, so +100 can push the octet past 255 (an
                // invalid IPv4 octet). Reject rather than emit a malformed IP.
                let fallback_octet = host_octet4 + 100;
                if fallback_octet > 254 {
                    return Err(format!(
                        "Could not assign unique IP for agent {}: fallback host octet {} exceeds 254",
                        agent_id, fallback_octet
                    ));
                }
                let fallback_ip =
                    format!("{}.{}.{}.{}", octet1, octet2, subnet_octet3, fallback_octet);
                if !self.used_ips.contains(&fallback_ip) {
                    self.used_ips.insert(fallback_ip.clone());
                    self.assigned_ips
                        .insert(fallback_ip.clone(), agent_id.to_string());
                    self.agent_to_ip
                        .insert(agent_id.to_string(), fallback_ip.clone());
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
                    return Err(format!(
                        "IP {} already assigned to agent {}",
                        ip, existing_agent
                    ));
                }
            }
            // If same agent, it's OK
            Ok(())
        } else {
            self.used_ips.insert(ip.to_string());
            self.assigned_ips
                .insert(ip.to_string(), agent_id.to_string());
            self.agent_to_ip
                .insert(agent_id.to_string(), ip.to_string());
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

    /// Get statistics about IP allocation, grouped by first octet.
    pub fn get_allocation_stats(&self) -> HashMap<String, usize> {
        let mut stats: HashMap<String, usize> = HashMap::new();
        for ip in self.assigned_ips.keys() {
            if let Some(first_octet) = ip.split('.').next() {
                *stats.entry(format!("{}.x.x.x", first_octet)).or_insert(0) += 1;
            }
        }
        stats
    }

    /// Assign an IP address for an agent within a specific subnet group.
    /// All agents in the same subnet group will receive IPs from the same /24 subnet.
    /// This is useful for simulating Sybil attacks where an attacker's nodes share infrastructure.
    ///
    /// Subnet groups use 100.64.x.0/24 (RFC 6598 shared address space — public per
    /// epee::is_ip_local, so monerod doesn't need --allow-local-ip to peer with them).
    /// `x` is assigned sequentially.
    pub fn assign_subnet_group_ip(
        &mut self,
        subnet_group: &str,
        agent_id: &str,
    ) -> Result<String, String> {
        // Get or create subnet allocation for this group
        let (subnet_prefix, next_host) = self
            .subnet_groups
            .entry(subnet_group.to_string())
            .or_insert_with(|| {
                let subnet_id = self.next_subnet_group_id;
                self.next_subnet_group_id = self.next_subnet_group_id.wrapping_add(1);
                // RFC 6598 (CGNAT) — public per epee, plenty of /24 capacity.
                let prefix = format!("100.64.{}", subnet_id);
                log::info!(
                    "Created new subnet group '{}' with prefix {}.0/24",
                    subnet_group,
                    prefix
                );
                (prefix, 10) // Start host IPs at .10
            });

        // Allocate the next available IP in this subnet
        let host = *next_host;
        if host > 254 {
            return Err(format!(
                "Subnet group '{}' exhausted (max 245 hosts per /24)",
                subnet_group
            ));
        }

        let ip = format!("{}.{}", subnet_prefix, host);

        // Check for conflicts
        if self.used_ips.contains(&ip) {
            // Try to find next available
            for try_host in (host + 1)..=254 {
                let try_ip = format!("{}.{}", subnet_prefix, try_host);
                if !self.used_ips.contains(&try_ip) {
                    self.used_ips.insert(try_ip.clone());
                    self.assigned_ips
                        .insert(try_ip.clone(), agent_id.to_string());
                    self.agent_to_ip
                        .insert(agent_id.to_string(), try_ip.clone());
                    // Update next_host for future allocations
                    if let Some((_, next)) = self.subnet_groups.get_mut(subnet_group) {
                        *next = try_host + 1;
                    }
                    return Ok(try_ip);
                }
            }
            return Err(format!(
                "No available IPs in subnet group '{}'",
                subnet_group
            ));
        }

        self.used_ips.insert(ip.clone());
        self.assigned_ips.insert(ip.clone(), agent_id.to_string());
        self.agent_to_ip.insert(agent_id.to_string(), ip.clone());

        // Increment next_host for this group
        if let Some((_, next)) = self.subnet_groups.get_mut(subnet_group) {
            *next = host + 1;
        }

        Ok(ip)
    }

    /// Get the subnet prefix for a given subnet group (if it exists)
    pub fn get_subnet_group_prefix(&self, subnet_group: &str) -> Option<&str> {
        self.subnet_groups
            .get(subnet_group)
            .map(|(prefix, _)| prefix.as_str())
    }
}
