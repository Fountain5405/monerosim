#!/usr/bin/env python3
"""
run_all_tests.py - Main Test Runner for MoneroSim Scripts

This script discovers and runs all test files in the scripts directory,
provides test result summaries, and supports coverage reporting.
"""

import sys
import os
import time
import argparse
import subprocess
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import unittest
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import test configuration
from scripts.test_config import (
    TEST_CATEGORIES, TEST_TIMEOUTS, TestResults, 
    COVERAGE_CONFIG, setup_test_environment
)
from scripts.error_handling import (
    log_info, log_error, log_success, log_warning,
    ColorCodes
)

COMPONENT = "TEST_RUNNER"


class TestRunner:
    """Main test runner for MoneroSim scripts."""
    
    def __init__(self, verbose: bool = False, coverage: bool = False,
                 category: Optional[str] = None, pattern: Optional[str] = None):
        """
        Initialize test runner.
        
        Args:
            verbose: Enable verbose output
            coverage: Enable coverage reporting
            category: Run only tests in this category
            pattern: Pattern to match test files
        """
        self.verbose = verbose
        self.coverage = coverage
        self.category = category
        self.pattern = pattern or "test_*.py"
        self.results = TestResults()
        self.test_files: List[Path] = []
        self.scripts_dir = Path(__file__).parent
    
    def discover_tests(self) -> List[Path]:
        """
        Discover all test files in the scripts directory.
        
        Returns:
            List of test file paths
        """
        log_info(COMPONENT, f"Discovering tests with pattern: {self.pattern}")
        
        test_files = []
        for file_path in self.scripts_dir.glob(self.pattern):
            if file_path.is_file() and file_path.name != "run_all_tests.py":
                test_files.append(file_path)
        
        # Sort for consistent ordering
        test_files.sort()
        
        log_info(COMPONENT, f"Found {len(test_files)} test files")
        return test_files
    
    def run_test_file(self, test_file: Path) -> Tuple[bool, str]:
        """
        Run a single test file.
        
        Args:
            test_file: Path to the test file
            
        Returns:
            Tuple of (success, output)
        """
        log_info(COMPONENT, f"Running tests in: {test_file.name}")
        
        start_time = time.time()
        
        try:
            # Run the test file as a subprocess
            cmd = [sys.executable, str(test_file)]
            if self.verbose:
                cmd.append("-v")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUTS.get(self.category, TEST_TIMEOUTS["default"])
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                self.results.add_pass(test_file.name, duration)
                log_success(COMPONENT, f"✓ {test_file.name} passed ({duration:.2f}s)")
                return True, result.stdout + result.stderr
            else:
                self.results.add_fail(test_file.name, result.stderr or "Test failed", duration)
                log_error(COMPONENT, f"✗ {test_file.name} failed ({duration:.2f}s)")
                return False, result.stdout + result.stderr
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            error_msg = f"Test timed out after {TEST_TIMEOUTS.get(self.category, TEST_TIMEOUTS['default'])}s"
            self.results.add_fail(test_file.name, error_msg, duration)
            log_error(COMPONENT, f"✗ {test_file.name} timed out")
            return False, error_msg
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Error running test: {str(e)}"
            self.results.add_fail(test_file.name, error_msg, duration)
            log_error(COMPONENT, f"✗ {test_file.name} error: {e}")
            return False, error_msg
    
    def run_unittest_discovery(self) -> bool:
        """
        Run tests using unittest discovery.
        
        Returns:
            True if all tests passed
        """
        log_info(COMPONENT, "Running tests with unittest discovery")
        
        # Create test loader
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Discover tests
        for test_file in self.test_files:
            try:
                # Load tests from the file
                spec = importlib.util.spec_from_file_location(
                    test_file.stem, test_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Add tests to suite
                file_suite = loader.loadTestsFromModule(module)
                suite.addTests(file_suite)
                
            except Exception as e:
                log_error(COMPONENT, f"Failed to load tests from {test_file.name}: {e}")
        
        # Run tests
        runner = unittest.TextTestRunner(
            verbosity=2 if self.verbose else 1,
            stream=sys.stdout
        )
        
        result = runner.run(suite)
        
        # Update our results
        self.results.passed = result.testsRun - len(result.failures) - len(result.errors)
        self.results.failed = len(result.failures) + len(result.errors)
        
        for test, error in result.failures + result.errors:
            self.results.errors.append((str(test), error))
        
        return result.wasSuccessful()
    
    def run_with_coverage(self) -> bool:
        """
        Run tests with coverage reporting.
        
        Returns:
            True if coverage was successful
        """
        try:
            import coverage
        except ImportError:
            log_error(COMPONENT, "Coverage module not installed. Install with: pip install coverage")
            return False
        
        log_info(COMPONENT, "Running tests with coverage reporting")
        
        # Initialize coverage
        cov = coverage.Coverage(
            source=COVERAGE_CONFIG["source"],
            omit=COVERAGE_CONFIG["omit"]
        )
        
        # Start coverage
        cov.start()
        
        # Run all tests
        all_passed = True
        for test_file in self.test_files:
            success, _ = self.run_test_file(test_file)
            if not success:
                all_passed = False
        
        # Stop coverage
        cov.stop()
        cov.save()
        
        # Generate report
        log_info(COMPONENT, "\nCoverage Report:")
        log_info(COMPONENT, "=" * 60)
        
        # Print report to console
        cov.report()
        
        # Generate HTML report
        html_dir = self.scripts_dir / "htmlcov"
        cov.html_report(directory=str(html_dir))
        log_info(COMPONENT, f"\nDetailed HTML coverage report: {html_dir}/index.html")
        
        # Generate JSON report for further processing
        json_file = self.scripts_dir / "coverage.json"
        cov.json_report(outfile=str(json_file))
        
        return all_passed
    
    def run_all(self) -> bool:
        """
        Run all discovered tests.
        
        Returns:
            True if all tests passed
        """
        # Discover tests
        self.test_files = self.discover_tests()
        
        if not self.test_files:
            log_warning(COMPONENT, "No test files found")
            return True
        
        log_info(COMPONENT, f"\n{'='*60}")
        log_info(COMPONENT, "Running MoneroSim Test Suite")
        log_info(COMPONENT, f"{'='*60}\n")
        
        # Run with coverage if requested
        if self.coverage:
            return self.run_with_coverage()
        
        # Run each test file
        all_passed = True
        for test_file in self.test_files:
            success, output = self.run_test_file(test_file)
            
            if self.verbose and output:
                print(f"\n--- Output from {test_file.name} ---")
                print(output)
                print(f"--- End of output from {test_file.name} ---\n")
            
            if not success:
                all_passed = False
        
        return all_passed
    
    def print_summary(self) -> None:
        """Print test results summary."""
        print(self.results.get_summary())
        
        # Print timing information
        if self.results.test_times:
            print(f"\nTest Execution Times:")
            print(f"{'='*50}")
            for test_name, duration in sorted(
                self.results.test_times.items(), 
                key=lambda x: x[1], 
                reverse=True
            ):
                print(f"  {test_name}: {duration:.2f}s")
            
            total_time = sum(self.results.test_times.values())
            print(f"\nTotal execution time: {total_time:.2f}s")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Run all tests for MoneroSim scripts"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    
    parser.add_argument(
        "--category",
        choices=list(TEST_CATEGORIES.keys()),
        help="Run only tests in specified category"
    )
    
    parser.add_argument(
        "--pattern",
        help="Pattern to match test files (default: test_*.py)"
    )
    
    parser.add_argument(
        "--file",
        help="Run only a specific test file"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available test files without running them"
    )
    
    parser.add_argument(
        "--junit",
        help="Generate JUnit XML report to specified file"
    )
    
    parser.add_argument(
        "--failfast",
        action="store_true",
        help="Stop on first test failure"
    )
    
    args = parser.parse_args()
    
    # Setup test environment
    setup_test_environment()
    
    # Create test runner
    runner = TestRunner(
        verbose=args.verbose,
        coverage=args.coverage,
        category=args.category,
        pattern=args.pattern
    )
    
    # Handle list option
    if args.list:
        test_files = runner.discover_tests()
        print("Available test files:")
        for test_file in test_files:
            print(f"  - {test_file.name}")
        return 0
    
    # Handle single file option
    if args.file:
        test_path = Path(args.file)
        if not test_path.exists():
            test_path = runner.scripts_dir / args.file
        
        if not test_path.exists():
            log_error(COMPONENT, f"Test file not found: {args.file}")
            return 1
        
        runner.test_files = [test_path]
        success, output = runner.run_test_file(test_path)
        
        if args.verbose or not success:
            print(output)
        
        runner.print_summary()
        return 0 if success else 1
    
    # Run all tests
    all_passed = runner.run_all()
    
    # Print summary
    runner.print_summary()
    
    # Generate JUnit report if requested
    if args.junit:
        # This would require additional implementation
        log_warning(COMPONENT, "JUnit report generation not yet implemented")
    
    # Return appropriate exit code
    if all_passed:
        log_success(COMPONENT, "\n✓ All tests passed!")
        return 0
    else:
        log_error(COMPONENT, "\n✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())