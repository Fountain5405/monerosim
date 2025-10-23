use std::collections::HashMap;
use std::fs;
use std::path::Path;
use color_eyre::eyre::{Result, eyre};

/// Errors that can occur during GML parsing
#[derive(Debug, Clone)]
pub enum GmlParseError {
    InvalidIp(String),
}

/// Represents a node in a GML graph
#[derive(Debug, Clone)]
pub struct GmlNode {
    pub id: u32,
    pub label: Option<String>,
    pub ip: Option<String>,
    pub region: Option<String>,
    pub attributes: HashMap<String, String>,
}

impl GmlNode {
    /// Check if a string is a valid IP address (IPv4 or IPv6)
    pub fn is_valid_ip(ip: &str) -> bool {
        ip.parse::<std::net::IpAddr>().is_ok()
    }

    /// Get the IP address from the dedicated ip field
    pub fn get_ip(&self) -> Option<&str> {
        self.ip.as_deref()
    }

    /// Get the region from the dedicated region field
    pub fn get_region(&self) -> Option<&str> {
        self.region.as_deref()
    }

    /// Check if the node has any valid IP address
    pub fn has_ip(&self) -> bool {
        self.ip.is_some()
    }
}


/// Parse IP address from GML node attributes
///
/// Extracts IP from GML node attributes and validates format.
/// Returns Some(valid_ip) if found and valid, None if not present or invalid.
/// Logs warnings for invalid IPs but continues parsing.
fn parse_ip(attributes: &HashMap<String, String>) -> Option<String> {
    let possible_keys = ["ip", "ip_addr", "address", "ip_address"];

    for key in &possible_keys {
        if let Some(value) = attributes.get(*key) {
            // Remove quotes if present
            let cleaned_value = value.trim_matches('"');
            if cleaned_value.parse::<std::net::Ipv4Addr>().is_ok() {
                return Some(cleaned_value.to_string());
            } else {
                log::warn!("Invalid IP address '{}' in attribute '{}'", cleaned_value, key);
            }
        }
    }

    None
}

/// Parse region from GML node attributes
///
/// Extracts region from GML node attributes.
/// Returns Some(region) if found, None if not present.
/// Handles quoted strings properly.
fn parse_region(attributes: &HashMap<String, String>) -> Option<String> {
    let possible_keys = ["region", "geographic_region", "location"];

    for key in &possible_keys {
        if let Some(value) = attributes.get(*key) {
            // Remove quotes if present
            let cleaned_value = value.trim_matches('"').to_string();
            return Some(cleaned_value);
        }
    }

    None
}

/// Represents an edge in a GML graph
#[derive(Debug, Clone)]
pub struct GmlEdge {
    pub source: u32,
    pub target: u32,
    pub attributes: HashMap<String, String>,
}

/// Represents a complete GML graph
#[derive(Debug, Clone)]
pub struct GmlGraph {
    pub nodes: Vec<GmlNode>,
    pub edges: Vec<GmlEdge>,
    pub attributes: HashMap<String, String>,
}

/// Legacy Graph structure for backward compatibility
#[derive(Debug, Default)]
pub struct Graph {
    pub nodes: Vec<Node>,
}

/// Legacy Node structure for backward compatibility
#[derive(Debug)]
pub struct Node {
    pub id: i32,
}

/// Token types for GML parsing
#[derive(Debug, Clone, PartialEq)]
enum Token {
    Identifier(String),
    Number(String),
    String(String),
    LeftBracket,
    RightBracket,
    Eof,
}

/// Simple lexer for GML format
struct Lexer {
    input: Vec<char>,
    position: usize,
    current_char: Option<char>,
}

impl Lexer {
    fn new(input: &str) -> Self {
        let chars: Vec<char> = input.chars().collect();
        let current_char = chars.get(0).copied();
        Self {
            input: chars,
            position: 0,
            current_char,
        }
    }

    fn advance(&mut self) {
        self.position += 1;
        self.current_char = self.input.get(self.position).copied();
    }

    fn skip_whitespace(&mut self) {
        while let Some(ch) = self.current_char {
            if ch.is_whitespace() {
                self.advance();
            } else {
                break;
            }
        }
    }

