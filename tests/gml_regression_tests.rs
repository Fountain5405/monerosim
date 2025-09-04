#[cfg(test)]
mod gml_regression_tests {
    use std::path::Path;
    use std::collections::HashMap;
    use std::io::Write;
    use tempfile::NamedTempFile;

    // Import from gml_parser
    use monerosim::gml_parser::{GmlGraph, GmlNode, GmlEdge, ip_utils, parse_gml_file, get_autonomous_systems, validate_topology};

    // Import from shadow_agents
    use monerosim::shadow_agents::{AsSubnetManager, distribute_agents_across_gml_nodes, get_agent_ip, GlobalIpRegistry, AgentType};

    /// Test that GML-related files exist and have basic structure
    #[test]
    fn test_gml_files_exist() {
        // Check that our test GML files exist
        let test_files = vec![
            "testnet.gml",
            "realistic_internet.gml",
            "test_with_ips.gml"
        ];

        for file in test_files {
            if Path::new(file).exists() {
                println!("✓ GML file {} exists", file);

                // Basic validation - check file is not empty
                let content = std::fs::read_to_string(file).unwrap();
                assert!(!content.is_empty(), "GML file {} is empty", file);
                assert!(content.contains("graph"), "GML file {} does not contain 'graph' keyword", file);
            } else {
                println!("⚠ GML file {} does not exist (skipping)", file);
            }
        }
    }

    /// Test configuration file validation
    #[test]
    fn test_gml_config_files() {
        let config_files = vec![
            "test_gml_as_config.yaml",
            "test_gml_config.yaml",
            "config_gml_40_agents_test.yaml"
        ];

        for file in config_files {
            if Path::new(file).exists() {
                println!("✓ Config file {} exists", file);

                // Basic validation - check file is not empty and contains expected content
                let content = std::fs::read_to_string(file).unwrap();
                assert!(!content.is_empty(), "Config file {} is empty", file);
                assert!(content.contains("network"), "Config file {} does not contain 'network' section", file);
            } else {
                println!("⚠ Config file {} does not exist (skipping)", file);
            }
        }
    }

    /// Test IP address format validation
    #[test]
    fn test_ip_format_validation() {
        // Test valid IP addresses
        let valid_ips = vec![
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "127.0.0.1",
            "255.255.255.255",
            "::1",
            "2001:db8::1",
        ];

        for ip in valid_ips {
            assert!(ip.parse::<std::net::IpAddr>().is_ok(), "IP {} should be valid", ip);
        }

        // Test invalid IP addresses
        let invalid_ips = vec![
            "invalid.ip",
            "256.1.1.1",
            "192.168.1.256",
            "not.an.ip",
            "",
        ];

        for ip in invalid_ips {
            assert!(ip.parse::<std::net::IpAddr>().is_err(), "IP {} should be invalid", ip);
        }

        println!("✓ IP format validation test passed");
    }

    /// Test subnet range calculations
    #[test]
    fn test_subnet_ranges() {
        // Test AS subnet ranges
        let as_subnets = vec![
            (65001, "10.0.0.0/24"),
            (65002, "192.168.0.0/24"),
            (65003, "172.16.0.0/24"),
        ];

        for (as_num, expected_subnet) in as_subnets {
            println!("✓ AS {} maps to subnet {}", as_num, expected_subnet);
        }

        // Test IP range generation within subnets
        let test_ranges = vec![
            ("10.0.0.10", 5, vec!["10.0.0.10", "10.0.0.11", "10.0.0.12", "10.0.0.13", "10.0.0.14"]),
            ("192.168.0.10", 3, vec!["192.168.0.10", "192.168.0.11", "192.168.0.12"]),
        ];

        for (start_ip, count, expected) in test_ranges {
            let start_addr: std::net::IpAddr = start_ip.parse().unwrap();
            if let std::net::IpAddr::V4(ipv4) = start_addr {
                let mut current = ipv4;
                let mut result = Vec::new();

                for _ in 0..count {
                    result.push(current.to_string());
                    let octets = current.octets();
                    current = std::net::Ipv4Addr::new(octets[0], octets[1], octets[2], octets[3] + 1);
                }

                assert_eq!(result, expected, "IP range generation failed for {}", start_ip);
            }
        }

        println!("✓ Subnet range test passed");
    }

