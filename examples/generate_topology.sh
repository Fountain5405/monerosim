#!/bin/bash

# Large-Scale Topology Generation Script
# This script demonstrates automated topology generation for network scaling
# Usage: ./generate_topology.sh [nodes] [output_file]

set -e  # Exit on any error

# Default values
DEFAULT_NODES=1000
DEFAULT_OUTPUT="topology.gml"

# Configuration
NODES=${1:-$DEFAULT_NODES}
OUTPUT_FILE=${2:-$DEFAULT_OUTPUT}
SEED=${3:-42}  # Default seed for reproducibility
AVG_DEGREE=4

echo "=== Monerosim Large-Scale Topology Generator ==="
echo "Nodes: $NODES"
echo "Output: $OUTPUT_FILE"
echo "Seed: $SEED"
echo "Average Degree: $AVG_DEGREE"
echo

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Python virtual environment not found at ./venv"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r scripts/requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "Activating Python virtual environment..."
source venv/bin/activate

# Check if topology generation script exists
if [ ! -f "scripts/create_large_scale_gml.py" ]; then
    echo "Error: Topology generation script not found at scripts/create_large_scale_gml.py"
    exit 1
fi

# Generate topology
echo "Generating topology with $NODES nodes..."
echo "This may take a few minutes for large topologies..."
echo

START_TIME=$(date +%s)

python scripts/create_large_scale_gml.py \
    --output "$OUTPUT_FILE" \
    --nodes "$NODES" \
    --avg-degree "$AVG_DEGREE" \
    --seed "$SEED"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo
echo "=== Topology Generation Complete ==="
echo "Output file: $OUTPUT_FILE"
echo "Generation time: ${DURATION}s"
echo

# Validate the generated file
echo "Validating generated topology..."
if [ -f "$OUTPUT_FILE" ]; then
    # Basic validation - check file size and format
    FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null || echo "unknown")

    # Count nodes and edges
    NODE_COUNT=$(grep -c "^node \[" "$OUTPUT_FILE" 2>/dev/null || echo "0")
    EDGE_COUNT=$(grep -c "^edge \[" "$OUTPUT_FILE" 2>/dev/null || echo "0")

    echo "File size: $FILE_SIZE bytes"
    echo "Nodes found: $NODE_COUNT"
    echo "Edges found: $EDGE_COUNT"

    if [ "$NODE_COUNT" -eq "$NODES" ]; then
        echo "✓ Node count matches expected value"
    else
        echo "⚠ Warning: Node count mismatch (expected: $NODES, found: $NODE_COUNT)"
    fi

    # Check for geographic distribution
    REGIONS=$(grep "region" "$OUTPUT_FILE" | sed 's/.*region "\([^"]*\)".*/\1/' | sort | uniq | wc -l)
    echo "Geographic regions: $REGIONS"

    if [ "$REGIONS" -gt 1 ]; then
        echo "✓ Geographic distribution detected"
    else
        echo "⚠ Warning: Limited geographic distribution"
    fi

else
    echo "Error: Output file was not created"
    exit 1
fi

echo
echo "=== Usage Instructions ==="
echo "1. Use this topology in your Monerosim configuration:"
echo "   network:"
echo "     path: \"$OUTPUT_FILE\""
echo
echo "2. Generate Shadow configuration:"
echo "   ./target/release/monerosim --config your_config.yaml"
echo
echo "3. Run the simulation:"
echo "   shadow shadow_output/shadow_agents.yaml"
echo
echo "4. For detailed information, see:"
echo "   - NETWORK_SCALING_GUIDE.md"
echo "   - docs/TOPOLOGY_GENERATION.md"
echo
echo "=== Example Configurations ==="
echo "Small test:   ./generate_topology.sh 100 small_test.gml"
echo "Medium sim:   ./generate_topology.sh 1000 medium_sim.gml"
echo "Large scale:  ./generate_topology.sh 5000 large_scale.gml"
echo "Reproducible: ./generate_topology.sh 5000 research_topo.gml 12345"

echo
echo "Topology generation completed successfully!"