    fn skip_comment(&mut self) {
        // Skip single-line comments starting with #
        if self.current_char == Some('#') {
            while let Some(ch) = self.current_char {
                if ch == '\n' {
                    break;
                }
                self.advance();
            }
        }
    }

    fn read_string(&mut self) -> Result<String> {
        let mut result = String::new();
        self.advance(); // Skip opening quote
        
        while let Some(ch) = self.current_char {
            if ch == '"' {
                self.advance(); // Skip closing quote
                return Ok(result);
            }
            if ch == '\\' {
                self.advance();
                if let Some(escaped) = self.current_char {
                    match escaped {
                        'n' => result.push('\n'),
                        't' => result.push('\t'),
                        'r' => result.push('\r'),
                        '\\' => result.push('\\'),
                        '"' => result.push('"'),
                        _ => {
                            result.push('\\');
                            result.push(escaped);
                        }
                    }
                    self.advance();
                }
            } else {
                result.push(ch);
                self.advance();
            }
        }
        
        Err(eyre!("Unterminated string literal"))
    }

    fn read_identifier_or_number(&mut self) -> String {
        let mut result = String::new();
        
        while let Some(ch) = self.current_char {
            if ch.is_alphanumeric() || ch == '_' || ch == '.' || ch == '-' || ch == '+' {
                result.push(ch);
                self.advance();
            } else {
                break;
            }
        }
        
        result
    }

    fn next_token(&mut self) -> Result<Token> {
        loop {
            self.skip_whitespace();
            
            match self.current_char {
                None => return Ok(Token::Eof),
                Some('#') => {
                    self.skip_comment();
                    continue;
                }
                Some('[') => {
                    self.advance();
                    return Ok(Token::LeftBracket);
                }
                Some(']') => {
                    self.advance();
                    return Ok(Token::RightBracket);
                }
                Some('"') => {
                    let string_val = self.read_string()?;
                    return Ok(Token::String(string_val));
                }
                Some(ch) if ch.is_alphabetic() || ch == '_' => {
                    let identifier = self.read_identifier_or_number();
                    return Ok(Token::Identifier(identifier));
                }
                Some(ch) if ch.is_numeric() || ch == '-' || ch == '+' => {
                    let number = self.read_identifier_or_number();
                    return Ok(Token::Number(number));
                }
                Some(ch) => {
                    return Err(eyre!("Unexpected character: '{}'", ch));
                }
            }
        }
    }
}

/// Parser for GML format
struct Parser {
    lexer: Lexer,
    current_token: Token,
}

impl Parser {
    fn new(mut lexer: Lexer) -> Result<Self> {
        let current_token = lexer.next_token()?;
        Ok(Self {
            lexer,
            current_token,
        })
    }

    fn advance(&mut self) -> Result<()> {
        self.current_token = self.lexer.next_token()?;
        Ok(())
    }

    fn expect_identifier(&mut self, expected: &str) -> Result<()> {
        match &self.current_token {
            Token::Identifier(id) if id == expected => {
                self.advance()?;
                Ok(())
            }
            _ => Err(eyre!("Expected identifier '{}', found {:?}", expected, self.current_token)),
        }
    }

    fn expect_left_bracket(&mut self) -> Result<()> {
        match self.current_token {
            Token::LeftBracket => {
                self.advance()?;
                Ok(())
            }
            _ => Err(eyre!("Expected '[', found {:?}", self.current_token)),
        }
    }

    fn expect_right_bracket(&mut self) -> Result<()> {
        match self.current_token {
            Token::RightBracket => {
                self.advance()?;
                Ok(())
            }
            _ => Err(eyre!("Expected ']', found {:?}", self.current_token)),
        }
    }

    fn parse_value(&mut self) -> Result<String> {
        match &self.current_token {
            Token::Identifier(val) | Token::Number(val) | Token::String(val) => {
                let result = val.clone();
                self.advance()?;
                Ok(result)
            }
            _ => Err(eyre!("Expected value, found {:?}", self.current_token)),
        }
    }


