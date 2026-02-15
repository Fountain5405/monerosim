#!/usr/bin/env python3
"""
Regenerate Enhanced Blocks File

This script manually regenerates the blocks_with_transactions.json file
from the existing blocks_found.json and transaction_tracking.json files.
This is needed when the monitor agent wasn't running during the simulation
or when the enhanced blocks file is incomplete.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

from agents.base_agent import DEFAULT_SHARED_DIR


def regenerate_enhanced_blocks(shared_dir: str = DEFAULT_SHARED_DIR):
    """
    Regenerate the enhanced blocks file from existing data.
    
    Args:
        shared_dir: Path to the shared directory containing monitor data
    """
    shared_path = Path(shared_dir)
    
    # Check required files
    blocks_file = shared_path / "blocks_found.json"
    tracking_file = shared_path / "transaction_tracking.json"
    enhanced_file = shared_path / "blocks_with_transactions.json"
    
    if not blocks_file.exists():
        print(f"Error: {blocks_file} not found")
        return False
    
    # Load blocks
    print(f"Loading blocks from {blocks_file}")
    with open(blocks_file, 'r') as f:
        blocks = json.load(f)
    print(f"Loaded {len(blocks)} blocks")
    
    # Load transaction tracking data if available
    tx_to_block_mapping = {}
    if tracking_file.exists():
        print(f"Loading transaction tracking from {tracking_file}")
        try:
            with open(tracking_file, 'r') as f:
                tracking_data = json.load(f)
            tx_to_block_mapping = tracking_data.get("tx_to_block_mapping", {})
            print(f"Loaded transaction mapping for {len(tx_to_block_mapping)} blocks")
        except Exception as e:
            print(f"Warning: Failed to load tracking data: {e}")
    else:
        print("Warning: No transaction tracking data found")
    
    # Generate enhanced blocks
    enhanced_blocks = []
    for i, block in enumerate(blocks):
        block_hash = block.get("block_hash", f"block_{i}")
        enhanced_block = block.copy()
        enhanced_block["transactions"] = tx_to_block_mapping.get(block_hash, [])
        enhanced_block["tx_count"] = len(enhanced_block["transactions"])
        enhanced_block["height"] = i + 1
        enhanced_blocks.append(enhanced_block)
    
    # Save enhanced blocks
    print(f"Saving {len(enhanced_blocks)} enhanced blocks to {enhanced_file}")
    with open(enhanced_file, 'w') as f:
        json.dump(enhanced_blocks, f, indent=2)
    
    # Report statistics
    total_tx_in_blocks = sum(block["tx_count"] for block in enhanced_blocks)
    blocks_with_tx = len([b for b in enhanced_blocks if b["tx_count"] > 0])
    
    print(f"\nEnhanced Blocks Statistics:")
    print(f"  Total Blocks: {len(enhanced_blocks)}")
    print(f"  Blocks with Transactions: {blocks_with_tx}")
    print(f"  Total Transactions in Blocks: {total_tx_in_blocks}")
    print(f"  Empty Blocks: {len(enhanced_blocks) - blocks_with_tx}")
    
    return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate enhanced blocks file")
    parser.add_argument("--shared-dir", default=DEFAULT_SHARED_DIR,
                       help="Path to shared directory containing monitor data")
    
    args = parser.parse_args()
    
    try:
        success = regenerate_enhanced_blocks(args.shared_dir)
        if success:
            print("\n✅ Enhanced blocks file regenerated successfully")
            
            # Test the analysis
            print("\n" + "="*60)
            print("Testing post-simulation analysis...")
            import subprocess
            result = subprocess.run([
                "python3", "scripts/post_simulation_monitor_analysis.py",
                "--shared-dir", args.shared_dir
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Analysis completed successfully")
                print("\nAnalysis output:")
                print(result.stdout)
            else:
                print("❌ Analysis failed")
                print("Error output:")
                print(result.stderr)
        else:
            print("❌ Failed to regenerate enhanced blocks file")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
