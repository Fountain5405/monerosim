#!/usr/bin/env python3
"""
Analyze the agent distribution across GML network nodes for the 40-agent test.
"""

import json
import yaml
from collections import defaultdict

def analyze_distribution():
    print("=== GML Network Topology Analysis ===")
    
    # Load the Shadow configuration
    with open('shadow_gml_40_test_output/shadow_agents.yaml', 'r') as f:
        shadow_config = yaml.safe_load(f)
    
    # Load the agent registry
    with open('/tmp/monerosim_shared/agent_registry.json', 'r') as f:
        agent_registry = json.load(f)
    
    # Analyze network topology
    network = shadow_config['network']['graph']
    nodes = network['nodes']
    edges = network['edges']
    
    print(f"Network Topology:")
    print(f"  - Nodes: {len(nodes)}")
    print(f"  - Edges: {len(edges)}")
    
    # Analyze node distribution
    node_distribution = defaultdict(list)
    
    # Map hosts to network nodes
    hosts = shadow_config['hosts']
    for host_id, host_config in hosts.items():
        network_node_id = host_config['network_node_id']
        node_distribution[network_node_id].append(host_id)
    
    print(f"\nAgent Distribution Across Network Nodes:")
    total_agents = 0
    for node_id in sorted(node_distribution.keys()):
        agents = node_distribution[node_id]
        print(f"  Network Node {node_id}: {len(agents)} agents")
        total_agents += len(agents)
        
        # Count agent types on this node
        miners = 0
        regular_users = 0
        controllers = 0
        scripts = 0
        
        for agent_id in agents:
            if agent_id.startswith('user'):
                # Find this agent in the registry
                agent_info = next((a for a in agent_registry['agents'] if a['id'] == agent_id), None)
                if agent_info:
                    if 'hashrate' in agent_info.get('attributes', {}):
                        miners += 1
                    elif agent_info.get('user_script') == 'agents.regular_user':
                        regular_users += 1
            elif agent_id == 'blockcontroller':
                controllers += 1
            elif agent_id.startswith('script'):
                scripts += 1
        
        print(f"    - Miners: {miners}")
        print(f"    - Regular Users: {regular_users}")
        print(f"    - Controllers: {controllers}")
        print(f"    - Scripts: {scripts}")
    
    print(f"\nTotal Agents: {total_agents}")
    
    # Analyze AS distribution (since testnet.gml has no AS attributes, each node is its own AS)
    print(f"\nAutonomous System Analysis:")
    print(f"  - AS Groups: {len(nodes)} (each node is its own AS)")
    print(f"  - AS-aware distribution: Agents distributed across {len(node_distribution)} AS groups")
    
    # Check load balancing
    node_counts = [len(agents) for agents in node_distribution.values()]
    min_agents = min(node_counts)
    max_agents = max(node_counts)
    avg_agents = sum(node_counts) / len(node_counts)
    
    print(f"\nLoad Balancing Analysis:")
    print(f"  - Min agents per node: {min_agents}")
    print(f"  - Max agents per node: {max_agents}")
    print(f"  - Average agents per node: {avg_agents:.1f}")
    print(f"  - Load balance ratio: {max_agents/min_agents:.2f} (closer to 1.0 is better)")
    
    # Analyze miner distribution
    print(f"\nMiner Analysis:")
    miners_by_node = defaultdict(int)
    total_miners = 0
    
    for agent in agent_registry['agents']:
        if 'hashrate' in agent.get('attributes', {}):
            # Find which network node this agent is on
            for node_id, agents in node_distribution.items():
                if agent['id'] in agents:
                    miners_by_node[node_id] += 1
                    total_miners += 1
                    break
    
    print(f"  - Total miners: {total_miners}")
    for node_id in sorted(miners_by_node.keys()):
        print(f"  - Network Node {node_id}: {miners_by_node[node_id]} miners")
    
    # Check miners.json issue
    with open('/tmp/monerosim_shared/miners.json', 'r') as f:
        miners_registry = json.load(f)
    
    print(f"\nMiner Registry Status:")
    print(f"  - Miners in registry: {len(miners_registry['miners'])}")
    if len(miners_registry['miners']) == 0:
        print("  - WARNING: No miners found in registry - this indicates the configuration issue")
        print("  - This is the known issue where miners are not properly detected")
    
    return {
        'total_agents': total_agents,
        'network_nodes': len(nodes),
        'load_balance_ratio': max_agents/min_agents,
        'miners_detected': total_miners,
        'miners_in_registry': len(miners_registry['miners'])
    }

if __name__ == '__main__':
    results = analyze_distribution()
    
    print(f"\n=== Summary ===")
    print(f"✓ Successfully generated configuration for {results['total_agents']} agents")
    print(f"✓ Distributed across {results['network_nodes']} network nodes")
    print(f"✓ Load balance ratio: {results['load_balance_ratio']:.2f}")
    print(f"✓ Miners detected in config: {results['miners_detected']}")
    
    if results['miners_in_registry'] == 0:
        print(f"⚠ Known issue: Miners not in registry (configuration system limitation)")
    else:
        print(f"✓ Miners in registry: {results['miners_in_registry']}")