    fn parse_node(&mut self) -> Result<GmlNode> {
        self.expect_identifier("node")?;
        self.expect_left_bracket()?;

        let mut id = None;
        let mut label = None;
        let mut attributes = HashMap::new();

        while self.current_token != Token::RightBracket {
            match &self.current_token {
                Token::Identifier(key) => {
                    let key = key.clone();
                    self.advance()?;
                    let value = self.parse_value()?;

                    match key.as_str() {
                        "id" => {
                            id = Some(value.parse::<u32>()
                                .map_err(|_| eyre!("Invalid node id: {}", value))?);
                        }
                        "label" => {
                            label = Some(value);
                        }
                        _ => {
                            attributes.insert(key, value);
                        }
                    }
                }
                _ => return Err(eyre!("Expected attribute name in node, found {:?}", self.current_token)),
            }
        }

        self.expect_right_bracket()?;

        let id = id.ok_or_else(|| eyre!("Node missing required 'id' attribute"))?;

        // Parse IP and region from attributes
        let ip = parse_ip(&attributes);
        let region = parse_region(&attributes);

        Ok(GmlNode {
            id,
            label,
            ip,
            region,
            attributes,
        })
    }

    fn parse_edge(&mut self) -> Result<GmlEdge> {
        self.expect_identifier("edge")?;
        self.expect_left_bracket()?;
        
        let mut source = None;
        let mut target = None;
        let mut attributes = HashMap::new();
        
        while self.current_token != Token::RightBracket {
            match &self.current_token {
                Token::Identifier(key) => {
                    let key = key.clone();
                    self.advance()?;
                    let value = self.parse_value()?;
                    
                    match key.as_str() {
                        "source" => {
                            source = Some(value.parse::<u32>()
                                .map_err(|_| eyre!("Invalid edge source: {}", value))?);
                        }
                        "target" => {
                            target = Some(value.parse::<u32>()
                                .map_err(|_| eyre!("Invalid edge target: {}", value))?);
                        }
                        _ => {
                            // Special handling for packet_loss: convert percentage strings to floats
                            let processed_value = if key == "packet_loss" && value.ends_with('%') {
                                // Remove '%' and parse as float, then divide by 100
                                if let Ok(percentage) = value.trim_end_matches('%').parse::<f64>() {
                                    format!("{}", percentage / 100.0)
                                } else {
                                    value // Keep original if parsing fails
                                }
                            } else {
                                value
                            };
                            attributes.insert(key, processed_value);
                        }
                    }
                }
                _ => return Err(eyre!("Expected attribute name in edge, found {:?}", self.current_token)),
            }
        }
        
        self.expect_right_bracket()?;
        
        let source = source.ok_or_else(|| eyre!("Edge missing required 'source' attribute"))?;
        let target = target.ok_or_else(|| eyre!("Edge missing required 'target' attribute"))?;
        
        Ok(GmlEdge {
            source,
            target,
            attributes,
        })
    }

    fn parse_graph(&mut self) -> Result<GmlGraph> {
        self.expect_identifier("graph")?;
        self.expect_left_bracket()?;
        
        let mut nodes = Vec::new();
        let mut edges = Vec::new();
        let mut attributes = HashMap::new();
        
        while self.current_token != Token::RightBracket {
            match &self.current_token {
                Token::Identifier(keyword) => {
                    match keyword.as_str() {
                        "node" => {
                            nodes.push(self.parse_node()?);
                        }
                        "edge" => {
                            edges.push(self.parse_edge()?);
                        }
                        _ => {
                            // Parse as graph attribute
                            let key = keyword.clone();
                            self.advance()?;
                            let value = self.parse_value()?;
                            attributes.insert(key, value);
                        }
                    }
                }
                _ => return Err(eyre!("Expected keyword in graph, found {:?}", self.current_token)),
            }
        }
        
        self.expect_right_bracket()?;
        
        Ok(GmlGraph {
            nodes,
            edges,
            attributes,
        })
    }
}

/// Parse a GML file and return a GmlGraph object
pub fn parse_gml_file(path: &str) -> Result<GmlGraph> {
    let content = fs::read_to_string(path)
        .map_err(|e| eyre!("Failed to read GML file '{}': {}", path, e))?;
    
    let lexer = Lexer::new(&content);
    let mut parser = Parser::new(lexer)?;
    
    parser.parse_graph()
}

