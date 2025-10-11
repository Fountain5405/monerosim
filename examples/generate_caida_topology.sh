#!/bin/bash
# File: examples/generate_caida_topology.sh
# Description: Example script for generating CAIDA-based network topologies

set -e

echo "Monerosim CAIDA Topology Generation Examples"
echo "============================================"
echo ""

# Check if CAIDA data exists
if [ ! -f "gml_processing/caida_aslinks.txt" ]; then
    echo "Error: CAIDA AS-links data not found at gml_processing/caida_aslinks.txt"
    echo "Please ensure the CAIDA dataset is available."
    exit 1
fi

# Function to generate topology
generate_topology() {
    local nodes=$1
    local output=$2
    local description=$3

    echo "Generating ${description} (${nodes} nodes)..."
    echo "Command: python gml_processing/create_large_scale_caida_gml.py \\"
    echo "  --caida-file gml_processing/caida_aslinks.txt \\"
    echo "  --output ${output} \\"
    echo "  --nodes ${nodes}"

    python gml_processing/create_large_scale_caida_gml.py \
        --caida-file gml_processing/caida_aslinks.txt \
        --output ${output} \
        --nodes ${nodes}

    echo "✓ Generated ${output}"
    echo ""
}

# Example 1: Small research topology
generate_topology 100 "examples/topology_research_100.gml" "small research topology"

# Example 2: Medium-scale simulation
generate_topology 500 "examples/topology_medium_500.gml" "medium-scale simulation topology"

# Example 3: Large-scale network
generate_topology 2000 "examples/topology_large_2000.gml" "large-scale network topology"

# Example 4: Maximum scale topology
generate_topology 5000 "examples/topology_max_5000.gml" "maximum scale topology"

echo "Topology Generation Complete!"
echo ""
echo "Generated files:"
echo "- examples/topology_research_100.gml (100 nodes)"
echo "- examples/topology_medium_500.gml (500 nodes)"
echo "- examples/topology_large_2000.gml (2000 nodes)"
echo "- examples/topology_max_5000.gml (5000 nodes)"
echo ""
echo "Use these topologies in your config.yaml:"
echo "network:"
echo "  path: \"examples/topology_research_100.gml\""
echo "  peer_mode: \"Dynamic\""
echo "  topology: \"Mesh\""