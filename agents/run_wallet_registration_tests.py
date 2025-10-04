#!/usr/bin/env python3
"""
Test runner script for wallet registration tests.
Executes all test suites and generates a comprehensive report.
"""

import sys
import os
import time
import unittest
import json
import traceback
import importlib.util
from pathlib import Path
from io import StringIO
from datetime import datetime

# Add the parent directory to the path to import modules
sys.path.insert(0, str(Path(__file__).parent))

# Import all test modules using importlib to avoid relative import issues
def load_test_module(module_name, file_path):
    """Load a test module from file path"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Load test modules
agents_dir = Path(__file__).parent
test_wallet_registration = load_test_module("test_wallet_registration", agents_dir / "test_wallet_registration.py")
test_block_controller_wallet_registration = load_test_module("test_block_controller_wallet_registration", agents_dir / "test_block_controller_wallet_registration.py")
test_regular_user_wallet_registration = load_test_module("test_regular_user_wallet_registration", agents_dir / "test_regular_user_wallet_registration.py")
test_integration_wallet_registration = load_test_module("test_integration_wallet_registration", agents_dir / "test_integration_wallet_registration.py")
test_timing_scenarios = load_test_module("test_timing_scenarios", agents_dir / "test_timing_scenarios.py")
test_error_handling = load_test_module("test_error_handling", agents_dir / "test_error_handling.py")
test_backward_compatibility = load_test_module("test_backward_compatibility", agents_dir / "test_backward_compatibility.py")

# Import test classes
TestWalletRegistration = test_wallet_registration.TestWalletRegistration
TestBlockControllerWalletRegistration = test_block_controller_wallet_registration.TestBlockControllerWalletRegistration
TestRegularUserWalletRegistration = test_regular_user_wallet_registration.TestRegularUserWalletRegistration
TestIntegrationWalletRegistration = test_integration_wallet_registration.TestIntegrationWalletRegistration
TestTimingScenarios = test_timing_scenarios.TestTimingScenarios
TestErrorHandling = test_error_handling.TestErrorHandling
TestBackwardCompatibility = test_backward_compatibility.TestBackwardCompatibility


class TestResult:
    """Class to store test results"""
    
    def __init__(self, name):
        self.name = name
        self.tests_run = 0
        self.failures = 0
        self.errors = 0
        self.skipped = 0
        self.success_rate = 0.0
        self.duration = 0.0
        self.test_details = []
        self.failure_details = []
        self.error_details = []


class TestRunner:
    """Test runner for wallet registration tests"""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None
        self.total_duration = 0.0
        self.total_tests = 0
        self.total_failures = 0
        self.total_errors = 0
        self.total_skipped = 0
        self.overall_success_rate = 0.0
        
    def run_test_suite(self, test_class, suite_name):
        """Run a test suite and capture results"""
        print(f"\n{'='*60}")
        print(f"Running {suite_name}")
        print(f"{'='*60}")
        
        # Create test result object
        result = TestResult(suite_name)
        
        # Create test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(test_class)
        
        # Create custom test result class to capture details
        class CustomTestResult(unittest.TextTestResult):
            def __init__(self, stream, descriptions, verbosity):
                super().__init__(stream, descriptions, verbosity)
                self.test_results = []
                self.failure_results = []
                self.error_results = []
                
            def addSuccess(self, test):
                super().addSuccess(test)
                self.test_results.append({
                    'test': str(test),
                    'status': 'SUCCESS',
                    'message': 'Test passed successfully'
                })
                
            def addFailure(self, test, err):
                super().addFailure(test, err)
                self.failure_results.append({
                    'test': str(test),
                    'status': 'FAILURE',
                    'message': str(err[1]),
                    'traceback': ''.join(traceback.format_exception(*err))
                })
                
            def addError(self, test, err):
                super().addError(test, err)
                self.error_results.append({
                    'test': str(test),
                    'status': 'ERROR',
                    'message': str(err[1]),
                    'traceback': ''.join(traceback.format_exception(*err))
                })
                
            def addSkip(self, test, reason):
                super().addSkip(test, reason)
                self.test_results.append({
                    'test': str(test),
                    'status': 'SKIPPED',
                    'message': reason
                })
        
        # Run tests with custom result handler
        stream = StringIO()
        start_time = time.time()
        
        runner = unittest.TextTestRunner(
            stream=stream,
            verbosity=2,
            resultclass=CustomTestResult
        )
        
        test_result = runner.run(suite)
        end_time = time.time()
        
        # Store results
        result.tests_run = test_result.testsRun
        result.failures = len(test_result.failures)
        result.errors = len(test_result.errors)
        result.skipped = len(test_result.skipped) if hasattr(test_result, 'skipped') else 0
        result.duration = end_time - start_time
        
        if result.tests_run > 0:
            result.success_rate = ((result.tests_run - result.failures - result.errors) / result.tests_run) * 100
        
        # Store test details
        if hasattr(test_result, 'test_results'):
            result.test_details = test_result.test_results
        if hasattr(test_result, 'failure_results'):
            result.failure_details = test_result.failure_results
        if hasattr(test_result, 'error_results'):
            result.error_details = test_result.error_results
        
        # Print results
        output = stream.getvalue()
        print(output)
        
        # Store in results dictionary
        self.results[suite_name] = result
        
        # Print summary
        print(f"\n{suite_name} Summary:")
        print(f"  Tests run: {result.tests_run}")
        print(f"  Failures: {result.failures}")
        print(f"  Errors: {result.errors}")
        print(f"  Skipped: {result.skipped}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Duration: {result.duration:.2f} seconds")
        
        return result
    
    def run_all_tests(self):
        """Run all test suites"""
        print("Starting Wallet Registration Test Suite")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        self.start_time = time.time()
        
        # Define test suites
        test_suites = [
            (TestWalletRegistration, "Wallet Registration Tests"),
            (TestBlockControllerWalletRegistration, "Block Controller Wallet Registration Tests"),
            (TestRegularUserWalletRegistration, "Regular User Wallet Registration Tests"),
            (TestIntegrationWalletRegistration, "Integration Tests"),
            (TestTimingScenarios, "Timing Scenario Tests"),
            (TestErrorHandling, "Error Handling Tests"),
            (TestBackwardCompatibility, "Backward Compatibility Tests")
        ]
        
        # Run all test suites
        for test_class, suite_name in test_suites:
            try:
                self.run_test_suite(test_class, suite_name)
            except Exception as e:
                print(f"Error running {suite_name}: {e}")
                traceback.print_exc()
        
        self.end_time = time.time()
        self.total_duration = self.end_time - self.start_time
        
        # Calculate totals
        self.total_tests = sum(r.tests_run for r in self.results.values())
        self.total_failures = sum(r.failures for r in self.results.values())
        self.total_errors = sum(r.errors for r in self.results.values())
        self.total_skipped = sum(r.skipped for r in self.results.values())
        
        if self.total_tests > 0:
            self.overall_success_rate = ((self.total_tests - self.total_failures - self.total_errors) / self.total_tests) * 100
    
    def generate_report(self):
        """Generate a comprehensive test report"""
        report = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": self.total_duration,
                "total_tests": self.total_tests,
                "total_failures": self.total_failures,
                "total_errors": self.total_errors,
                "total_skipped": self.total_skipped,
                "overall_success_rate": self.overall_success_rate
            },
            "test_suites": {}
        }
        
        # Add details for each test suite
        for suite_name, result in self.results.items():
            suite_report = {
                "tests_run": result.tests_run,
                "failures": result.failures,
                "errors": result.errors,
                "skipped": result.skipped,
                "success_rate": result.success_rate,
                "duration_seconds": result.duration,
                "test_details": result.test_details,
                "failure_details": result.failure_details,
                "error_details": result.error_details
            }
            
            report["test_suites"][suite_name] = suite_report
        
        # Add summary and recommendations
        report["summary"] = self._generate_summary()
        report["recommendations"] = self._generate_recommendations()
        
        return report
    
    def _generate_summary(self):
        """Generate a summary of the test results"""
        summary = {
            "status": "PASSED" if self.total_failures == 0 and self.total_errors == 0 else "FAILED",
            "key_findings": [],
            "performance_metrics": {
                "total_test_time": self.total_duration,
                "average_test_time": self.total_duration / max(len(self.results), 1),
                "fastest_suite": None,
                "slowest_suite": None
            }
        }
        
        # Find fastest and slowest suites
        if self.results:
            fastest_suite = min(self.results.items(), key=lambda x: x[1].duration)
            slowest_suite = max(self.results.items(), key=lambda x: x[1].duration)
            
            summary["performance_metrics"]["fastest_suite"] = {
                "name": fastest_suite[0],
                "duration": fastest_suite[1].duration
            }
            
            summary["performance_metrics"]["slowest_suite"] = {
                "name": slowest_suite[0],
                "duration": slowest_suite[1].duration
            }
        
        # Add key findings
        if self.overall_success_rate >= 95:
            summary["key_findings"].append("Excellent test success rate")
        elif self.overall_success_rate >= 80:
            summary["key_findings"].append("Good test success rate")
        else:
            summary["key_findings"].append("Test success rate needs improvement")
        
        if self.total_errors > 0:
            summary["key_findings"].append(f"{self.total_errors} test errors detected")
        
        if self.total_failures > 0:
            summary["key_findings"].append(f"{self.total_failures} test failures detected")
        
        return summary
    
    def _generate_recommendations(self):
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for failures and errors
        if self.total_failures > 0:
            recommendations.append("Review and fix failing tests")
        
        if self.total_errors > 0:
            recommendations.append("Investigate and resolve test errors")
        
        # Check performance
        if self.total_duration > 300:  # 5 minutes
            recommendations.append("Consider optimizing test performance")
        
        # Check specific test suites
        for suite_name, result in self.results.items():
            if result.failures > 0 or result.errors > 0:
                recommendations.append(f"Focus on fixing issues in {suite_name}")
        
        # Check success rates
        for suite_name, result in self.results.items():
            if result.success_rate < 90:
                recommendations.append(f"Improve test coverage and reliability in {suite_name}")
        
        if not recommendations:
            recommendations.append("All tests passed successfully. Continue maintaining test quality.")
        
        return recommendations
    
    def save_report(self, filename):
        """Save the test report to a file"""
        report = self.generate_report()
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nTest report saved to: {filename}")
    
    def print_summary(self):
        """Print a summary of all test results"""
        print(f"\n{'='*60}")
        print("WALLET REGISTRATION TEST SUITE SUMMARY")
        print(f"{'='*60}")
        
        print(f"Total Duration: {self.total_duration:.2f} seconds")
        print(f"Total Tests: {self.total_tests}")
        print(f"Total Failures: {self.total_failures}")
        print(f"Total Errors: {self.total_errors}")
        print(f"Total Skipped: {self.total_skipped}")
        print(f"Overall Success Rate: {self.overall_success_rate:.1f}%")
        
        print(f"\nTest Suite Breakdown:")
        for suite_name, result in self.results.items():
            status = "PASS" if result.failures == 0 and result.errors == 0 else "FAIL"
            print(f"  {suite_name}: {result.tests_run} tests, {result.success_rate:.1f}% success, {status}")
        
        # Print recommendations
        report = self.generate_report()
        if report["recommendations"]:
            print(f"\nRecommendations:")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. {rec}")


def main():
    """Main function to run all tests"""
    # Create test runner
    runner = TestRunner()
    
    # Run all tests
    runner.run_all_tests()
    
    # Print summary
    runner.print_summary()
    
    # Generate timestamp for report filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"wallet_registration_test_report_{timestamp}.json"
    
    # Save report
    runner.save_report(report_filename)
    
    # Return exit code based on results
    return 0 if runner.total_failures == 0 and runner.total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())