/// Legacy function for backward compatibility with shadow_agents.rs
pub fn parse_gml(file_path: &Path) -> Result<Graph> {
    let gml_graph = parse_gml_file(file_path.to_str()
        .ok_or_else(|| eyre!("Invalid file path: {:?}", file_path))?)?;
    
    // Convert GmlGraph to legacy Graph format
    let nodes = gml_graph.nodes.into_iter()
        .map(|gml_node| Node { id: gml_node.id as i32 })
        .collect();
    
    Ok(Graph { nodes })
}

/// Group nodes by autonomous system if AS attributes exist
pub fn get_autonomous_systems(graph: &GmlGraph) -> Vec<Vec<u32>> {
    let mut as_groups: HashMap<String, Vec<u32>> = HashMap::new();
    let mut nodes_without_as = Vec::new();

    for node in &graph.nodes {
        if let Some(as_number) = node.attributes.get("AS").or_else(|| node.attributes.get("as")) {
            as_groups.entry(as_number.clone()).or_insert_with(Vec::new).push(node.id);
        } else {
            nodes_without_as.push(node.id);
        }
    }

    let mut result: Vec<Vec<u32>> = as_groups.into_values().collect();

    // Add nodes without AS attributes as separate groups
    for node_id in nodes_without_as {
        result.push(vec![node_id]);
    }

    result
}

