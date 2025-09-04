#!/usr/bin/env python3
"""
Hierarchical Addressing Test Runner

This script provides a convenient interface to run the hierarchical addressing
and inter-network communication tests. It handles setup, execution, and
result analysis for comprehensive validation of the network topology system.
"""

import argparse
import sys
import time
import json
from pathlib import Path
from typing import Optional

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.test_hierarchical_addressing import HierarchicalAddressingTest


class HierarchicalAddressingTestRunner:
    """Test runner for hierarchical addressing validation"""

    def __init__(self, shared_dir: Path = Path("/tmp/monerosim_shared")):
        self.shared_dir = shared_dir
        self.test_instance: Optional[HierarchicalAddressingTest] = None

    def setup_test_environment(self) -> bool:
        """Set up the test environment"""
        print("Setting up hierarchical addressing test environment...")

        # Ensure shared directory exists
        self.shared_dir.mkdir(mode=0o755, exist_ok=True)

        # Check for required files
        required_files = [
            "global_network_20_nodes_no_comments.gml",
            "config_global_20_agents.yaml"
        ]

        missing_files = []
        for filename in required_files:
            if not Path(filename).exists():
                missing_files.append(filename)

        if missing_files:
            print(f"❌ Missing required files: {missing_files}")
            print("Please ensure the following files are present:")
            for filename in missing_files:
                print(f"  - {filename}")
            return False

        print("✅ Test environment setup complete")
        return True

    def run_test(self, log_level: str = "INFO") -> bool:
        """Run the hierarchical addressing test"""
        print("🚀 Starting Hierarchical Addressing and Inter-Network Communication Test")
        print("=" * 80)

        # Create test instance
        self.test_instance = HierarchicalAddressingTest(
            shared_dir=self.shared_dir,
            log_level=log_level
        )

        # Run all tests
        start_time = time.time()
        success = self.test_instance.run_all_tests()
        end_time = time.time()

        # Print execution time
        execution_time = end_time - start_time
        print(f"⏱️  Execution Time: {execution_time:.2f} seconds")
        return success

    def analyze_results(self) -> dict:
        """Analyze test results and provide insights"""
        # Load the test report
        report_path = self.shared_dir / "hierarchical_addressing_test_report.json"
        if not report_path.exists():
            return {"error": "Test report not found. Run tests first to generate a report."}

        with open(report_path, 'r') as f:
            report = json.load(f)

        # Analyze results
        analysis = {
            "summary": report["test_summary"],
            "network_health": self._analyze_network_health(report),
            "recommendations": self._generate_recommendations(report),
            "performance_metrics": self._calculate_performance_metrics(report)
        }

        return analysis

    def _analyze_network_health(self, report: dict) -> dict:
        """Analyze the overall network health from test results"""
        test_results = report["test_results"]
        network_topology = report.get("network_topology", {})

        health_score = 0
        max_score = len(test_results)

        for result in test_results:
            if result["passed"]:
                health_score += 1

        health_percentage = (health_score / max_score * 100) if max_score > 0 else 0

        # Determine health status
        if health_percentage >= 90:
            status = "Excellent"
        elif health_percentage >= 75:
            status = "Good"
        elif health_percentage >= 60:
            status = "Fair"
        else:
            status = "Poor"

        return {
            "health_score": health_score,
            "max_score": max_score,
            "health_percentage": health_percentage,
            "status": status,
            "as_coverage": len(network_topology.get("autonomous_systems", {})),
            "expected_as_groups": 5  # Based on the global network configuration
        }

    def _generate_recommendations(self, report: dict) -> list:
        """Generate recommendations based on test results"""
        recommendations = []
        test_results = report["test_results"]

        # Check for failed tests
        failed_tests = [result for result in test_results if not result["passed"]]

        for failed_test in failed_tests:
            test_name = failed_test["test_name"]
            details = failed_test.get("details", {})

            if test_name == "network_topology_validation":
                if "missing" in details:
                    recommendations.append(
                        f"Add missing autonomous systems: {details['missing']}"
                    )
                if "invalid_ips" in details:
                    recommendations.append(
                        f"Fix invalid IP addresses in AS groups: {details['invalid_ips']}"
                    )

            elif test_name == "as_aware_ip_assignment":
                if "incorrect_mappings" in details:
                    recommendations.append(
                        f"Correct IP to AS mappings for {len(details['incorrect_mappings'])} addresses"
                    )

            elif test_name == "shared_state_communication":
                shared_files = details.get("shared_files", {})
                missing_files = [
                    filename for filename, status in shared_files.items()
                    if not status.get("exists", False)
                ]
                if missing_files:
                    recommendations.append(
                        f"Create missing shared state files: {missing_files}"
                    )

            elif test_name == "cross_as_transaction_flow":
                if details.get("as_groups_with_wallets", 0) < 2:
                    recommendations.append(
                        "Ensure at least 2 AS groups have agents with wallet capabilities"
                    )

        # General recommendations
        if not failed_tests:
            recommendations.append("Network topology and addressing system are functioning correctly")
            recommendations.append("Consider adding more comprehensive cross-AS transaction testing")

        return recommendations

    def _calculate_performance_metrics(self, report: dict) -> dict:
        """Calculate performance metrics from test results"""
        test_results = report["test_results"]
        network_topology = report.get("network_topology", {})

        # Calculate AS distribution efficiency
        as_distribution = {}
        if "autonomous_systems" in network_topology:
            total_agents = sum(len(ips) for ips in network_topology["autonomous_systems"].values())
            as_distribution = {
                as_num: {
                    "agent_count": len(ips),
                    "percentage": (len(ips) / total_agents * 100) if total_agents > 0 else 0
                }
                for as_num, ips in network_topology["autonomous_systems"].items()
            }

        return {
            "test_execution_time": report.get("timestamp", 0),
            "as_distribution_efficiency": as_distribution,
            "total_as_groups": len(network_topology.get("autonomous_systems", {})),
            "test_coverage": len(test_results)
        }

    def print_analysis_report(self, analysis: dict):
        """Print a formatted analysis report"""
        print("\n" + "=" * 80)
        print("HIERARCHICAL ADDRESSING TEST ANALYSIS REPORT")
        print("=" * 80)

        # Summary
        summary = analysis["summary"]
        print("\n📊 SUMMARY:")
        print(f"  Overall Result: {summary['overall_result']}")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        print(f"  Tests Passed: {summary['passed_tests']}/{summary['total_tests']}")

        # Network Health
        health = analysis["network_health"]
        print("\n🏥 NETWORK HEALTH:")
        print(f"  Status: {health['status']}")
        print(f"  Health Score: {health['health_score']}/{health['max_score']}")
        print(f"  AS Coverage: {health['as_coverage']}/{health['expected_as_groups']}")

        # Performance Metrics
        perf = analysis["performance_metrics"]
        print("\n⚡ PERFORMANCE METRICS:")
        print(f"  AS Groups: {perf['total_as_groups']}")
        print(f"  Test Coverage: {perf['test_coverage']} tests")

        if perf["as_distribution_efficiency"]:
            print("  AS Distribution:")
            for as_num, stats in perf["as_distribution_efficiency"].items():
                print(f"    AS {as_num}: {stats['agent_count']} agents ({stats['percentage']:.1f}%)")

        # Recommendations
        recommendations = analysis["recommendations"]
        if recommendations:
            print("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        print("\n" + "=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Hierarchical Addressing Test Runner"
    )
    parser.add_argument(
        "--shared-dir",
        type=Path,
        default=Path("/tmp/monerosim_shared"),
        help="Shared directory for simulation state"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level for tests"
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip environment setup checks"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze existing test results, don't run tests"
    )

    args = parser.parse_args()

    # Create test runner
    runner = HierarchicalAddressingTestRunner(shared_dir=args.shared_dir)

    # Setup environment
    if not args.skip_setup and not args.analyze_only:
        if not runner.setup_test_environment():
            sys.exit(1)

    # Run tests or analyze results
    if args.analyze_only:
        print("🔍 Analyzing existing test results...")
        analysis = runner.analyze_results()
        if "error" in analysis:
            print(f"❌ Analysis failed: {analysis['error']}")
            sys.exit(1)
        else:
            runner.print_analysis_report(analysis)
    else:
        # Run the test
        success = runner.run_test(log_level=args.log_level)

        # Analyze and display results
        analysis = runner.analyze_results()
        if "error" not in analysis:
            runner.print_analysis_report(analysis)

        # Exit with appropriate code
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()