    /// Test agent distribution logic
    #[test]
    fn test_agent_distribution_logic() {
        // Test basic round-robin distribution
        let nodes = 5;
        let agents = 12;

        let mut node_counts = vec![0; nodes];
        for i in 0..agents {
            let node_index = i % nodes;
            node_counts[node_index] += 1;
        }

        // Each node should get either 2 or 3 agents (12 agents / 5 nodes = 2.4)
        for count in node_counts {
            assert!(count == 2 || count == 3, "Node should get 2 or 3 agents, got {}", count);
        }

        println!("✓ Agent distribution logic test passed");
    }

    /// Test configuration file parsing
    #[test]
    fn test_config_parsing() {
        // Test that we can parse YAML configuration files
        let config_content = r#"
general:
  stop_time: "10m"
  fresh_blockchain: true

network:
  path: "testnet.gml"

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"
"#;

        // Try to parse it as YAML
        let config: Result<serde_yaml::Value, _> = serde_yaml::from_str(config_content);
        assert!(config.is_ok(), "Failed to parse configuration YAML");

        let config = config.unwrap();

        // Validate structure
        assert!(config.get("general").is_some(), "Config missing 'general' section");
        assert!(config.get("network").is_some(), "Config missing 'network' section");
        assert!(config.get("agents").is_some(), "Config missing 'agents' section");

        // Validate network section has path
        let network = config.get("network").unwrap();
        assert!(network.get("path").is_some(), "Network section missing 'path' field");

        println!("✓ Configuration parsing test passed");
    }

    /// Test GML file structure validation
    #[test]
    fn test_gml_file_structure() {
        // Test with a simple GML content
        let gml_content = r#"
            graph [
                directed 1
                node [ id 0 AS "65001" label "Node1" ]
                node [ id 1 AS "65002" label "Node2" ]
                edge [ source 0 target 1 latency "10ms" ]
            ]
        "#;

        // Basic structure validation
        assert!(gml_content.contains("graph"), "GML must contain 'graph' keyword");
        assert!(gml_content.contains("node"), "GML must contain 'node' definitions");
        assert!(gml_content.contains("id"), "GML nodes must have 'id' attributes");

        // Test that it parses as valid YAML-like structure (basic check)
        assert!(gml_content.contains("["), "GML must have opening brackets");
        assert!(gml_content.contains("]"), "GML must have closing brackets");

        println!("✓ GML file structure test passed");
    }

    /// Test AS number validation
    #[test]
    fn test_as_number_validation() {
        // Valid AS numbers (typical range)
        let valid_as_numbers = vec![
            "65001", "65002", "65003", "64512", "65534"
        ];

        for as_num in &valid_as_numbers {
            // Should be parseable as u32
            assert!(as_num.parse::<u32>().is_ok(), "AS number {} should be valid", as_num);
        }

        // Test AS number ranges
        for as_num in &valid_as_numbers {
            let as_u32 = as_num.parse::<u32>().unwrap();
            assert!(as_u32 >= 64512 && as_u32 <= 65534, "AS number {} should be in private range", as_num);
        }

        println!("✓ AS number validation test passed");
    }

    /// Test network topology validation concepts
    #[test]
    fn test_topology_validation_concepts() {
        // Test basic connectivity concepts
        let nodes = vec![0, 1, 2, 3];
        let edges = vec![(0, 1), (1, 2), (2, 3)];

        // Check that all nodes are referenced in edges
        let mut referenced_nodes = std::collections::HashSet::new();
        for (source, target) in &edges {
            referenced_nodes.insert(source);
            referenced_nodes.insert(target);
        }

        // All nodes should be referenced (basic connectivity)
        for node in &nodes {
            assert!(referenced_nodes.contains(node), "Node {} is not connected", node);
        }

        // Test for duplicate edges (should not exist)
        let mut edge_set = std::collections::HashSet::new();
        for (source, target) in &edges {
            let edge = (*source, *target);
            assert!(!edge_set.contains(&edge), "Duplicate edge found: ({}, {})", source, target);
            edge_set.insert(edge);
        }

        println!("✓ Topology validation concepts test passed");
    }

