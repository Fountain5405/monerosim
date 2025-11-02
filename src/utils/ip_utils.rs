use std::net::IpAddr;

/// IP utility functions for validation and manipulation

/// Check if a string is a valid IP address (IPv4 or IPv6)
pub fn is_valid_ip(ip: &str) -> bool {
    ip.parse::<IpAddr>().is_ok()
}

/// Check if a string is a valid IPv4 address
pub fn is_valid_ipv4(ip: &str) -> bool {
    ip.parse::<std::net::Ipv4Addr>().is_ok()
}

/// Check if a string is a valid IPv6 address
pub fn is_valid_ipv6(ip: &str) -> bool {
    ip.parse::<std::net::Ipv6Addr>().is_ok()
}

/// Extract valid IP addresses from a list of strings
pub fn extract_valid_ips(values: &[String]) -> Vec<String> {
    values
        .iter()
        .filter(|ip| is_valid_ip(ip))
        .cloned()
        .collect()
}

/// Format an IP address with its default subnet mask
pub fn format_with_subnet(ip: &str) -> Result<String, String> {
    if let Ok(ip_addr) = ip.parse::<IpAddr>() {
        match ip_addr {
            IpAddr::V4(_) => Ok(format!("{}/24", ip)),
            IpAddr::V6(_) => Ok(format!("{}/64", ip)),
        }
    } else {
        Err("Invalid IP address".to_string())
    }
}

/// Check if an IP address is private (RFC 1918 for IPv4, RFC 4193 for IPv6)
pub fn is_private_ip(ip: &str) -> Result<bool, String> {
    if let Ok(ip_addr) = ip.parse::<IpAddr>() {
        match ip_addr {
            IpAddr::V4(ipv4) => {
                let octets = ipv4.octets();
                // RFC 1918 private ranges
                Ok(
                    // 10.0.0.0/8
                    octets[0] == 10 ||
                    // 172.16.0.0/12
                    (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31) ||
                    // 192.168.0.0/16
                    (octets[0] == 192 && octets[1] == 168)
                )
            }
            IpAddr::V6(ipv6) => {
                let segments = ipv6.segments();
                // RFC 4193 Unique Local Addresses (fc00::/7)
                Ok(segments[0] & 0xfe00 == 0xfc00)
            }
        }
    } else {
        Err("Invalid IP address".to_string())
    }
}

/// Generate a range of IP addresses starting from the given IP
pub fn generate_ip_range(start_ip: &str, count: usize) -> Result<Vec<String>, String> {
    if let Ok(ip_addr) = start_ip.parse::<IpAddr>() {
        match ip_addr {
            IpAddr::V4(ipv4) => {
                let mut result = Vec::new();
                let mut octets = ipv4.octets();

                for i in 0..count {
                    // Simple increment - this will fail if we go beyond 255
                    if octets[3] as usize + i > 255 {
                        return Err("IP range would exceed valid range".to_string());
                    }

                    let new_ip = std::net::Ipv4Addr::new(octets[0], octets[1], octets[2], octets[3] + i as u8);
                    result.push(new_ip.to_string());
                }

                Ok(result)
            }
            IpAddr::V6(_) => {
                // IPv6 range generation not implemented
                Err("IPv6 range generation not supported".to_string())
            }
        }
    } else {
        Err("Invalid start IP address".to_string())
    }
}