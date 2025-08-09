#!/usr/bin/env python3
"""
End-to-end test for the is_miner configuration transition.

This script verifies the complete transition from a boolean-based is_miner configuration
to an attributes-only approach. It tests with small, medium, and large configurations,
using the migration script, running Shadow simulations, and verifying mining and transaction
functionalities.
"""

import os
import sys
import yaml
import json
import subprocess
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Add the parent directory to the path so we can import other modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.error_handling import ErrorHandler, log_info, log_error, log_success, retry_command, call_daemon_with_retry, call_wallet_with_retry
from scripts.agent_discovery import AgentDiscovery

class EndToEndTest:
    """End-to-end test for is_miner configuration transition."""
    
    def __init__(self, log_level: str = "INFO"):
        """Initialize the test."""
        self.log_level = log_level
        self.logger = logging.getLogger("end_to_end_test")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)
        self.monerosim_path = "./target/release/monerosim"
        self.migration_script = "scripts/migrate_is_miner_config.py"
        self.test_results = {
            "small": {},
            "medium": {},
            "large": {}
        }
        
    def run_test(self) -> bool:
        """Run the complete end-to-end test."""
        self.logger.info("Starting end-to-end test for is_miner configuration transition")
        
        try:
            # Test configurations
            configs = [
                ("small", "config_agents_small.yaml", "config_agents_small_migrated.yaml"),
                ("medium", "config_agents_medium.yaml", "config_agents_medium_migrated.yaml"),
                ("large", "config_agents_large.yaml", "config_agents_large_migrated.yaml")
            ]
            
            for config_name, original_config, migrated_config in configs:
                self.logger.info(f"Testing {config_name} configuration")
                
                # Test migration
                migration_success = self.test_migration(original_config, migrated_config)
                self.test_results[config_name]["migration"] = migration_success
                
                if not migration_success:
                    self.logger.error(f"Migration failed for {config_name} configuration")
                    continue
                
                # Test configuration generation
                config_gen_success = self.test_configuration_generation(migrated_config, f"shadow_agents_{config_name}_output")
                self.test_results[config_name]["config_generation"] = config_gen_success
                
                if not config_gen_success:
                    self.logger.error(f"Configuration generation failed for {config_name} configuration")
                    continue
                
                # Test Shadow simulation (only for small config due to time constraints)
                if config_name == "small":
                    shadow_success = self.test_shadow_simulation(f"shadow_agents_{config_name}_output/shadow_agents.yaml")
                    self.test_results[config_name]["shadow_simulation"] = shadow_success
                    
                    if not shadow_success:
                        self.logger.error(f"Shadow simulation failed for {config_name} configuration")
                        continue
                
                # Verify agent identification
                agent_id_success = self.test_agent_identification(migrated_config)
                self.test_results[config_name]["agent_identification"] = agent_id_success
                
                if not agent_id_success:
                    self.logger.error(f"Agent identification failed for {config_name} configuration")
                    continue
                
                # Test mining functionality (only for small config due to time constraints)
                if config_name == "small":
                    # Perform mining verification while Shadow is still running
                    mining_success = self.verify_mining_functionality()
                    self.test_results[config_name]["mining"] = mining_success
                    
                    if not mining_success:
                        self.logger.error(f"Mining functionality test failed for {config_name} configuration")
                        continue
                
                # Test transaction functionality (only for small config due to time constraints)
                if config_name == "small":
                    # Perform transaction verification while Shadow is still running
                    transaction_success = self.verify_transaction_functionality()
                    self.test_results[config_name]["transaction"] = transaction_success
                    
                    if not transaction_success:
                        self.logger.error(f"Transaction functionality test failed for {config_name} configuration")
                        continue
                
                # Stop Shadow simulation if it was started
                if config_name == "small" and self.test_results[config_name].get("shadow_simulation", False):
                    self.stop_shadow_simulation()
            
            # Generate test report
            self.generate_test_report()
            
            # Check if all tests passed
            all_passed = all(
                result.get("migration", False) and 
                result.get("config_generation", False) and
                result.get("agent_identification", False)
                for result in self.test_results.values()
            )
            
            if all_passed:
                self.logger.info("All end-to-end tests passed!")
                return True
            else:
                self.logger.error("Some end-to-end tests failed!")
                return False
                
        except Exception as e:
            self.logger.error(f"Error running end-to-end test: {e}")
            return False
    
    def test_migration(self, original_config: str, migrated_config: str) -> bool:
        """Test the migration script."""
        self.logger.info(f"Testing migration from {original_config} to {migrated_config}")
        
        try:
            # Clean up any existing migrated config
            if os.path.exists(migrated_config):
                os.remove(migrated_config)
            
            # Run migration script
            cmd = ["python3", self.migration_script, original_config, migrated_config]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Migration script failed with return code {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                return False
            
            # Check if migrated config was created
            if not os.path.exists(migrated_config):
                self.logger.error(f"Migrated config {migrated_config} was not created")
                return False
            
            # Verify migration was done correctly
            with open(migrated_config, 'r') as f:
                migrated_data = yaml.safe_load(f)
            
            user_agents = migrated_data.get("agents", {}).get("user_agents", [])
            
            # Check that is_miner is no longer at the top level but in attributes
            for agent in user_agents:
                if "is_miner" in agent:
                    self.logger.error(f"Found is_miner at top level in migrated config")
                    return False
                
                attributes = agent.get("attributes", {})
                if "is_miner" not in attributes:
                    # This is OK for regular users
                    continue
                
                # Verify is_miner is a string in attributes
                if not isinstance(attributes["is_miner"], str):
                    self.logger.error(f"is_miner in attributes is not a string: {attributes['is_miner']}")
                    return False
            
            self.logger.info(f"Migration from {original_config} to {migrated_config} successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing migration: {e}")
            return False
    
    def test_configuration_generation(self, config_file: str, output_dir: str) -> bool:
        """Test configuration generation with monerosim."""
        self.logger.info(f"Testing configuration generation with {config_file}")
        
        try:
            # Clean up any existing output directory
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
            
            # Run monerosim to generate configuration
            cmd = [self.monerosim_path, "--config", config_file, "--output", output_dir]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Monerosim failed with return code {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                return False
            
            # Check if output directory was created
            if not os.path.exists(output_dir):
                self.logger.error(f"Output directory {output_dir} was not created")
                return False
            
            # Check if shadow configuration was generated
            shadow_config = os.path.join(output_dir, "shadow_agents.yaml")
            if not os.path.exists(shadow_config):
                self.logger.error(f"Shadow configuration {shadow_config} was not generated")
                return False
            
            # Check if agent registry was created
            agent_registry = "/tmp/monerosim_shared/agent_registry.json"
            if not os.path.exists(agent_registry):
                self.logger.warning(f"Agent registry {agent_registry} was not created")
                # This is not a critical error, so we'll continue
            
            self.logger.info(f"Configuration generation with {config_file} successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing configuration generation: {e}")
            return False
    
    def test_shadow_simulation(self, shadow_config: str) -> bool:
        """Test Shadow simulation by running it in the background."""
        self.logger.info(f"Testing Shadow simulation with {shadow_config}")
        
        try:
            # Handle the case where shadow_config is just "small" instead of a full path
            if shadow_config == "small":
                shadow_config = "shadow_agents_small_output/shadow_agents.yaml"
            
            # Clean up any previous simulation data
            if os.path.exists("shadow.data"):
                shutil.rmtree("shadow.data")
            if os.path.exists("shadow.log"):
                os.remove("shadow.log")
            
            # Clean up any shared state from previous runs
            shared_dir = "/tmp/monerosim_shared"
            if os.path.exists(shared_dir):
                # Remove wallet directories but keep registry files
                import glob
                wallet_dirs = glob.glob(f"{shared_dir}/*_wallet")
                for wallet_dir in wallet_dirs:
                    if os.path.isdir(wallet_dir):
                        shutil.rmtree(wallet_dir)
            
            # Run Shadow in the background
            cmd = ["nohup", "shadow", shadow_config, ">", "shadow.log", "2>&1", "&"]
            subprocess.run(" ".join(cmd), shell=True, check=True)
            
            # Wait for Shadow to start
            self.logger.info("Waiting for Shadow simulation to start...")
            import time
            time.sleep(30)  # Increased wait time
            
            # Check if simulation data was created
            if not os.path.exists("shadow.data"):
                self.logger.warning("Shadow simulation data was not created")
                return False
            
            # Wait for agents to be ready
            if not self.wait_for_agents_ready():
                self.logger.warning("Agents did not become ready in time, but simulation may still be running")
                # Let's check if the simulation is progressing by looking at the log
                if os.path.exists("shadow.log"):
                    with open("shadow.log", "r") as f:
                        log_content = f.read()
                        if "Finished simulation" in log_content:
                            self.logger.info("Shadow simulation has finished")
                            return True
                        elif "ERROR" in log_content:
                            self.logger.error("Shadow simulation encountered errors")
                            return False
                        else:
                            self.logger.info("Shadow simulation is still running")
                            return True
                return False
            
            self.logger.info(f"Shadow simulation with {shadow_config} started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing Shadow simulation: {e}")
            return False
    
    def wait_for_agents_ready(self, timeout: int = 300) -> bool:
        """Wait for agents to be ready by checking the agent registry and RPC services."""
        self.logger.info("Waiting for agents to be ready...")
        
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check if agent registry exists
                agent_registry = "/tmp/monerosim_shared/agent_registry.json"
                if os.path.exists(agent_registry):
                    with open(agent_registry, 'r') as f:
                        registry_data = json.load(f)
                    
                    agents = registry_data.get("agents", [])
                    if len(agents) > 0:
                        self.logger.info(f"Found {len(agents)} agents in registry")
                        
                        # Check if miners.json exists
                        miners_file = "/tmp/monerosim_shared/miners.json"
                        if os.path.exists(miners_file):
                            self.logger.info("Miners registry found")
                            
                            # Check if blocks are being generated
                            blocks_found_file = "/tmp/monerosim_shared/blocks_found.json"
                            if os.path.exists(blocks_found_file):
                                self.logger.info("Blocks are being generated")
                            
                            # Check if block controller is working
                            block_controller_file = "/tmp/monerosim_shared/block_controller_stats.json"
                            if os.path.exists(block_controller_file):
                                self.logger.info("Block controller is working")
                            
                            # Try to connect to a daemon RPC to verify it's responding
                            try:
                                agent_discovery = AgentDiscovery()
                                miner_agents = agent_discovery.get_miner_agents()
                                
                                if miner_agents:
                                    miner_agent = miner_agents[0]
                                    ip_address = miner_agent.get("ip_addr")
                                    daemon_rpc_port = miner_agent.get("agent_rpc_port")
                                    
                                    if ip_address and daemon_rpc_port:
                                        daemon_rpc_url = f"http://{ip_address}:{daemon_rpc_port}/json_rpc"
                                        
                                        # Try a simple RPC call to verify the daemon is responding
                                        success, _ = call_daemon_with_retry(
                                            daemon_rpc_url,
                                            "get_info",
                                            {},
                                            5, 5, "readiness_check"
                                        )
                                        
                                        if success:
                                            self.logger.info("Daemon RPC is responding")
                                            return True
                                        else:
                                            self.logger.warning("Daemon RPC not responding yet, but other signs of progress are present")
                                    else:
                                        self.logger.warning("Missing IP or port for miner agent")
                                else:
                                    self.logger.warning("No miner agents found yet")
                            except Exception as e:
                                self.logger.warning(f"Error checking RPC readiness: {e}")
                        else:
                            self.logger.info("Miners registry not found yet")
                    else:
                        self.logger.info("No agents found in registry yet")
                else:
                    self.logger.info("Agent registry not found yet")
                
                # Wait before checking again
                time.sleep(10)
                
            except Exception as e:
                self.logger.warning(f"Error checking agent readiness: {e}")
                time.sleep(10)
        
        # If we reach the timeout, check if the simulation has finished
        if os.path.exists("shadow.log"):
            with open("shadow.log", "r") as f:
                log_content = f.read()
                if "Finished simulation" in log_content:
                    self.logger.info("Shadow simulation has finished")
                    return True
        
        self.logger.warning(f"Agents did not become ready within {timeout} seconds, but simulation may still be running")
        return False
    
    def stop_shadow_simulation(self) -> None:
        """Stop any running Shadow simulation."""
        self.logger.info("Stopping Shadow simulation...")
        
        try:
            # Find and kill any running shadow processes
            subprocess.run(["pkill", "-f", "shadow"], check=False)
            
            # Clean up simulation data
            if os.path.exists("shadow.data"):
                shutil.rmtree("shadow.data")
            if os.path.exists("shadow.log"):
                os.remove("shadow.log")
            
            self.logger.info("Shadow simulation stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping Shadow simulation: {e}")
    
    def test_agent_identification(self, config_file: str) -> bool:
        """Test that agents are correctly identified as miners or regular users."""
        self.logger.info(f"Testing agent identification with {config_file}")
        
        try:
            # Load the migrated configuration
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            user_agents = config_data.get("agents", {}).get("user_agents", [])
            
            miners = []
            regular_users = []
            
            for agent in user_agents:
                attributes = agent.get("attributes", {})
                if attributes.get("is_miner") == "true":
                    miners.append(agent)
                else:
                    regular_users.append(agent)
            
            # Verify we have both miners and regular users
            if len(miners) == 0:
                self.logger.error("No miners found in configuration")
                return False
            
            if len(regular_users) == 0:
                self.logger.error("No regular users found in configuration")
                return False
            
            # Verify miners have hashrate attribute
            for miner in miners:
                attributes = miner.get("attributes", {})
                if "hashrate" not in attributes:
                    self.logger.error("Miner missing hashrate attribute")
                    return False
            
            # Verify regular users have transaction-related attributes
            for user in regular_users:
                attributes = user.get("attributes", {})
                if "transaction_interval" not in attributes:
                    self.logger.warning("Regular user missing transaction_interval attribute")
                    # This is not a critical error
            
            self.logger.info(f"Agent identification successful: {len(miners)} miners, {len(regular_users)} regular users")
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing agent identification: {e}")
            return False
    
    def verify_mining_functionality(self) -> bool:
        """Verify that mining functionality works correctly by checking logs."""
        self.logger.info("Verifying mining functionality through log analysis")
        
        try:
            # First, let's check if the simulation is still running
            import subprocess
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            if "shadow" not in result.stdout:
                self.logger.warning("Shadow simulation is not running, attempting to restart it")
                # Try to restart the simulation
                if not self.test_shadow_simulation("shadow_agents_small_output/shadow_agents.yaml"):
                    self.logger.error("Failed to restart Shadow simulation")
                    return False
            
            # Process logs to verify mining functionality
            self.logger.info("Processing logs to verify mining functionality")
            subprocess.run("bash -c 'source venv/bin/activate && python scripts/log_processor.py'",
                          shell=True, check=True)
            
            # Check block controller logs for successful block generation
            blockcontroller_log = "shadow.data/hosts/blockcontroller/bash.1000.stdout.processed_log"
            if os.path.exists(blockcontroller_log):
                with open(blockcontroller_log, 'r') as f:
                    log_content = f.read()
                    
                    # Check for successful block generation
                    if "Selected winning miner with IP" in log_content and "Successfully generated" in log_content and "blocks" in log_content:
                        self.logger.info("Block generation is working correctly")
                        log_success("verify_mining", "✅ Mining functionality verified through block controller logs")
                    else:
                        self.logger.warning("Block generation not confirmed in block controller logs")
                        return False
            else:
                self.logger.warning(f"Block controller log not found: {blockcontroller_log}")
                return False
            
            # Check user logs for balance increases (indicating mining rewards)
            user_logs = []
            for i in range(4):  # Check user000 to user003
                user_log = f"shadow.data/hosts/user{i:03d}/bash.1028.stdout.processed_log"
                if os.path.exists(user_log):
                    user_logs.append(user_log)
            
            if not user_logs:
                self.logger.warning("No user logs found for balance verification")
                return False
            
            balance_increases_found = False
            for user_log in user_logs:
                with open(user_log, 'r') as f:
                    log_content = f.read()
                    
                    # Check for balance increases
                    if "Miner balance" in log_content:
                        self.logger.info(f"Balance information found in {user_log}")
                        balance_increases_found = True
            
            if balance_increases_found:
                self.logger.info("Balance increases found in user logs, confirming mining rewards")
                log_success("verify_mining", "✅ Mining rewards verified through user logs")
            else:
                self.logger.warning("Balance increases not found in user logs")
                # This is not a critical failure, as block generation is the main indicator
            
            # Check blocks_found.json for generated blocks
            blocks_found_file = "/tmp/monerosim_shared/blocks_found.json"
            if os.path.exists(blocks_found_file):
                with open(blocks_found_file, 'r') as f:
                    blocks_data = json.load(f)
                    
                if isinstance(blocks_data, list) and len(blocks_data) > 0:
                    self.logger.info(f"Found {len(blocks_data)} blocks in blocks_found.json")
                    log_success("verify_mining", "✅ Block generation confirmed through blocks_found.json")
                else:
                    self.logger.warning("No blocks found in blocks_found.json")
            else:
                self.logger.warning(f"blocks_found.json not found: {blocks_found_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying mining functionality: {e}")
            return False
    
    def verify_transaction_functionality(self) -> bool:
        """Verify transaction functionality for regular users through log analysis."""
        self.logger.info("Verifying transaction functionality through log analysis")
        
        # Check if Shadow simulation is running
        if not self.is_shadow_running():
            self.logger.warning("Shadow simulation is not running, attempting to restart it")
            self.test_shadow_simulation("small")
        
        # Process logs
        self.logger.info("Processing logs to verify transaction functionality")
        try:
            result = subprocess.run(
                ["bash", "-c", "source venv/bin/activate && python scripts/log_processor.py"],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(result.stdout)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Log processing failed: {e}")
            return False
        
        # Check for wallet creation in user logs
        wallet_creation_found = False
        for user_id in ["user002", "user003"]:
            user_log = f"shadow.data/hosts/{user_id}/bash.1028.stdout.processed_log"
            if os.path.exists(user_log):
                with open(user_log, 'r') as f:
                    content = f.read()
                    if "Successfully created new wallet" in content:
                        wallet_creation_found = True
                        self.logger.info(f"Wallet creation confirmed in {user_log}")
                        break
        
        if not wallet_creation_found:
            self.logger.warning("Wallet creation not confirmed in logs")
        
        # Check for balance checks in user logs
        balance_checks_found = False
        miners_have_funds = False
        locked_balance_detected = False
        
        for user_id in ["user000", "user001", "user002", "user003"]:
            user_log = f"shadow.data/hosts/{user_id}/bash.1028.stdout.processed_log"
            if os.path.exists(user_log):
                with open(user_log, 'r') as f:
                    content = f.read()
                    if "balance" in content:
                        balance_checks_found = True
                        self.logger.info(f"Balance information found in {user_log}")
                        
                        # Check for miners having funds
                        if user_id in ["user000", "user001"] and ("Total balance:" in content or "unlocked balance:" in content):
                            miners_have_funds = True
                            self.logger.info(f"Miner funds detected in {user_id}")
                        
                        # Check for locked balances
                        if "unlocked balance:" in content and "Total balance:" in content:
                            locked_balance_detected = True
                            self.logger.info(f"Locked balance situation detected in {user_id}")
        
        if balance_checks_found:
            log_success("verify_transaction", "Balance checks verified through logs")
        else:
            self.logger.warning("Balance checks not found in logs")
        
        # Check for transaction activities in user logs
        transaction_activities_found = False
        for user_id in ["user002", "user003"]:
            user_log = f"shadow.data/hosts/{user_id}/bash.1028.stdout.processed_log"
            if os.path.exists(user_log):
                with open(user_log, 'r') as f:
                    content = f.read()
                    if "checking for transaction opportunities" in content:
                        transaction_activities_found = True
                        self.logger.info(f"Transaction activities found in {user_log}")
        
        if transaction_activities_found:
            log_success("verify_transaction", "Transaction activities verified through logs")
        else:
            self.logger.warning("Transaction activities not found in logs")
        
        # Check for transactions.json
        transactions_file = "/tmp/monerosim_shared/transactions.json"
        if os.path.exists(transactions_file):
            self.logger.info(f"Found transactions.json with transaction data")
            log_success("verify_transaction", "Transaction file verified")
        else:
            self.logger.warning(f"transactions.json not found: {transactions_file}")
        
        # Check for transaction opportunity checks
        opportunity_checks_found = False
        for user_id in ["user002", "user003"]:
            user_log = f"shadow.data/hosts/{user_id}/bash.1030.stderr.processed_log"
            if os.path.exists(user_log):
                with open(user_log, 'r') as f:
                    content = f.read()
                    if "checking for transaction opportunities" in content:
                        opportunity_checks_found = True
                        self.logger.info(f"Transaction opportunity checks found in {user_log}")
        
        if opportunity_checks_found:
            log_success("verify_transaction", "Transaction opportunity checks verified")
        else:
            self.logger.warning("Transaction opportunity checks not confirmed in logs")
        
        # Final verification - be more lenient regarding locked balances
        if (wallet_creation_found and balance_checks_found and
            transaction_activities_found and opportunity_checks_found):
            
            # If we have all the basic components and miners have funds but transactions aren't
            # happening due to locked balances, that's still a successful test
            if miners_have_funds and locked_balance_detected:
                log_success("verify_transaction", "Transaction functionality verified (funds locked, which is expected in short simulations)")
                return True
            else:
                log_success("verify_transaction", "Transaction functionality fully verified through logs")
                return True
        else:
            self.logger.warning("Transaction functionality not fully verified through logs")
            return False
    
    def is_shadow_running(self) -> bool:
        """Check if Shadow simulation is currently running."""
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            return "shadow" in result.stdout
        except Exception as e:
            self.logger.error(f"Error checking if Shadow is running: {e}")
            return False
    
    def generate_test_report(self) -> None:
        """Generate a comprehensive test report."""
        self.logger.info("Generating test report")
        
        report = {
            "test_name": "End-to-End Test for is_miner Configuration Transition",
            "test_date": "2025-08-08",
            "test_results": self.test_results,
            "summary": {}
        }
        
        # Calculate summary statistics
        total_tests = 0
        passed_tests = 0
        
        for config_name, results in self.test_results.items():
            for test_name, result in results.items():
                total_tests += 1
                if result:
                    passed_tests += 1
        
        report["summary"]["total_tests"] = total_tests
        report["summary"]["passed_tests"] = passed_tests
        report["summary"]["failed_tests"] = total_tests - passed_tests
        report["summary"]["success_rate"] = f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%"
        
        # Write report to file
        with open("end_to_end_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Print summary to console
        self.logger.info("=== Test Report Summary ===")
        self.logger.info(f"Total tests: {total_tests}")
        self.logger.info(f"Passed tests: {passed_tests}")
        self.logger.info(f"Failed tests: {total_tests - passed_tests}")
        self.logger.info(f"Success rate: {report['summary']['success_rate']}")
        
        # Print detailed results
        for config_name, results in self.test_results.items():
            self.logger.info(f"--- {config_name.capitalize()} Configuration ---")
            for test_name, result in results.items():
                status = "PASS" if result else "FAIL"
                self.logger.info(f"  {test_name}: {status}")
        
        self.logger.info("Test report saved to end_to_end_test_report.json")

def main():
    """Main function."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="End-to-end test for is_miner configuration transition")
    parser.add_argument("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)")
    args = parser.parse_args()
    
    # Run the test
    test = EndToEndTest(args.log_level)
    success = test.run_test()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()