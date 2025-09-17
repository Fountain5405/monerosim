use std::collections::HashMap;
use std::fs;
use std::path::Path;
use color_eyre::eyre::{Result, eyre};

/// Represents a node in a GML graph
#[derive(Debug, Clone)]
pub struct GmlNode {
    pub id: u32,
    pub label: Option<String>,
    pub attributes: HashMap<String, String>,
}

impl GmlNode {
    /// Extract IP address from node attributes
    ///
    /// Looks for IP addresses in common attribute keys:
    /// - "ip"
    /// - "ip_addr"
    /// - "address"
    /// - "ip_address"
    ///
    /// Returns the first valid IP address found, or None if no valid IP is present
    pub fn get_ip(&self) -> Option<String> {
        let possible_keys = ["ip", "ip_addr", "address", "ip_address"];

        for key in &possible_keys {
            if let Some(value) = self.attributes.get(*key) {
                if Self::is_valid_ip(value) {
                    return Some(value.clone());
                }
            }
        }

        None
    }

    /// Set IP address in node attributes
    ///
    /// Stores the IP address under the "ip" attribute key
    /// Returns an error if the IP address is not valid
    pub fn set_ip(&mut self, ip: &str) -> Result<(), String> {
        if !Self::is_valid_ip(ip) {
            return Err(format!("Invalid IP address: {}", ip));
        }

        self.attributes.insert("ip".to_string(), ip.to_string());
        Ok(())
    }

    /// Check if a string is a valid IP address (IPv4 or IPv6)
    pub fn is_valid_ip(ip: &str) -> bool {
        ip.parse::<std::net::IpAddr>().is_ok()
    }

    /// Get all IP addresses from node attributes
    ///
    /// Returns a vector of all valid IP addresses found in any attribute
    pub fn get_all_ips(&self) -> Vec<String> {
        self.attributes
            .values()
            .filter(|value| Self::is_valid_ip(value))
            .cloned()
            .collect()
    }

    /// Check if the node has any valid IP address
    pub fn has_ip(&self) -> bool {
        self.get_ip().is_some()
    }
}

/// IP address validation and utility functions
pub mod ip_utils {
    use std::net::IpAddr;

    /// Validate if a string is a valid IP address (IPv4 or IPv6)
    pub fn is_valid_ip(ip: &str) -> bool {
        ip.parse::<IpAddr>().is_ok()
    }

    /// Validate if a string is a valid IPv4 address
    pub fn is_valid_ipv4(ip: &str) -> bool {
        match ip.parse::<IpAddr>() {
            Ok(addr) => addr.is_ipv4(),
            Err(_) => false,
        }
    }

    /// Validate if a string is a valid IPv6 address
    pub fn is_valid_ipv6(ip: &str) -> bool {
        match ip.parse::<IpAddr>() {
            Ok(addr) => addr.is_ipv6(),
            Err(_) => false,
        }
    }

    /// Extract all valid IP addresses from a vector of strings
    pub fn extract_valid_ips(values: &[String]) -> Vec<String> {
        values
            .iter()
            .filter(|value| is_valid_ip(value))
            .cloned()
            .collect()
    }

    /// Format an IP address with a subnet mask (assumes /24 for IPv4, /64 for IPv6)
    pub fn format_with_subnet(ip: &str) -> Result<String, String> {
        match ip.parse::<IpAddr>() {
            Ok(addr) => {
                if addr.is_ipv4() {
                    Ok(format!("{}/24", ip))
                } else {
                    Ok(format!("{}/64", ip))
                }
            }
            Err(_) => Err(format!("Invalid IP address: {}", ip)),
        }
    }

    /// Check if an IP address is in a private range
    pub fn is_private_ip(ip: &str) -> Result<bool, String> {
        match ip.parse::<IpAddr>() {
            Ok(addr) => {
                match addr {
                    IpAddr::V4(ipv4) => {
                        let octets = ipv4.octets();
                        // 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
                        Ok(octets[0] == 10 ||
                           (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31) ||
                           (octets[0] == 192 && octets[1] == 168))
                    }
                    IpAddr::V6(ipv6) => {
                        // fc00::/7 (unique local addresses)
                        let segments = ipv6.segments();
                        Ok(segments[0] & 0xfe00 == 0xfc00)
                    }
                }
            }
            Err(_) => Err(format!("Invalid IP address: {}", ip)),
        }
    }

