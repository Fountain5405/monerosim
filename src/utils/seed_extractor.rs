//! Seed node IP extractor.
//!
//! Extracts hardcoded seed node IPs from monerod source code.
//! This allows the simulation to use the same IPs that monerod expects.

use std::path::Path;
use std::sync::LazyLock;
use std::fs;
use regex::Regex;

static IP_PATTERN: LazyLock<Regex> = LazyLock::new(||
    Regex::new(r#"full_addrs\.insert\("(\d+\.\d+\.\d+\.\d+):(\d+)"\)"#).unwrap()
);

/// Mainnet seed node info
#[derive(Debug, Clone)]
pub struct SeedNode {
    pub ip: String,
    pub port: u16,
}

/// Extract mainnet seed IPs from monerod source code.
///
/// This reads the net_node.inl file and parses the hardcoded IP addresses
/// from the `get_ip_seed_nodes()` function's else (mainnet) case.
///
/// # Arguments
/// * `monerod_path` - Path to the monerod binary (used to derive source path)
///
/// # Returns
/// Vector of SeedNode structs containing IP and port
pub fn extract_mainnet_seed_ips(monerod_path: &str) -> Result<Vec<SeedNode>, String> {
    // Derive source path from monerod binary path
    // Example: /path/to/monero-shadow/build/Linux/release/bin/monerod
    //       -> /path/to/monero-shadow/src/p2p/net_node.inl

    let monerod_path = Path::new(monerod_path);

    // Navigate up from bin/monerod to find the source directory
    // Try to find the monero source root by looking for src/p2p/net_node.inl
    let mut current = monerod_path.parent(); // bin/
    let mut source_path = None;

    // Walk up the directory tree looking for the source
    for _ in 0..10 {
        if let Some(dir) = current {
            let potential_source = dir.join("src/p2p/net_node.inl");
            if potential_source.exists() {
                source_path = Some(potential_source);
                break;
            }
            current = dir.parent();
        } else {
            break;
        }
    }

    let net_node_path = source_path.ok_or_else(|| {
        format!("Could not find net_node.inl relative to monerod path: {}", monerod_path.display())
    })?;

    extract_seed_ips_from_file(&net_node_path)
}

/// Extract seed IPs directly from a net_node.inl file path
pub fn extract_seed_ips_from_file(file_path: &Path) -> Result<Vec<SeedNode>, String> {
    let content = fs::read_to_string(file_path)
        .map_err(|e| format!("Failed to read {}: {}", file_path.display(), e))?;

    parse_mainnet_seed_ips(&content)
}

/// Parse mainnet seed IPs from net_node.inl content
///
/// Looks for the pattern in get_ip_seed_nodes():
/// ```cpp
/// else
/// {
///   full_addrs.insert("176.9.0.187:18080");
///   ...
/// }
/// ```
fn parse_mainnet_seed_ips(content: &str) -> Result<Vec<SeedNode>, String> {
    // Find the get_ip_seed_nodes function
    let func_start = content.find("get_ip_seed_nodes()")
        .ok_or("Could not find get_ip_seed_nodes() function")?;

    // Get the content after the function definition
    let func_content = &content[func_start..];

    let ip_pattern = &*IP_PATTERN;

    let mut seed_nodes = Vec::new();
    let mut in_mainnet_block = false;
    let mut brace_depth = 0;

    for line in func_content.lines() {
        // Track brace depth to know when we exit the function
        brace_depth += line.matches('{').count() as i32;
        brace_depth -= line.matches('}').count() as i32;

        // Stop at the end of the function
        if brace_depth < 0 {
            break;
        }

        // Look for the else block (mainnet case)
        // The mainnet case is the else after STAGENET check
        if line.contains("else") && !line.contains("if") {
            in_mainnet_block = true;
        }

        // If we're in the mainnet block and find an insert with port 18080
        if in_mainnet_block {
            if let Some(caps) = ip_pattern.captures(line) {
                let ip = caps.get(1).unwrap().as_str().to_string();
                let port: u16 = caps.get(2).unwrap().as_str().parse().unwrap_or(18080);

                // Only include mainnet IPs (port 18080)
                if port == 18080 {
                    seed_nodes.push(SeedNode { ip, port });
                }
            }
        }

        // Reset when we see return (end of else block)
        if line.contains("return") {
            in_mainnet_block = false;
        }
    }

    if seed_nodes.is_empty() {
        Err("No mainnet seed IPs found in source".to_string())
    } else {
        Ok(seed_nodes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_mainnet_seed_ips() {
        let content = r#"
  std::set<std::string> node_server<t_payload_net_handler>::get_ip_seed_nodes() const
  {
    std::set<std::string> full_addrs;
    if (m_nettype == cryptonote::TESTNET)
    {
      full_addrs.insert("176.9.0.187:28080");
    }
    else if (m_nettype == cryptonote::STAGENET)
    {
      full_addrs.insert("176.9.0.187:38080");
    }
    else if (m_nettype == cryptonote::FAKECHAIN)
    {
    }
    else
    {
      full_addrs.insert("176.9.0.187:18080");
      full_addrs.insert("88.198.163.90:18080");
      full_addrs.insert("66.85.74.134:18080");
    }
    return full_addrs;
  }
"#;

        let seeds = parse_mainnet_seed_ips(content).unwrap();
        assert_eq!(seeds.len(), 3);
        assert_eq!(seeds[0].ip, "176.9.0.187");
        assert_eq!(seeds[0].port, 18080);
    }
}
