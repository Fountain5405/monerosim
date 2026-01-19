#!/bin/bash
# Launch the AI config generator
# Usage: ./smart_config_tool.sh [prompt] [options]
#
# Examples:
#   ./smart_config_tool.sh                              # Interactive mode
#   ./smart_config_tool.sh "5 miners, 20 users, 8h"    # Direct generation
#   ./smart_config_tool.sh --model llama-3.3-70b-versatile "your prompt"

cd "$(dirname "$0")"
python3 -m scripts.ai_config "$@"