    /// Generate a sequential IP address range
    ///
    /// # Examples
    /// ```
    /// use monerosim::gml_parser::ip_utils;
    /// let range = ip_utils::generate_ip_range("192.168.1.1", 5).unwrap();
    /// assert_eq!(range, vec!["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5"]);
    /// ```
    pub fn generate_ip_range(start_ip: &str, count: usize) -> Result<Vec<String>, String> {
        let start_addr: IpAddr = start_ip.parse().map_err(|_| format!("Invalid start IP: {}", start_ip))?;

        match start_addr {
            IpAddr::V4(ipv4) => {
                let mut result = Vec::new();
                let mut current = ipv4;

                for _ in 0..count {
                    result.push(current.to_string());
                    // Increment the last octet
                    let octets = current.octets();
                    if octets[3] == 255 {
                        return Err("IP range would exceed 255".to_string());
                    }
                    current = std::net::Ipv4Addr::new(octets[0], octets[1], octets[2], octets[3] + 1);
                }

                Ok(result)
            }
            IpAddr::V6(_) => {
                Err("IPv6 range generation not implemented".to_string())
            }
        }
    }
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

    fn parse_attributes(&mut self) -> Result<HashMap<String, String>> {
        let mut attributes = HashMap::new();
        
        while let Token::Identifier(key) = &self.current_token.clone() {
            let key = key.clone();
            self.advance()?;
            
            let value = self.parse_value()?;
            attributes.insert(key, value);
        }
        
        Ok(attributes)
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
        
        Ok(GmlNode {
            id,
            label,
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
                GmlNode { id: 0, label: None, attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect() },
                GmlNode { id: 1, label: None, attributes: [("AS".to_string(), "65001".to_string())].iter().cloned().collect() },
                GmlNode { id: 2, label: None, attributes: [("AS".to_string(), "65002".to_string())].iter().cloned().collect() },
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
                GmlNode { id: 0, label: None, attributes: HashMap::new() },
                GmlNode { id: 1, label: None, attributes: HashMap::new() },
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
                GmlNode { id: 0, label: None, attributes: HashMap::new() },
                GmlNode { id: 0, label: None, attributes: HashMap::new() },
            ],
            edges: vec![],
            attributes: HashMap::new(),
        };
        
        assert!(validate_topology(&invalid_graph).is_err());
        
        // Test invalid edge reference
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
            attributes: HashMap::new(),
        };

        // No IP initially
        assert!(node.get_ip().is_none());
        assert!(!node.has_ip());

        // Add IP with "ip" key
        node.attributes.insert("ip".to_string(), "192.168.1.1".to_string());
        assert_eq!(node.get_ip(), Some("192.168.1.1".to_string()));
        assert!(node.has_ip());

        // Test with different keys
        let mut node2 = GmlNode {
            id: 1,
            label: None,
            attributes: [("ip_addr".to_string(), "10.0.0.1".to_string())].iter().cloned().collect(),
        };
        assert_eq!(node2.get_ip(), Some("10.0.0.1".to_string()));

        let mut node3 = GmlNode {
            id: 2,
            label: None,
            attributes: [("address".to_string(), "172.16.0.1".to_string())].iter().cloned().collect(),
        };
        assert_eq!(node3.get_ip(), Some("172.16.0.1".to_string()));

        // Test invalid IP
        let mut node4 = GmlNode {
            id: 3,
            label: None,
            attributes: [("ip".to_string(), "invalid.ip".to_string())].iter().cloned().collect(),
        };
        assert!(node4.get_ip().is_none());
    }

    #[test]
    fn test_gml_node_set_ip() {
        let mut node = GmlNode {
            id: 0,
            label: None,
            attributes: HashMap::new(),
        };

        // Set valid IP
        assert!(node.set_ip("192.168.1.1").is_ok());
        assert_eq!(node.attributes.get("ip"), Some(&"192.168.1.1".to_string()));

        // Try to set invalid IP
        assert!(node.set_ip("invalid.ip").is_err());
        // Original IP should still be there
        assert_eq!(node.attributes.get("ip"), Some(&"192.168.1.1".to_string()));
    }

    #[test]
    fn test_gml_node_get_all_ips() {
        let mut node = GmlNode {
            id: 0,
            label: None,
            attributes: HashMap::new(),
        };

        // No IPs initially
        assert!(node.get_all_ips().is_empty());

        // Add multiple attributes, some with IPs
        node.attributes.insert("ip".to_string(), "192.168.1.1".to_string());
        node.attributes.insert("name".to_string(), "router1".to_string());
        node.attributes.insert("backup_ip".to_string(), "10.0.0.1".to_string());
        node.attributes.insert("invalid_ip".to_string(), "not.an.ip".to_string());

        let ips = node.get_all_ips();
        assert_eq!(ips.len(), 2);
        assert!(ips.contains(&"192.168.1.1".to_string()));
        assert!(ips.contains(&"10.0.0.1".to_string()));
        assert!(!ips.contains(&"not.an.ip".to_string()));
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
}