#!/usr/bin/env python3
"""
Comprehensive Internet Topology Test Runner

This script runs the comprehensive end-to-end test for the realistic internet
topology simulation system. It handles building the monerosim binary if needed
and executes all test validations.

Usage:
    python3 scripts/run_comprehensive_internet_test.py [--build] [--verbose]

Options:
    --build    : Build the monerosim binary before running tests
    --verbose  : Enable verbose logging
    --help     : Show this help message
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path

def setup_logging(verbose=False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('comprehensive_test_runner.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def build_monerosim():
    """Build the monerosim binary"""
    logger = logging.getLogger(__name__)

    logger.info("Building monerosim binary...")

    try:
        # Check if cargo is available
        result = subprocess.run(['cargo', '--version'],
                              capture_output=True, text=True, check=True)
        logger.info(f"Cargo version: {result.stdout.strip()}")

        # Build the binary
        result = subprocess.run(['cargo', 'build', '--release'],
                              capture_output=True, text=True, check=True, timeout=300)

        if result.returncode == 0:
            logger.info("Monerosim binary built successfully")
            return True
        else:
            logger.error(f"Build failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Build timed out after 5 minutes")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed with error: {e}")
        return False
    except FileNotFoundError:
        logger.error("Cargo not found. Please install Rust toolchain.")
        return False

def check_prerequisites():
    """Check if all prerequisites are met"""
    logger = logging.getLogger(__name__)

    # Check if required files exist
    required_files = [
        "comprehensive_internet_topology_test.gml",
        "config_comprehensive_internet_test.yaml",
        "scripts/comprehensive_internet_topology_test.py"
    ]

    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        logger.error(f"Missing required files: {missing_files}")
        return False

    # Check if monerosim binary exists
    if not os.path.exists("target/release/monerosim"):
        logger.warning("Monerosim binary not found. Will need to build it.")
        return False

    logger.info("All prerequisites met")
    return True

def run_test():
    """Run the comprehensive test"""
    logger = logging.getLogger(__name__)

    logger.info("Running comprehensive internet topology test...")

    try:
        # Import and run the test
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        from comprehensive_internet_topology_test import ComprehensiveInternetTopologyTest

        test = ComprehensiveInternetTopologyTest()
        success = test.run_all_tests()

        if success:
            logger.info("🎉 All tests passed!")
            return True
        else:
            logger.error("❌ Some tests failed. Check the test report for details.")
            return False

    except ImportError as e:
        logger.error(f"Failed to import test module: {e}")
        return False
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Comprehensive Internet Topology Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/run_comprehensive_internet_test.py
  python3 scripts/run_comprehensive_internet_test.py --build
  python3 scripts/run_comprehensive_internet_test.py --verbose
  python3 scripts/run_comprehensive_internet_test.py --build --verbose
        """
    )

    parser.add_argument('--build', action='store_true',
                       help='Build the monerosim binary before running tests')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--help', action='help',
                       help='Show this help message')

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("Starting Comprehensive Internet Topology Test Runner")
    logger.info("=" * 60)

    # Check prerequisites
    if not check_prerequisites():
        if not args.build:
            logger.error("Prerequisites not met. Use --build to build the binary.")
            sys.exit(1)

    # Build if requested
    if args.build:
        if not build_monerosim():
            logger.error("Failed to build monerosim binary")
            sys.exit(1)

    # Run the test
    if run_test():
        logger.info("Test runner completed successfully")
        sys.exit(0)
    else:
        logger.error("Test runner failed")
        sys.exit(1)

if __name__ == "__main__":
    main()