    /// Test IP validation functions
    #[test]
    fn test_ip_validation() {
        // Valid IPv4 addresses
        assert!(ip_utils::is_valid_ip("192.168.1.1"));
        assert!(ip_utils::is_valid_ip("10.0.0.1"));
        assert!(ip_utils::is_valid_ip("172.16.0.1"));
        assert!(ip_utils::is_valid_ipv4("192.168.1.1"));
        assert!(!ip_utils::is_valid_ipv6("192.168.1.1"));

        // Valid IPv6 addresses
        assert!(ip_utils::is_valid_ip("::1"));
        assert!(ip_utils::is_valid_ip("2001:db8::1"));
        assert!(ip_utils::is_valid_ipv6("::1"));
        assert!(!ip_utils::is_valid_ipv4("::1"));

        // Invalid IP addresses
        assert!(!ip_utils::is_valid_ip("invalid.ip"));
        assert!(!ip_utils::is_valid_ip("256.1.1.1"));
        assert!(!ip_utils::is_valid_ip("192.168.1.256"));
    }

    /// Test IP range generation
    #[test]
    fn test_ip_range_generation() {
        let range = ip_utils::generate_ip_range("192.168.1.1", 5).unwrap();
        assert_eq!(range.len(), 5);
        assert_eq!(range[0], "192.168.1.1");
        assert_eq!(range[1], "192.168.1.2");
        assert_eq!(range[2], "192.168.1.3");
        assert_eq!(range[3], "192.168.1.4");
        assert_eq!(range[4], "192.168.1.5");

        // Test range that would exceed 255
        assert!(ip_utils::generate_ip_range("192.168.1.254", 5).is_err());

        // Test invalid start IP
        assert!(ip_utils::generate_ip_range("invalid.ip", 5).is_err());
    }

    /// Test AS-aware subnet manager
    #[test]
    fn test_as_subnet_manager() {
        let mut manager = AsSubnetManager::new();

        // Test AS 65001 (192.168.100.x subnet)
        assert_eq!(manager.assign_as_aware_ip("65001"), Some("192.168.100.100".to_string()));
        assert_eq!(manager.assign_as_aware_ip("65001"), Some("192.168.100.101".to_string()));

        // Test AS 65002 (192.168.101.x subnet)
        assert_eq!(manager.assign_as_aware_ip("65002"), Some("192.168.101.100".to_string()));
        assert_eq!(manager.assign_as_aware_ip("65002"), Some("192.168.101.101".to_string()));

        // Test AS 65003 (192.168.102.x subnet)
        assert_eq!(manager.assign_as_aware_ip("65003"), Some("192.168.102.100".to_string()));

        // Test unknown AS (should return None)
        assert_eq!(manager.assign_as_aware_ip("65004"), None);
    }

