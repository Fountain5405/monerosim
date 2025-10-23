#!/usr/bin/env python3
"""
Post-Simulation Monitor Analysis Script

This script analyzes the monitor agent's output files from /tmp/monerosim_shared
to create a comprehensive final report with accurate transaction counting.

It addresses the issue where the monitor agent cannot accurately count transactions
included in blocks because blocks_found.json doesn't contain transaction data.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import argparse
from collections import defaultdict


class PostSimulationAnalyzer:
    """Analyzes simulation data from shared monitor files."""
    
    def __init__(self, shared_dir: str = "/tmp/monerosim_shared"):
        """
        Initialize the analyzer.
        
        Args:
            shared_dir: Path to the shared directory containing monitor data
        """
        self.shared_dir = Path(shared_dir)
        self.transactions_file = self.shared_dir / "transactions.json"
        self.blocks_file = self.shared_dir / "blocks_found.json"
        self.agent_registry_file = self.shared_dir / "agent_registry.json"
        
        # Data storage
        self.transactions = []
        self.blocks = []
        self.agent_registry = {}
        
        # Analysis results
        self.analysis_results = {}
        
        # Simple logger
        self.logger = self
        
    def info(self, message):
        print(f"INFO: {message}")
    
    def warning(self, message):
        print(f"WARNING: {message}")
        
    def load_data(self) -> bool:
        """
        Load all data files from the shared directory.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load transactions
            if self.transactions_file.exists():
                with open(self.transactions_file, 'r') as f:
                    self.transactions = json.load(f)
                print(f"Loaded {len(self.transactions)} transactions")
            else:
                print(f"Warning: Transactions file not found: {self.transactions_file}")
                return False
            
            # Load blocks
            if self.blocks_file.exists():
                with open(self.blocks_file, 'r') as f:
                    self.blocks = json.load(f)
                print(f"Loaded {len(self.blocks)} blocks")
            else:
                print(f"Warning: Blocks file not found: {self.blocks_file}")
                return False
            
            # Load agent registry
            if self.agent_registry_file.exists():
                with open(self.agent_registry_file, 'r') as f:
                    self.agent_registry = json.load(f)
                print(f"Loaded agent registry with {len(self.agent_registry.get('agents', {}))} agents")
            
            return True
            
        except Exception as e:
            print(f"Error loading data: {e}")
            return False
    
    def analyze_transactions(self) -> Dict[str, Any]:
        """
        Analyze transaction data.
        
        Returns:
            Dictionary containing transaction analysis results
        """
        if not self.transactions:
            return {"error": "No transaction data available"}
        
        # Count transactions by sender
        sender_counts = defaultdict(int)
        unique_tx_hashes = set()
        total_amount = 0
        
        for tx in self.transactions:
            sender = tx.get("sender_id", "unknown")
            sender_counts[sender] += 1
            
            # Extract transaction hash
            tx_hash_data = tx.get("tx_hash", {})
            if isinstance(tx_hash_data, dict) and "tx_hash" in tx_hash_data:
                unique_tx_hashes.add(tx_hash_data["tx_hash"])
            elif isinstance(tx_hash_data, str):
                unique_tx_hashes.add(tx_hash_data)
            
            # Sum amounts
            amount = tx.get("amount", 0)
            if isinstance(amount, (int, float)):
                total_amount += amount
        
        return {
            "total_transactions": len(self.transactions),
            "unique_transaction_hashes": len(unique_tx_hashes),
            "total_amount_transferred": total_amount,
            "transactions_by_sender": dict(sender_counts),
            "average_transaction_amount": total_amount / len(self.transactions) if self.transactions else 0
        }
    
    def analyze_blocks(self) -> Dict[str, Any]:
        """
        Analyze block data, including enhanced transaction data if available.
        
        Returns:
            Dictionary containing block analysis results
        """
        if not self.blocks:
            return {"error": "No block data available"}
        
        # Try to load enhanced block data first
        enhanced_blocks_file = self.shared_dir / "blocks_with_transactions.json"
        enhanced_blocks = None
        
        if enhanced_blocks_file.exists():
            try:
                with open(enhanced_blocks_file, 'r') as f:
                    enhanced_blocks = json.load(f)
                self.logger.info(f"Loaded enhanced block data with {len(enhanced_blocks)} blocks")
            except Exception as e:
                self.logger.warning(f"Failed to load enhanced block data: {e}")
        
        # Analyze enhanced blocks if available, otherwise basic blocks
        if enhanced_blocks:
            return self._analyze_enhanced_blocks(enhanced_blocks)
        else:
            return self._analyze_basic_blocks(self.blocks)
    
    def _analyze_enhanced_blocks(self, enhanced_blocks: List[Dict]) -> Dict[str, Any]:
        """Analyze enhanced block data with transaction information."""
        # Count blocks by miner
        miner_counts = defaultdict(int)
        timestamps = []
        transaction_counts = []
        total_transactions = 0
        
        for block in enhanced_blocks:
            miner_ip = block.get("miner_ip", "unknown")
            miner_counts[miner_ip] += 1
            
            # Collect timestamps for timing analysis
            timestamp = block.get("timestamp", 0)
            if timestamp:
                timestamps.append(timestamp)
            
            # Collect transaction data
            transactions = block.get("transactions", [])
            tx_count = len(transactions)
            transaction_counts.append(tx_count)
            total_transactions += tx_count
        
        # Calculate block timing
        block_timing = {}
        if len(timestamps) > 1:
            sorted_timestamps = sorted(timestamps)
            intervals = [sorted_timestamps[i+1] - sorted_timestamps[i] 
                       for i in range(len(sorted_timestamps)-1)]
            block_timing = {
                "first_block_time": min(timestamps),
                "last_block_time": max(timestamps),
                "total_duration": max(timestamps) - min(timestamps),
                "average_block_time": sum(intervals) / len(intervals) if intervals else 0,
                "blocks_per_hour": len(enhanced_blocks) / ((max(timestamps) - min(timestamps)) / 3600) if max(timestamps) != min(timestamps) else 0
            }
        
        # Calculate transaction statistics
        tx_stats = {}
        if transaction_counts:
            tx_stats = {
                "total_transactions_in_blocks": total_transactions,
                "average_transactions_per_block": sum(transaction_counts) / len(transaction_counts),
                "max_transactions_in_block": max(transaction_counts),
                "min_transactions_in_block": min(transaction_counts),
                "blocks_with_transactions": len([tc for tc in transaction_counts if tc > 0]),
                "empty_blocks": len([tc for tc in transaction_counts if tc == 0])
            }
        
        return {
            "total_blocks": len(enhanced_blocks),
            "blocks_by_miner": dict(miner_counts),
            "block_timing": block_timing,
            "transaction_stats": tx_stats,
            "data_source": "enhanced"
        }
    
    def _analyze_basic_blocks(self, blocks: List[Dict]) -> Dict[str, Any]:
        """Analyze basic block data without transaction information."""
        # Count blocks by miner
        miner_counts = defaultdict(int)
        timestamps = []
        
        for block in blocks:
            miner_ip = block.get("miner_ip", "unknown")
            miner_counts[miner_ip] += 1
            
            # Collect timestamps for timing analysis
            timestamp = block.get("timestamp", 0)
            if timestamp:
                timestamps.append(timestamp)
        
        # Calculate block timing
        block_timing = {}
        if len(timestamps) > 1:
            sorted_timestamps = sorted(timestamps)
            intervals = [sorted_timestamps[i+1] - sorted_timestamps[i] 
                       for i in range(len(sorted_timestamps)-1)]
            block_timing = {
                "first_block_time": min(timestamps),
                "last_block_time": max(timestamps),
                "total_duration": max(timestamps) - min(timestamps),
                "average_block_time": sum(intervals) / len(intervals) if intervals else 0,
                "blocks_per_hour": len(blocks) / ((max(timestamps) - min(timestamps)) / 3600) if max(timestamps) != min(timestamps) else 0
            }
        
        return {
            "total_blocks": len(blocks),
            "blocks_by_miner": dict(miner_counts),
            "block_timing": block_timing,
            "data_source": "basic"
        }
    
    def analyze_agents(self) -> Dict[str, Any]:
        """
        Analyze agent data from registry.
        
        Returns:
            Dictionary containing agent analysis results
        """
        if not self.agent_registry:
            return {"error": "No agent registry data available"}
        
        agents = self.agent_registry.get("agents", {})
        if isinstance(agents, dict):
            agents = list(agents.values())
        
        # Count agent types
        agent_types = defaultdict(int)
        miner_count = 0
        user_count = 0
        
        for agent in agents:
            agent_id = agent.get("id", "unknown")
            attributes = agent.get("attributes", {})
            
            if attributes.get("is_miner") == "true":
                miner_count += 1
                agent_types["miner"] += 1
            else:
                user_count += 1
                agent_types["user"] += 1
        
        return {
            "total_agents": len(agents),
            "miner_agents": miner_count,
            "user_agents": user_count,
            "agent_types": dict(agent_types)
        }
    
    def get_transaction_inclusion_data(self) -> Dict[str, Any]:
        """
        Get actual transaction inclusion data from enhanced block files.
        
        Returns:
            Dictionary with actual transaction inclusion data or indication of data unavailability
        """
        total_transactions = len(self.transactions)
        total_blocks = len(self.blocks)
        
        # Try to load enhanced block data
        enhanced_blocks_file = self.shared_dir / "blocks_with_transactions.json"
        if enhanced_blocks_file.exists():
            try:
                with open(enhanced_blocks_file, 'r') as f:
                    enhanced_blocks = json.load(f)
                
                # Count actual transactions in blocks
                actual_tx_in_blocks = sum(len(block.get("transactions", [])) for block in enhanced_blocks)
                inclusion_rate = actual_tx_in_blocks / total_transactions if total_transactions > 0 else 0.0
                
                return {
                    "transactions_in_blocks": actual_tx_in_blocks,
                    "inclusion_rate": inclusion_rate,
                    "total_transactions": total_transactions,
                    "total_blocks": total_blocks,
                    "data_available": True,
                    "data_source": "blocks_with_transactions.json"
                }
            except Exception as e:
                self.logger.warning(f"Failed to load enhanced block data: {e}")
        
        # Check if transaction tracking data is available
        tx_tracking_file = self.shared_dir / "transaction_tracking.json"
        if tx_tracking_file.exists():
            try:
                with open(tx_tracking_file, 'r') as f:
                    tracking_data = json.load(f)
                
                included_txs = tracking_data.get("included_txs", [])
                actual_tx_in_blocks = len(included_txs)
                inclusion_rate = actual_tx_in_blocks / total_transactions if total_transactions > 0 else 0.0
                
                return {
                    "transactions_in_blocks": actual_tx_in_blocks,
                    "inclusion_rate": inclusion_rate,
                    "total_transactions": total_transactions,
                    "total_blocks": total_blocks,
                    "data_available": True,
                    "data_source": "transaction_tracking.json"
                }
            except Exception as e:
                self.logger.warning(f"Failed to load transaction tracking data: {e}")
        
        # No enhanced data available
        return {
            "transactions_in_blocks": None,
            "inclusion_rate": None,
            "total_transactions": total_transactions,
            "total_blocks": total_blocks,
            "data_available": False,
            "message": "Transaction inclusion data not available - enhanced monitoring not enabled or incomplete"
        }
    
    def evaluate_success_criteria(self) -> Dict[str, Any]:
        """
        Evaluate simulation success criteria.
        
        Returns:
            Dictionary containing success criteria evaluation
        """
        tx_analysis = self.analyze_transactions()
        block_analysis = self.analyze_blocks()
        agent_analysis = self.analyze_agents()
        tx_inclusion = self.get_transaction_inclusion_data()
        
        total_transactions = tx_analysis.get("total_transactions", 0)
        total_blocks = block_analysis.get("total_blocks", 0)
        user_agents = agent_analysis.get("user_agents", 0)
        
        # Handle transaction inclusion - only use actual data
        tx_inclusion_success = False
        tx_inclusion_details = "Transaction inclusion data not available"
        
        if tx_inclusion.get("data_available", False):
            included_count = tx_inclusion.get("transactions_in_blocks", 0)
            if included_count is not None and total_transactions > 0:
                tx_inclusion_success = included_count >= total_transactions * 0.8  # 80% threshold
                tx_inclusion_details = f"{included_count}/{total_transactions} transactions included in blocks"
            else:
                tx_inclusion_details = "Transaction inclusion data incomplete"
        
        # Success criteria
        criteria = {
            "blocks_created": {
                "success": total_blocks > 0,
                "details": f"{total_blocks} blocks mined"
            },
            "blocks_propagated": {
                "success": total_blocks > 0 and user_agents > 0,
                "details": f"{total_blocks} blocks available to {user_agents} user nodes"
            },
            "transactions_created_broadcast": {
                "success": total_transactions > 0,
                "details": f"{total_transactions} transactions created"
            },
            "transactions_in_blocks": {
                "success": tx_inclusion_success,
                "details": tx_inclusion_details
            }
        }
        
        # Overall success - only if all criteria pass and transaction data is available
        overall_success = all(c["success"] for c in criteria.values()) and tx_inclusion.get("data_available", False)
        
        # Prepare summary
        summary = {
            "total_blocks": total_blocks,
            "total_transactions": total_transactions,
            "user_nodes": user_agents,
            "transaction_inclusion_data_available": tx_inclusion.get("data_available", False)
        }
        
        if tx_inclusion.get("data_available", False):
            included_count = tx_inclusion.get("transactions_in_blocks", 0)
            if included_count is not None:
                summary["transactions_in_blocks"] = included_count
                summary["success_rate"] = included_count / total_transactions if total_transactions > 0 else 0.0
            else:
                summary["transactions_in_blocks"] = "unknown"
                summary["success_rate"] = "unknown"
        else:
            summary["transactions_in_blocks"] = "unknown"
            summary["success_rate"] = "unknown"
        
        return {
            "criteria": criteria,
            "overall_success": overall_success,
            "summary": summary
        }
    
    def run_analysis(self) -> Dict[str, Any]:
        """
        Run complete analysis.
        
        Returns:
            Dictionary containing all analysis results
        """
        print("Starting post-simulation analysis...")
        
        if not self.load_data():
            return {"error": "Failed to load data files"}
        
        print("Analyzing transactions...")
        tx_analysis = self.analyze_transactions()
        
        print("Analyzing blocks...")
        block_analysis = self.analyze_blocks()
        
        print("Analyzing agents...")
        agent_analysis = self.analyze_agents()
        
        print("Getting transaction inclusion data...")
        tx_inclusion = self.get_transaction_inclusion_data()
        
        print("Evaluating success criteria...")
        success_criteria = self.evaluate_success_criteria()
        
        self.analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "transactions": tx_analysis,
            "blocks": block_analysis,
            "agents": agent_analysis,
            "transaction_inclusion": tx_inclusion,
            "success_criteria": success_criteria
        }
        
        return self.analysis_results
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate a comprehensive text report.
        
        Args:
            output_file: Optional file to save the report
            
        Returns:
            The report as a string
        """
        if not self.analysis_results:
            return "No analysis results available. Run run_analysis() first."
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report_lines = [
            "=== MoneroSim Post-Simulation Monitor Analysis ===",
            f"Generated: {timestamp}",
            "",
            "SIMULATION OVERVIEW:",
        ]
        
        # Add summary statistics
        success_criteria = self.analysis_results.get("success_criteria", {})
        summary = success_criteria.get("summary", {})
        
        report_lines.extend([
            f"  Total Nodes Analyzed: {self.analysis_results.get('agents', {}).get('total_agents', 0)}",
            f"  Total Blocks Mined: {summary.get('total_blocks', 0)}",
            f"  Total Unique Transactions Created: {summary.get('total_transactions', 0)}",
            f"  Transactions in Blocks: {summary.get('transactions_in_blocks', 'unknown')}",
            f"  Transaction Inclusion Data Available: {'Yes' if summary.get('transaction_inclusion_data_available', False) else 'No'}",
            "",
            "SUCCESS CRITERIA RESULTS:",
            ""
        ])
        
        # Add success criteria details
        criteria = success_criteria.get("criteria", {})
        for criterion_name, criterion_data in criteria.items():
            status = "PASS" if criterion_data.get("success", False) else "FAIL"
            report_lines.extend([
                f"  • {criterion_name.replace('_', ' ').title()}: {status}",
                f"    {criterion_data.get('details', 'No details')}",
                ""
            ])
        
        # Add overall result
        overall_success = success_criteria.get("overall_success", False)
        report_lines.extend([
            "OVERALL RESULT:",
            f"  {'SUCCESS' if overall_success else 'FAILURE'}",
            ""
        ])
        
        # Add detailed analysis sections
        report_lines.extend([
            "DETAILED ANALYSIS:",
            "",
            "TRANSACTION ANALYSIS:",
        ])
        
        tx_analysis = self.analysis_results.get("transactions", {})
        if "error" not in tx_analysis:
            report_lines.extend([
                f"  Total Transactions: {tx_analysis.get('total_transactions', 0)}",
                f"  Unique Transaction Hashes: {tx_analysis.get('unique_transaction_hashes', 0)}",
                f"  Total Amount Transferred: {tx_analysis.get('total_amount_transferred', 0):.6f} XMR",
                f"  Average Transaction Amount: {tx_analysis.get('average_transaction_amount', 0):.6f} XMR",
                ""
            ])
            
            # Top senders
            sender_counts = tx_analysis.get("transactions_by_sender", {})
            if sender_counts:
                report_lines.append("  Top Transaction Senders:")
                sorted_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                for sender, count in sorted_senders:
                    report_lines.append(f"    {sender}: {count} transactions")
                report_lines.append("")
        
        # Block analysis
        report_lines.append("BLOCK ANALYSIS:")
        block_analysis = self.analysis_results.get("blocks", {})
        if "error" not in block_analysis:
            report_lines.extend([
                f"  Total Blocks: {block_analysis.get('total_blocks', 0)}",
                ""
            ])
            
            # Miner distribution
            miner_counts = block_analysis.get("blocks_by_miner", {})
            if miner_counts:
                report_lines.append("  Blocks by Miner:")
                sorted_miners = sorted(miner_counts.items(), key=lambda x: x[1], reverse=True)
                for miner, count in sorted_miners:
                    report_lines.append(f"    {miner}: {count} blocks")
                report_lines.append("")
            
            # Block timing
            timing = block_analysis.get("block_timing", {})
            if timing and "blocks_per_hour" in timing:
                report_lines.extend([
                    "  Block Timing:",
                    f"    Average Block Time: {timing.get('average_block_time', 0):.1f} seconds",
                    f"    Blocks Per Hour: {timing.get('blocks_per_hour', 0):.1f}",
                    ""
                ])
        
        # Transaction inclusion analysis
        report_lines.append("TRANSACTION INCLUSION ANALYSIS:")
        tx_inclusion = self.analysis_results.get("transaction_inclusion", {})
        if "error" not in tx_inclusion:
            if tx_inclusion.get("data_available", False):
                data_source = tx_inclusion.get("data_source", "unknown")
                included_count = tx_inclusion.get("transactions_in_blocks", 0)
                inclusion_rate = tx_inclusion.get("inclusion_rate", 0)
                report_lines.extend([
                    f"  Data Source: {data_source}",
                    f"  Transactions Included in Blocks: {included_count}",
                    f"  Inclusion Rate: {inclusion_rate:.1%}",
                    ""
                ])
            else:
                report_lines.extend([
                    f"  Data Available: No",
                    f"  Message: {tx_inclusion.get('message', 'Enhanced monitoring data not available')}",
                    ""
                ])
        
        # Agent analysis
        report_lines.append("AGENT ANALYSIS:")
        agent_analysis = self.analysis_results.get("agents", {})
        if "error" not in agent_analysis:
            report_lines.extend([
                f"  Total Agents: {agent_analysis.get('total_agents', 0)}",
                f"  User Agents: {agent_analysis.get('user_agents', 0)}",
                f"  Miner Agents: {agent_analysis.get('miner_agents', 0)}",
                ""
            ])
        
        report = "\n".join(report_lines)
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"Report saved to: {output_file}")
        
        return report
    
    def save_json_report(self, output_file: Optional[str] = None) -> str:
        """
        Save analysis results as JSON.
        
        Args:
            output_file: Optional file to save the JSON report
            
        Returns:
            Path to the saved file
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"post_simulation_analysis_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
        
        print(f"JSON report saved to: {output_file}")
        return output_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze MoneroSim monitor data")
    parser.add_argument("--shared-dir", default="/tmp/monerosim_shared",
                       help="Path to shared directory containing monitor data")
    parser.add_argument("--output", help="Output file for text report")
    parser.add_argument("--json-output", help="Output file for JSON report")
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    
    args = parser.parse_args()
    
    try:
        # Create analyzer
        analyzer = PostSimulationAnalyzer(args.shared_dir)
        
        # Run analysis
        results = analyzer.run_analysis()
        
        if "error" in results:
            print(f"Analysis failed: {results['error']}")
            sys.exit(1)
        
        # Generate reports
        if not args.quiet:
            print("\n" + "="*60)
            report = analyzer.generate_report()
            print(report)
        
        # Save text report
        if args.output:
            analyzer.generate_report(args.output)
        
        # Save JSON report
        json_file = analyzer.save_json_report(args.json_output)
        
        # Return success based on overall success criteria
        overall_success = results.get("success_criteria", {}).get("overall_success", False)
        sys.exit(0 if overall_success else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
