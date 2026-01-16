//! IP address allocation logic.
//!
//! This file contains the core IP allocation algorithms, including
//! geographic distribution across continents and subnet management
//! for different network configurations.

use crate::gml_parser::{GmlGraph, GmlNode};
use super::registry::{AgentType, GlobalIpRegistry};
use super::as_manager::AsSubnetManager;

/// Get AS number from a GML node
fn get_node_as_number(gml_node: &GmlNode) -> Option<String> {
    gml_node.attributes.get("AS").or_else(|| gml_node.attributes.get("as")).cloned()
}

/// Get IP address for an agent using the centralized Global IP Registry
/// Priority order:
/// 1) Subnet group (if specified) - agents with the same group share a /24 subnet
/// 2) Pre-allocated GML IP
/// 3) AS-aware IP
/// 4) Dynamic IP assignment
pub fn get_agent_ip(
    agent_type: AgentType,
    agent_id: &str,
    agent_index: usize,
    network_node_id: u32,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    subnet_group: Option<&str>,
) -> String {
    // Priority 0: If subnet_group is specified, use subnet group allocation
    if let Some(group) = subnet_group {
        match ip_registry.assign_subnet_group_ip(group, agent_id) {
            Ok(ip) => {
                log::info!("Assigned subnet group IP {} to agent {} (group: {})", ip, agent_id, group);
                return ip;
            }
            Err(e) => {
                log::warn!("Failed to assign subnet group IP for agent {}: {}. Falling back to default allocation.", agent_id, e);
                // Fall through to default allocation
            }
        }
    }
    // For GML topologies, try pre-allocated and AS-aware assignment first
    if using_gml_topology {
        if let Some(gml) = gml_graph {
            // Find the GML node with the matching network_node_id
            if let Some(gml_node) = gml.nodes.iter().find(|node| node.id == network_node_id) {
                // Priority 1: Check for pre-allocated IP from GML node
                if let Some(pre_allocated_ip) = gml_node.get_ip() {
                    // Validate IP format
                    if !GmlNode::is_valid_ip(pre_allocated_ip) {
                        log::warn!("Invalid pre-allocated IP '{}' for node {} in GML file", pre_allocated_ip, network_node_id);
                    } else {
                        // Check for conflicts with existing assignments
                        if let Some(conflicting_agent) = ip_registry.get_agent_for_ip(pre_allocated_ip) {
                            if conflicting_agent != agent_id {
                                log::warn!("IP conflict detected: {} already assigned to agent {}, agent {} (node {}) will use fallback IP",
                                           pre_allocated_ip, conflicting_agent, agent_id, network_node_id);
                                // Continue to fallback instead of panicking
                            } else {
                                log::debug!("Using pre-allocated IP {} for agent {} (node {})", pre_allocated_ip, agent_id, network_node_id);
                                return pre_allocated_ip.to_string();
                            }
                        } else {
                            // Register this IP in our central registry
                            if let Err(conflict) = ip_registry.register_pre_allocated_ip(pre_allocated_ip, agent_id) {
                                log::error!("Failed to register pre-allocated IP {} for agent {}: {}", pre_allocated_ip, agent_id, conflict);
                                // Continue to fallback
                            } else {
                                log::info!("Assigned pre-allocated IP {} to agent {} (node {})", pre_allocated_ip, agent_id, network_node_id);
                                return pre_allocated_ip.to_string();
                            }
                        }
                    }
                }

                // Priority 2: Try AS-aware assignment using the legacy AS subnet manager
                if let Some(as_number) = get_node_as_number(gml_node) {
                    if let Some(as_ip) = subnet_manager.assign_as_aware_ip(&as_number) {
                        // Check if this AS IP conflicts with our registry
                        if let Some(conflicting_agent) = ip_registry.get_agent_for_ip(&as_ip) {
                            if conflicting_agent != agent_id {
                                log::warn!("AS-aware IP {} for agent {} conflicts with existing assignment to {}", as_ip, agent_id, conflicting_agent);
                            } else {
                                log::debug!("Using AS-aware IP {} for agent {} (AS {}, node {})", as_ip, agent_id, as_number, network_node_id);
                                return as_ip;
                            }
                        } else {
                            // Register this IP in our central registry
                            if let Err(conflict) = ip_registry.register_pre_allocated_ip(&as_ip, agent_id) {
                                log::warn!("Failed to register AS-aware IP {} for agent {}: {}", as_ip, agent_id, conflict);
                                // Continue to fallback
                            } else {
                                log::info!("Assigned AS-aware IP {} to agent {} (AS {}, node {})", as_ip, agent_id, as_number, network_node_id);
                                return as_ip;
                            }
                        }
                    }
                }
            } else {
                log::warn!("Agent {} assigned to node {} which doesn't exist in GML topology", agent_id, network_node_id);
            }
        }
    }

    // Priority 3: Use the centralized IP registry for dynamic assignment
    match ip_registry.assign_ip(agent_type, agent_id) {
        Ok(ip) => {
            log::info!("Assigned dynamic IP {} to agent {} using global registry", ip, agent_id);
            ip
        },
        Err(error) => {
            // Fallback to legacy assignment if centralized registry fails
            log::warn!("IP registry assignment failed for {}: {}. Using geographic fallback.", agent_id, error);

            // Fallback logic using geographic subnets
            let fallback_ip = match agent_type {
                AgentType::UserAgent => format!("192.168.10.{}", 10 + (agent_index % 245)),
                AgentType::MinerDistributor => format!("192.168.20.{}", 10 + (agent_index % 245)),
                AgentType::PureScriptAgent => format!("192.168.30.{}", 10 + (agent_index % 245)),
                AgentType::Infrastructure => format!("192.168.40.{}", 10 + (agent_index % 245)),
            };

            // Try to register the fallback IP
            if let Some(conflicting_agent) = ip_registry.get_agent_for_ip(&fallback_ip) {
                if conflicting_agent != agent_id {
                    log::error!("Fallback IP {} conflicts with existing assignment to {}", fallback_ip, conflicting_agent);
                }
            } else {
                // Use the public method to register
                let _ = ip_registry.register_pre_allocated_ip(&fallback_ip, agent_id);
            }

            log::info!("Assigned fallback IP {} to agent {}", fallback_ip, agent_id);
            fallback_ip
        }
    }
}