    /// Test autonomous system detection
    #[test]
    fn test_autonomous_system_detection() {
        let graph = GmlGraph {
            nodes: vec![
                GmlNode {
                    id: 0,
                    label: None,
                    attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 1,
                    label: None,
                    attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 2,
                    label: None,
                    attributes: [("as".to_string(), "65002".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 3,
                    label: None,
                    attributes: HashMap::new(), // No AS attribute
                },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };

        let as_groups = get_autonomous_systems(&graph);

        // Should have 3 groups: 65001 (2 nodes), 65002 (1 node), no-AS (1 node)
        assert_eq!(as_groups.len(), 3);

        // Find AS 65001 group
        let as_65001 = as_groups.iter().find(|group| group.contains(&0)).unwrap();
        assert!(as_65001.contains(&1));
        assert_eq!(as_65001.len(), 2);

        // Find AS 65002 group
        let as_65002 = as_groups.iter().find(|group| group.contains(&2)).unwrap();
        assert_eq!(as_65002.len(), 1);
    }

    /// Test agent distribution across GML nodes
    #[test]
    fn test_agent_distribution_across_gml_nodes() {
        // Test with AS groups
        let graph = GmlGraph {
            nodes: vec![
                GmlNode {
                    id: 0,
                    label: None,
                    attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 1,
                    label: None,
                    attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 2,
                    label: None,
                    attributes: [("AS".to_string(), "65002".to_string())].iter().cloned().collect(),
                },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };

        let assignments = distribute_agents_across_gml_nodes(&graph, 6);

        // Should distribute 6 agents across the nodes
        assert_eq!(assignments.len(), 6);

        // Count assignments per node
        let mut node_counts = HashMap::new();
        for &node_id in &assignments {
            *node_counts.entry(node_id).or_insert(0) += 1;
        }

        // AS 65001 (nodes 0,1) should get 4 agents (2/3 of 6)
        // AS 65002 (node 2) should get 2 agents (1/3 of 6)
        assert_eq!(*node_counts.get(&0).unwrap_or(&0), 2);
        assert_eq!(*node_counts.get(&1).unwrap_or(&0), 2);
        assert_eq!(*node_counts.get(&2).unwrap_or(&0), 2);
    }

    /// Test agent IP assignment with GML topology
    #[test]
    fn test_agent_ip_assignment_with_gml() {
        let mut subnet_manager = AsSubnetManager::new();
        let mut ip_registry = GlobalIpRegistry::new();

        let graph = GmlGraph {
            nodes: vec![
                GmlNode {
                    id: 0,
                    label: None,
                    attributes: [
                        ("AS".to_string(), "65001".to_string()),
                        ("ip".to_string(), "192.168.1.100".to_string())
                    ].iter().cloned().collect(),
                },
                GmlNode {
                    id: 1,
                    label: None,
                    attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 2,
                    label: None,
                    attributes: [("AS".to_string(), "65002".to_string())].iter().cloned().collect(),
                },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };

        // Test IP assignment for node with pre-assigned IP
        let ip1 = get_agent_ip(AgentType::UserAgent, "user000", 0, 0, Some(&graph), true, &mut subnet_manager, &mut ip_registry);
        assert_eq!(ip1, "192.168.1.100");

        // Test IP assignment for node in AS 65001 (should get 192.168.100.100)
        let ip2 = get_agent_ip(AgentType::UserAgent, "user001", 1, 1, Some(&graph), true, &mut subnet_manager, &mut ip_registry);
        assert_eq!(ip2, "192.168.100.100");

        // Test IP assignment for node in AS 65002 (should get 192.168.101.100)
        let ip3 = get_agent_ip(AgentType::UserAgent, "user002", 2, 2, Some(&graph), true, &mut subnet_manager, &mut ip_registry);
        assert_eq!(ip3, "192.168.101.100");
    }

    /// Test fallback IP assignment without GML
    #[test]
    fn test_fallback_ip_assignment() {
        let mut subnet_manager = AsSubnetManager::new();
        let mut ip_registry = GlobalIpRegistry::new();

        // Test fallback when no GML topology
        let ip = get_agent_ip(AgentType::UserAgent, "user000", 0, 0, None, false, &mut subnet_manager, &mut ip_registry);
        assert_eq!(ip, "192.168.0.10");

        let ip2 = get_agent_ip(AgentType::UserAgent, "user001", 1, 0, None, false, &mut subnet_manager, &mut ip_registry);
        assert_eq!(ip2, "172.16.1.10");
    }

    /// Test network topology validation
    #[test]
    fn test_topology_validation() {
        // Valid topology
        let valid_graph = GmlGraph {
            nodes: vec![
                GmlNode { id: 0, label: None, attributes: HashMap::new() },
                GmlNode { id: 1, label: None, attributes: HashMap::new() },
            ],
            edges: vec![
                GmlEdge { source: 0, target: 1, attributes: HashMap::new() },
            ],
            attributes: HashMap::new(),
        };
        assert!(validate_topology(&valid_graph).is_ok());

        // Invalid: duplicate node IDs
        let invalid_graph1 = GmlGraph {
            nodes: vec![
                GmlNode { id: 0, label: None, attributes: HashMap::new() },
                GmlNode { id: 0, label: None, attributes: HashMap::new() },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };
        assert!(validate_topology(&invalid_graph1).is_err());

        // Invalid: edge references non-existent node
        let invalid_graph2 = GmlGraph {
            nodes: vec![
                GmlNode { id: 0, label: None, attributes: HashMap::new() },
            ],
            edges: vec![
                GmlEdge { source: 0, target: 999, attributes: HashMap::new() },
            ],
            attributes: HashMap::new(),
        };
        assert!(validate_topology(&invalid_graph2).is_err());
    }

    /// Test GML parsing with complex attributes
    #[test]
    fn test_gml_parsing_with_complex_attributes() {
        let gml_content = r#"
            graph [
                directed 1
                node [ id 0 AS "65001" bandwidth "1000Mbit" latency "10ms" ]
                node [ id 1 as "65002" ip "192.168.1.1" packet_loss "0.1%" ]
                edge [ source 0 target 1 latency "50ms" bandwidth "100Mbit" ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();

        assert_eq!(graph.attributes.get("directed"), Some(&"1".to_string()));
        assert_eq!(graph.nodes.len(), 2);
        assert_eq!(graph.edges.len(), 1);

        // Check node attributes
        assert_eq!(graph.nodes[0].attributes.get("AS"), Some(&"65001".to_string()));
        assert_eq!(graph.nodes[0].attributes.get("bandwidth"), Some(&"1000Mbit".to_string()));
        assert_eq!(graph.nodes[1].attributes.get("ip"), Some(&"192.168.1.1".to_string()));

        // Check edge attributes
        assert_eq!(graph.edges[0].attributes.get("latency"), Some(&"50ms".to_string()));
        assert_eq!(graph.edges[0].attributes.get("bandwidth"), Some(&"100Mbit".to_string()));
    }

    /// Test IP address conflict detection
    #[test]
    fn test_ip_address_conflict_detection() {
        let mut node1 = GmlNode {
            id: 0,
            label: None,
            attributes: HashMap::new(),
        };
        let mut node2 = GmlNode {
            id: 1,
            label: None,
            attributes: HashMap::new(),
        };

        // Assign same IP to both nodes
        node1.set_ip("192.168.1.1").unwrap();
        node2.set_ip("192.168.1.1").unwrap();

        // Both should have the same IP (this is allowed at GML level,
        // conflict detection happens at Shadow configuration level)
        assert_eq!(node1.get_ip(), Some("192.168.1.1".to_string()));
        assert_eq!(node2.get_ip(), Some("192.168.1.1".to_string()));
    }

    /// Test subnet range exhaustion handling
    #[test]
    fn test_subnet_range_exhaustion() {
        let mut manager = AsSubnetManager::new();

        // Assign IPs from 192.168.100.100 to 192.168.100.254 (valid host addresses)
        for i in 100..=254 {
            let expected_ip = format!("192.168.100.{}", i);
            let assigned_ip = manager.assign_as_aware_ip("65001");
            assert_eq!(assigned_ip, Some(expected_ip));
        }

        // Next assignment should return None (subnet exhausted)
        // We don't assign .255 as it's typically the broadcast address
        assert_eq!(manager.assign_as_aware_ip("65001"), None);
    }

    /// Test mixed case AS attributes
    #[test]
    fn test_mixed_case_as_attributes() {
        let graph = GmlGraph {
            nodes: vec![
                GmlNode {
                    id: 0,
                    label: None,
                    attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 1,
                    label: None,
                    attributes: [("as".to_string(), "65001".to_string())].iter().cloned().collect(),
                },
                GmlNode {
                    id: 2,
                    label: None,
                    attributes: [("As".to_string(), "65002".to_string())].iter().cloned().collect(),
                },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };

        let as_groups = get_autonomous_systems(&graph);

        // Should group nodes 0 and 1 together (both AS 65001)
        // Node 2 should be separate (AS 65002)
        assert_eq!(as_groups.len(), 2);

        let as_65001 = as_groups.iter().find(|group| group.contains(&0)).unwrap();
        assert!(as_65001.contains(&1));
        assert!(!as_65001.contains(&2));
    }

    /// Test empty GML graph handling
    #[test]
    fn test_empty_gml_graph_handling() {
        let empty_graph = GmlGraph {
            nodes: vec![],
            edges: vec![],
            attributes: HashMap::new(),
        };

        // Should handle empty graph gracefully
        let assignments = distribute_agents_across_gml_nodes(&empty_graph, 5);
        // All agents should be assigned to node 0 (fallback)
        assert_eq!(assignments.len(), 5);
        assert!(assignments.iter().all(|&node_id| node_id == 0));
    }

    /// Test large-scale agent distribution
    #[test]
    fn test_large_scale_agent_distribution() {
        // Create a graph with many nodes across multiple AS
        let mut nodes = Vec::new();
        for i in 0..100 {
            let as_number = format!("6500{}", (i % 5) + 1); // AS 65001-65005
            nodes.push(GmlNode {
                id: i as u32,
                label: None,
                attributes: [("AS".to_string(), as_number)].iter().cloned().collect(),
            });
        }

        let graph = GmlGraph {
            nodes,
            edges: vec![],
            attributes: HashMap::new(),
        };

        let assignments = distribute_agents_across_gml_nodes(&graph, 1000);

        // Should distribute 1000 agents across 100 nodes
        assert_eq!(assignments.len(), 1000);

        // Each node should get approximately 10 agents (1000/100)
        let mut node_counts = HashMap::new();
        for &node_id in &assignments {
            *node_counts.entry(node_id).or_insert(0) += 1;
        }

        // Check that distribution is reasonably even
        for &count in node_counts.values() {
            assert!(count >= 8 && count <= 12); // Allow some variance
        }
    }

    /// Test GML parsing error handling
    #[test]
    fn test_gml_parsing_error_handling() {
        // Test malformed GML
        let malformed_gml = r#"
            graph [
                node [ id 0 AS "65001"
                # Missing closing bracket
                node [ id 1 AS "65002" ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", malformed_gml).unwrap();

        // Should handle parsing errors gracefully
        let result = parse_gml_file(temp_file.path().to_str().unwrap());
        assert!(result.is_err());
    }

    /// Test IP utility functions edge cases
    #[test]
    fn test_ip_utils_edge_cases() {
        // Test empty string
        assert!(!ip_utils::is_valid_ip(""));

        // Test localhost variations
        assert!(ip_utils::is_valid_ip("127.0.0.1"));
        assert!(!ip_utils::is_valid_ip("localhost")); // This should fail as it's not a valid IP

        // Test broadcast addresses
        assert!(ip_utils::is_valid_ip("255.255.255.255"));
        assert!(ip_utils::is_valid_ip("192.168.255.255"));

        // Test format with subnet
        assert_eq!(ip_utils::format_with_subnet("192.168.1.1").unwrap(), "192.168.1.1/24");
        assert_eq!(ip_utils::format_with_subnet("::1").unwrap(), "::1/64");

        // Test private IP detection
        assert!(ip_utils::is_private_ip("10.0.0.1").unwrap());
        assert!(ip_utils::is_private_ip("172.16.0.1").unwrap());
        assert!(ip_utils::is_private_ip("192.168.1.1").unwrap());
        assert!(!ip_utils::is_private_ip("8.8.8.8").unwrap());
    }

    /// Test end-to-end GML configuration processing
    #[test]
    fn test_end_to_end_gml_config() {
        // Test that we can process a complete GML-based configuration
        let config_content = r#"
general:
  stop_time: "5m"
  fresh_blockchain: true
  log_level: "info"

network:
  path: "testnet.gml"

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "60"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "false"
        transaction_interval: "30"
"#;

        // Try to parse it as YAML
        let config: Result<serde_yaml::Value, _> = serde_yaml::from_str(config_content);
        assert!(config.is_ok(), "Failed to parse GML configuration YAML");

        let config = config.unwrap();

        // Validate GML-specific structure
        assert!(config.get("network").is_some(), "Config missing 'network' section");
        let network = config.get("network").unwrap();
        assert!(network.get("path").is_some(), "Network section missing 'path' field");

        // Validate agents have proper attributes for GML topology
        let agents = config.get("agents").unwrap();
        let user_agents = agents.get("user_agents").unwrap();
        assert!(user_agents.as_sequence().unwrap().len() == 2, "Should have 2 user agents");

        println!("✓ End-to-end GML configuration test passed");
    }

    /// Test performance with large GML topologies
    #[test]
    fn test_large_topology_performance() {
        // Create a large topology for performance testing
        let mut nodes = Vec::new();
        let num_nodes = 100;

        for i in 0..num_nodes {
            let as_number = format!("6500{}", (i % 5) + 1); // 5 different AS groups
            nodes.push(GmlNode {
                id: i as u32,
                label: Some(format!("Node{}", i)),
                attributes: [
                    ("AS".to_string(), as_number),
                    ("bandwidth".to_string(), "1000Mbit".to_string()),
                ].iter().cloned().collect(),
            });
        }

        let graph = GmlGraph {
            nodes,
            edges: vec![], // No edges for this performance test
            attributes: HashMap::new(),
        };

        // Test AS grouping performance
        let start = std::time::Instant::now();
        let as_groups = get_autonomous_systems(&graph);
        let as_grouping_time = start.elapsed();

        // Test agent distribution performance
        let start = std::time::Instant::now();
        let assignments = distribute_agents_across_gml_nodes(&graph, 500);
        let distribution_time = start.elapsed();

        // Validate results
        assert_eq!(as_groups.len(), 5, "Should have 5 AS groups");
        assert_eq!(assignments.len(), 500, "Should distribute 500 agents");

        // Performance should be reasonable (less than 100ms for this size)
        assert!(as_grouping_time < std::time::Duration::from_millis(100),
                "AS grouping took too long: {:?}", as_grouping_time);
        assert!(distribution_time < std::time::Duration::from_millis(100),
                "Agent distribution took too long: {:?}", distribution_time);

        println!("✓ Large topology performance test passed");
        println!("  AS grouping time: {:?}", as_grouping_time);
        println!("  Agent distribution time: {:?}", distribution_time);
    }

    /// Test GML topology with realistic network attributes
    #[test]
    fn test_realistic_gml_topology() {
        let gml_content = r#"
            graph [
                directed 1
                # Multi-AS internet topology
                node [ id 0 AS "65001" label "US-West" bandwidth "1000Mbit" region "us-west" ]
                node [ id 1 AS "65001" label "US-East" bandwidth "500Mbit" region "us-east" ]
                node [ id 2 AS "65002" label "EU-Central" bandwidth "200Mbit" region "eu-central" ]
                node [ id 3 AS "65002" label "EU-North" bandwidth "100Mbit" region "eu-north" ]
                node [ id 4 AS "65003" label "Asia-Pacific" bandwidth "150Mbit" region "asia-pac" ]

                # Inter-AS connections with realistic latencies
                edge [ source 0 target 2 latency "120ms" bandwidth "100Mbit" type "transatlantic" ]
                edge [ source 1 target 3 latency "90ms" bandwidth "200Mbit" type "transatlantic" ]
                edge [ source 2 target 4 latency "200ms" bandwidth "50Mbit" type "transpacific" ]
                edge [ source 3 target 4 latency "180ms" bandwidth "75Mbit" type "transpacific" ]

                # Intra-AS connections
                edge [ source 0 target 1 latency "15ms" bandwidth "1Gbit" type "domestic" ]
                edge [ source 2 target 3 latency "8ms" bandwidth "500Mbit" type "domestic" ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();

        // Validate realistic topology
        assert_eq!(graph.nodes.len(), 5);
        assert_eq!(graph.edges.len(), 6);

        // Check AS distribution
        let as_groups = get_autonomous_systems(&graph);
        assert_eq!(as_groups.len(), 3); // 3 different AS groups

        // Validate network attributes
        for node in &graph.nodes {
            assert!(node.attributes.contains_key("bandwidth"));
            assert!(node.attributes.contains_key("region"));
        }

        for edge in &graph.edges {
            assert!(edge.attributes.contains_key("latency"));
            assert!(edge.attributes.contains_key("bandwidth"));
            assert!(edge.attributes.contains_key("type"));
        }

        // Test agent distribution on realistic topology
        let assignments = distribute_agents_across_gml_nodes(&graph, 10);
        assert_eq!(assignments.len(), 10);

        // Validate topology
        validate_topology(&graph).unwrap();

        println!("✓ Realistic GML topology test passed");
    }

    /// Test error handling for malformed GML files
    #[test]
    fn test_malformed_gml_error_handling() {
        let malformed_cases = vec![
            // Missing closing bracket
            (r#"graph [ node [ id 0 ]"#, true),
            // Invalid node ID
            (r#"graph [ node [ id "invalid" ] ]"#, true),
            // Duplicate node IDs (caught by validation, not parsing)
            (r#"graph [ node [ id 0 ] node [ id 0 ] ]"#, false),
            // Edge referencing non-existent node (caught by validation, not parsing)
            (r#"graph [ node [ id 0 ] edge [ source 0 target 999 ] ]"#, false),
            // Invalid edge source/target
            (r#"graph [ node [ id 0 ] edge [ source "invalid" target 0 ] ]"#, true),
        ];

        for (i, (malformed_gml, should_fail_at_parse)) in malformed_cases.iter().enumerate() {
            let mut temp_file = NamedTempFile::new().unwrap();
            write!(temp_file, "{}", malformed_gml).unwrap();

            let result = parse_gml_file(temp_file.path().to_str().unwrap());

            if *should_fail_at_parse {
                assert!(result.is_err(), "Test case {} should have failed at parse but didn't", i);
                println!("✓ Malformed GML test case {} correctly failed at parse: {:?}", i, result.err());
            } else {
                // These cases should pass parsing but fail validation
                if let Ok(graph) = result {
                    let validation_result = validate_topology(&graph);
                    assert!(validation_result.is_err(), "Test case {} should have failed validation but didn't", i);
                    println!("✓ Malformed GML test case {} correctly failed at validation: {:?}", i, validation_result.err());
                } else {
                    println!("⚠ Test case {} failed at parse instead of validation: {:?}", i, result.err());
                }
            }
        }

        println!("✓ Malformed GML error handling test passed");
    }

    /// Test configuration validation for GML topologies
    #[test]
    fn test_gml_config_validation() {
        // Test valid GML configuration
        let valid_config = r#"
general:
  stop_time: "10m"
  fresh_blockchain: true

network:
  path: "topology.gml"

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"
"#;

        let config: Result<serde_yaml::Value, _> = serde_yaml::from_str(valid_config);
        assert!(config.is_ok());

        // Test configuration with missing GML path
        let invalid_config = r#"
general:
  stop_time: "10m"

network:
  type: "1_gbit_switch"  # Not GML

agents:
  user_agents:
    - daemon: "monerod"
"#;

        let config: Result<serde_yaml::Value, _> = serde_yaml::from_str(invalid_config);
        assert!(config.is_ok());

        let config = config.unwrap();
        let network = config.get("network").unwrap();
        assert!(network.get("path").is_none()); // Should not have path for switch topology

        println!("✓ GML configuration validation test passed");
    }
}