/// Validate the network topology
pub fn validate_topology(graph: &GmlGraph) -> Result<(), String> {
    // Check for duplicate node IDs
    let mut node_ids = std::collections::HashSet::new();
    for node in &graph.nodes {
        if !node_ids.insert(node.id) {
            return Err(format!("Duplicate node ID: {}", node.id));
        }
    }
    
    // Check that all edges reference valid nodes
    for edge in &graph.edges {
        if !node_ids.contains(&edge.source) {
            return Err(format!("Edge references non-existent source node: {}", edge.source));
        }
        if !node_ids.contains(&edge.target) {
            return Err(format!("Edge references non-existent target node: {}", edge.target));
        }
    }
    
    // Check for basic connectivity (at least one edge if there are multiple nodes)
    if graph.nodes.len() > 1 && graph.edges.is_empty() {
        return Err("Graph has multiple nodes but no edges - network is disconnected".to_string());
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_parse_simple_gml() {
        let gml_content = r#"
            graph [
                node [ id 0 ]
                node [ id 1 label "Node1" ]
                edge [ source 0 target 1 ]
            ]
        "#;
        
        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();
        
        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();
        
        assert_eq!(graph.nodes.len(), 2);
        assert_eq!(graph.edges.len(), 1);
        assert_eq!(graph.nodes[0].id, 0);
        assert_eq!(graph.nodes[1].id, 1);
        assert_eq!(graph.nodes[1].label, Some("Node1".to_string()));
        assert_eq!(graph.edges[0].source, 0);
        assert_eq!(graph.edges[0].target, 1);
    }

    #[test]
    fn test_parse_gml_with_attributes() {
        let gml_content = r#"
            graph [
                directed 1
                node [ id 0 AS "65001" bandwidth "1000" ]
                node [ id 1 AS "65002" ]
                edge [ source 0 target 1 weight 10 latency "5ms" ]
            ]
        "#;
        
        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();
        
        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();
        
        assert_eq!(graph.attributes.get("directed"), Some(&"1".to_string()));
        assert_eq!(graph.nodes[0].attributes.get("AS"), Some(&"65001".to_string()));
        assert_eq!(graph.nodes[0].attributes.get("bandwidth"), Some(&"1000".to_string()));
        assert_eq!(graph.edges[0].attributes.get("weight"), Some(&"10".to_string()));
        assert_eq!(graph.edges[0].attributes.get("latency"), Some(&"5ms".to_string()));
    }

    #[test]
    fn test_parse_testnet_gml() {
        // Test parsing the actual testnet.gml file if it exists
        if std::path::Path::new("testnet.gml").exists() {
            let graph = parse_gml_file("testnet.gml").unwrap();
            
            println!("Successfully parsed testnet.gml!");
            println!("Nodes: {}", graph.nodes.len());
            for node in &graph.nodes {
                println!("  Node {}: label={:?}, attributes={:?}", node.id, node.label, node.attributes);
            }
            println!("Edges: {}", graph.edges.len());
            for edge in &graph.edges {
                println!("  Edge {} -> {}: attributes={:?}", edge.source, edge.target, edge.attributes);
            }
            
            // Test validation
            validate_topology(&graph).unwrap();
            
            // Test autonomous systems
            let as_groups = get_autonomous_systems(&graph);
            println!("Autonomous systems: {} groups", as_groups.len());
            
            // Test backward compatibility
            let legacy_graph = parse_gml(std::path::Path::new("testnet.gml")).unwrap();
            assert_eq!(legacy_graph.nodes.len(), graph.nodes.len());
            
            // Verify the expected structure from testnet.gml
            assert_eq!(graph.nodes.len(), 2);
            assert_eq!(graph.edges.len(), 4);
            assert!(graph.nodes.iter().any(|n| n.id == 0));
            assert!(graph.nodes.iter().any(|n| n.id == 1));
        } else {
            println!("testnet.gml not found, skipping test");
        }
    }

    #[test]
    fn test_get_autonomous_systems() {
        let mut graph = GmlGraph {
            nodes: vec![
                GmlNode { id: 0, label: None, ip: None, region: None, attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect() },
                GmlNode { id: 1, label: None, ip: None, region: None, attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect() },
                GmlNode { id: 2, label: None, ip: None, region: None, attributes: [("AS".to_string(), "65002".to_string())].iter().cloned().collect() },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };
        
        let as_groups = get_autonomous_systems(&graph);
        assert_eq!(as_groups.len(), 2);
        
        // Check that nodes 0 and 1 are in the same AS
        let as1 = as_groups.iter().find(|group| group.contains(&0)).unwrap();
        assert!(as1.contains(&1));
        
        // Check that node 2 is in a different AS
        let as2 = as_groups.iter().find(|group| group.contains(&2)).unwrap();
        assert_eq!(as2.len(), 1);
    }

    #[test]
    fn test_validate_topology() {
        let graph = GmlGraph {
            nodes: vec![
                GmlNode { id: 0, label: None, ip: None, region: None, attributes: HashMap::new() },
                GmlNode { id: 1, label: None, ip: None, region: None, attributes: HashMap::new() },
            ],
            edges: vec![
                GmlEdge { source: 0, target: 1, attributes: HashMap::new() },
            ],
            attributes: HashMap::new(),
        };

        assert!(validate_topology(&graph).is_ok());

        // Test duplicate node ID
        let invalid_graph = GmlGraph {
            nodes: vec![
                GmlNode { id: 0, label: None, ip: None, region: None, attributes: HashMap::new() },
                GmlNode { id: 0, label: None, ip: None, region: None, attributes: HashMap::new() },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };

        assert!(validate_topology(&invalid_graph).is_err());

        // Test invalid edge reference
        let invalid_graph2 = GmlGraph {
            nodes: vec![
                GmlNode { id: 0, label: None, ip: None, region: None, attributes: HashMap::new() },
            ],
            edges: vec![
                GmlEdge { source: 0, target: 999, attributes: HashMap::new() },
            ],
            attributes: HashMap::new(),
        };

        assert!(validate_topology(&invalid_graph2).is_err());
    }

    #[test]
    fn test_backward_compatibility() {
        let gml_content = r#"
            graph [
                node [ id 0 ]
                node [ id 1 ]
                edge [ source 0 target 1 ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let legacy_graph = parse_gml(temp_file.path()).unwrap();

        assert_eq!(legacy_graph.nodes.len(), 2);
        assert_eq!(legacy_graph.nodes[0].id, 0);
        assert_eq!(legacy_graph.nodes[1].id, 1);
    }

    #[test]
    fn test_gml_node_get_ip() {
        // Test node with IP in different attribute keys
        let mut node = GmlNode {
            id: 0,
            label: None,
            ip: None,
            region: None,
            attributes: HashMap::new(),
        };

        // No IP initially
        assert!(node.get_ip().is_none());
        assert!(!node.has_ip());

        // Add IP with "ip" key
        node.attributes.insert("ip".to_string(), "192.168.1.1".to_string());
        // Note: get_ip() now returns from dedicated field, not attributes
        assert_eq!(node.get_ip(), None); // Should be None since dedicated field is None

        // Test with different keys - these should be None since get_ip() uses dedicated field
        let mut node2 = GmlNode {
            id: 1,
            label: None,
            ip: None,
            region: None,
            attributes: [("ip_addr".to_string(), "10.0.0.1".to_string())].iter().cloned().collect(),
        };
        assert_eq!(node2.get_ip(), None);

        let mut node3 = GmlNode {
            id: 2,
            label: None,
            ip: None,
            region: None,
            attributes: [("address".to_string(), "172.16.0.1".to_string())].iter().cloned().collect(),
        };
        assert_eq!(node3.get_ip(), None);

        // Test invalid IP - should be None
        let mut node4 = GmlNode {
            id: 3,
            label: None,
            ip: None,
            region: None,
            attributes: [("ip".to_string(), "invalid.ip".to_string())].iter().cloned().collect(),
        };
        assert!(node4.get_ip().is_none());
    }


    #[test]
    fn test_ip_utils_validation() {
        // Test valid IPs
        assert!(ip_utils::is_valid_ip("192.168.1.1"));
        assert!(ip_utils::is_valid_ip("10.0.0.1"));
        assert!(ip_utils::is_valid_ip("::1"));
        assert!(ip_utils::is_valid_ip("2001:db8::1"));
        assert!(ip_utils::is_valid_ipv4("192.168.1.1"));
        assert!(ip_utils::is_valid_ipv6("::1"));
        assert!(!ip_utils::is_valid_ipv4("::1"));
        assert!(!ip_utils::is_valid_ipv6("192.168.1.1"));

        // Test invalid IPs
        assert!(!ip_utils::is_valid_ip("invalid.ip"));
        assert!(!ip_utils::is_valid_ip("256.1.1.1"));
        assert!(!ip_utils::is_valid_ip("192.168.1.256"));
        assert!(!ip_utils::is_valid_ipv4("invalid.ip"));
        assert!(!ip_utils::is_valid_ipv6("invalid:ip"));
    }

    #[test]
    fn test_ip_utils_extract_valid_ips() {
        let values = vec![
            "192.168.1.1".to_string(),
            "invalid.ip".to_string(),
            "10.0.0.1".to_string(),
            "not an ip".to_string(),
            "::1".to_string(),
        ];

        let valid_ips = ip_utils::extract_valid_ips(&values);
        assert_eq!(valid_ips.len(), 3);
        assert!(valid_ips.contains(&"192.168.1.1".to_string()));
        assert!(valid_ips.contains(&"10.0.0.1".to_string()));
        assert!(valid_ips.contains(&"::1".to_string()));
    }

    #[test]
    fn test_ip_utils_format_with_subnet() {
        // Test IPv4
        assert_eq!(ip_utils::format_with_subnet("192.168.1.1").unwrap(), "192.168.1.1/24");

        // Test IPv6
        assert_eq!(ip_utils::format_with_subnet("::1").unwrap(), "::1/64");

        // Test invalid IP
        assert!(ip_utils::format_with_subnet("invalid.ip").is_err());
    }

    #[test]
    fn test_ip_utils_is_private_ip() {
        // Test private IPv4 addresses
        assert!(ip_utils::is_private_ip("10.0.0.1").unwrap());
        assert!(ip_utils::is_private_ip("172.16.0.1").unwrap());
        assert!(ip_utils::is_private_ip("192.168.1.1").unwrap());

        // Test public IPv4 addresses
        assert!(!ip_utils::is_private_ip("8.8.8.8").unwrap());
        assert!(!ip_utils::is_private_ip("203.0.113.1").unwrap());

        // Test private IPv6 addresses
        assert!(ip_utils::is_private_ip("fc00::1").unwrap());
        assert!(ip_utils::is_private_ip("fd00::1").unwrap());

        // Test public IPv6 addresses
        assert!(!ip_utils::is_private_ip("2001:db8::1").unwrap());

        // Test invalid IP
        assert!(ip_utils::is_private_ip("invalid.ip").is_err());
    }

    #[test]
    fn test_ip_utils_generate_ip_range() {
        // Test IPv4 range
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

        // Test IPv6 (should return error)
        assert!(ip_utils::generate_ip_range("::1", 5).is_err());
    }

    #[test]
    fn test_gml_node_is_valid_ip() {
        // Test the static method on GmlNode
        assert!(GmlNode::is_valid_ip("192.168.1.1"));
        assert!(GmlNode::is_valid_ip("::1"));
        assert!(!GmlNode::is_valid_ip("invalid.ip"));
    }

    #[test]
    fn test_parse_node_with_ip() {
        let gml_content = r#"
            graph [
                node [ id 0 ip "192.168.1.1" ]
                node [ id 1 ip_addr "10.0.0.1" ]
                node [ id 2 address "172.16.0.1" ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();

        assert_eq!(graph.nodes.len(), 3);
        assert_eq!(graph.nodes[0].ip, Some("192.168.1.1".to_string()));
        assert_eq!(graph.nodes[1].ip, Some("10.0.0.1".to_string()));
        assert_eq!(graph.nodes[2].ip, Some("172.16.0.1".to_string()));
    }

    #[test]
    fn test_parse_node_with_region() {
        let gml_content = r#"
            graph [
                node [ id 0 region "North America" ]
                node [ id 1 geographic_region "Europe" ]
                node [ id 2 location "Asia" ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();

        assert_eq!(graph.nodes.len(), 3);
        assert_eq!(graph.nodes[0].region, Some("North America".to_string()));
        assert_eq!(graph.nodes[1].region, Some("Europe".to_string()));
        assert_eq!(graph.nodes[2].region, Some("Asia".to_string()));
    }

    #[test]
    fn test_parse_node_without_ip() {
        let gml_content = r#"
            graph [
                node [ id 0 label "Node0" ]
                node [ id 1 AS "65001" ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();

        assert_eq!(graph.nodes.len(), 2);
        assert_eq!(graph.nodes[0].ip, None);
        assert_eq!(graph.nodes[1].ip, None);
    }

    #[test]
    fn test_invalid_ip_format() {
        let gml_content = r#"
            graph [
                node [ id 0 ip "invalid.ip.address" ]
                node [ id 1 ip "192.168.1.1" ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();

        assert_eq!(graph.nodes.len(), 2);
        // Invalid IP should be None, valid IP should be parsed
        assert_eq!(graph.nodes[0].ip, None);
        assert_eq!(graph.nodes[1].ip, Some("192.168.1.1".to_string()));
    }

    #[test]
    fn test_parse_node_complete() {
        let gml_content = r#"
            graph [
                node [
                    id 0
                    label "Router1"
                    ip "192.168.1.1"
                    region "North America"
                    AS "65001"
                    bandwidth "1000Mbit"
                ]
            ]
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", gml_content).unwrap();

        let graph = parse_gml_file(temp_file.path().to_str().unwrap()).unwrap();

        assert_eq!(graph.nodes.len(), 1);
        let node = &graph.nodes[0];
        assert_eq!(node.id, 0);
        assert_eq!(node.label, Some("Router1".to_string()));
        assert_eq!(node.ip, Some("192.168.1.1".to_string()));
        assert_eq!(node.region, Some("North America".to_string()));
        assert_eq!(node.attributes.get("AS"), Some(&"65001".to_string()));
        assert_eq!(node.attributes.get("bandwidth"), Some(&"1000Mbit".to_string()));
    }

    #[test]
    fn test_gml_node_get_ip_region_accessors() {
        let node = GmlNode {
            id: 0,
            label: None,
            ip: Some("192.168.1.1".to_string()),
            region: Some("North America".to_string()),
            attributes: HashMap::new(),
        };

        assert_eq!(node.get_ip(), Some("192.168.1.1"));
        assert_eq!(node.get_region(), Some("North America"));
    }

    #[test]
    fn test_gml_node_get_ip_region_accessors_none() {
        let node = GmlNode {
            id: 0,
            label: None,
            ip: None,
            region: None,
            attributes: HashMap::new(),
        };

        assert_eq!(node.get_ip(), None);
        assert_eq!(node.get_region(), None);
    }
}