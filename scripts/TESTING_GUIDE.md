# MoneroSim Scripts Testing Guide

This guide explains how to run tests for the MoneroSim Python scripts, add new tests, and follow testing best practices.

## Table of Contents

1. [Overview](#overview)
2. [Setup](#setup)
3. [Running Tests](#running-tests)
4. [Test Structure](#test-structure)
5. [Adding New Tests](#adding-new-tests)
6. [Testing Best Practices](#testing-best-practices)
7. [Coverage Goals](#coverage-goals)
8. [Troubleshooting](#troubleshooting)

## Overview

The MoneroSim test suite provides comprehensive testing for all Python scripts in the project. It includes:

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test interactions between different scripts
- **Mock Tests**: Use mock RPC responses to test without actual daemons
- **System Tests**: Test with real Shadow simulation (when available)

### Test Files

- `test_config.py` - Common test configuration and fixtures
- `run_all_tests.py` - Main test runner script
- `test_integration.py` - Integration tests for script interactions
- `test_*.py` - Individual test files for each script

## Setup

### 1. Install Dependencies

First, ensure you have the Python virtual environment activated:

```bash
cd /home/lever65/monerosim_dev/monerosim
source venv/bin/activate
```

Install testing dependencies:

```bash
pip install -r scripts/requirements.txt
```

### 2. Verify Installation

Check that all testing tools are installed:

```bash
python -m pytest --version
python -m coverage --version
```

## Running Tests

### Run All Tests

The simplest way to run all tests:

```bash
cd scripts
python run_all_tests.py
```

### Run with Verbose Output

For detailed test output:

```bash
python run_all_tests.py --verbose
```

### Run with Coverage

To generate a coverage report:

```bash
python run_all_tests.py --coverage
```

This will:
- Run all tests with coverage tracking
- Generate a console coverage report
- Create an HTML report in `scripts/htmlcov/`
- Save JSON coverage data to `scripts/coverage.json`

### Run Specific Test Files

To run a single test file:

```bash
python run_all_tests.py --file test_error_handling.py
```

### Run by Category

To run only tests in a specific category:

```bash
python run_all_tests.py --category unit
python run_all_tests.py --category integration
```

### List Available Tests

To see all available test files without running them:

```bash
python run_all_tests.py --list
```

### Using pytest Directly

You can also use pytest directly for more control:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest test_error_handling.py

# Run specific test function
pytest test_error_handling.py::test_logging

# Run with markers
pytest -m "not slow"
```

## Test Structure

### Test Configuration (`test_config.py`)

The test configuration module provides:

- **Mock RPC Responses**: Pre-defined responses for testing
- **Test Fixtures**: Common setup/teardown utilities
- **Test Categories**: Organization of test types
- **Mock Servers**: Simulated RPC servers for testing

Example usage:

```python
from test_config import TestFixtures, MOCK_RPC_RESPONSES

def test_example():
    # Create a mock RPC response
    response = TestFixtures.create_mock_rpc_response("get_info", "success")
    
    # Use mock response in test
    assert response["result"]["height"] == 12345
```

### Unit Tests

Unit tests focus on individual functions:

```python
class TestErrorHandling(unittest.TestCase):
    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        delay = exponential_backoff(3, base_delay=1, max_delay=30)
        self.assertEqual(delay, 4)  # 2^2 * 1
```

### Integration Tests

Integration tests verify script interactions:

```python
class TestScriptIntegration(unittest.TestCase):
    def test_simple_test_workflow(self):
        """Test the complete simple_test workflow."""
        # Test multiple components working together
        self.assertTrue(verify_daemon_ready(...))
        self.assertTrue(verify_wallet_created(...))
```

## Adding New Tests

### 1. Create a Test File

For a new script `my_script.py`, create `test_my_script.py`:

```python
#!/usr/bin/env python3
"""Test suite for my_script.py"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import my_script
from scripts.test_config import TestFixtures, MOCK_RPC_RESPONSES


class TestMyScript(unittest.TestCase):
    """Test cases for my_script functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.component = "TEST_MY_SCRIPT"
    
    def test_basic_functionality(self):
        """Test basic script functionality."""
        result = my_script.my_function()
        self.assertEqual(result, expected_value)


if __name__ == "__main__":
    unittest.main()
```

### 2. Add Mock Responses

If your script makes RPC calls, add mock responses to `test_config.py`:

```python
MOCK_RPC_RESPONSES["my_method"] = {
    "success": {
        "jsonrpc": "2.0",
        "id": "0",
        "result": {"data": "test"}
    },
    "error": {
        "jsonrpc": "2.0",
        "id": "0",
        "error": {"code": -1, "message": "Test error"}
    }
}
```

### 3. Use Mocking

Mock external dependencies:

```python
@patch('scripts.my_script.requests.post')
def test_rpc_call(self, mock_post):
    """Test RPC call functionality."""
    # Set up mock response
    mock_post.return_value.json.return_value = MOCK_RPC_RESPONSES["get_info"]["success"]
    
    # Call function
    result = my_script.make_rpc_call()
    
    # Verify
    self.assertTrue(result)
    mock_post.assert_called_once()
```

## Testing Best Practices

### 1. Test Isolation

Each test should be independent:

```python
def setUp(self):
    """Set up clean state for each test."""
    self.temp_dir = TestFixtures.create_temp_dir()

def tearDown(self):
    """Clean up after each test."""
    TestFixtures.cleanup_temp_dir(self.temp_dir)
```

### 2. Descriptive Test Names

Use clear, descriptive test names:

```python
def test_wallet_creation_with_existing_wallet_opens_instead(self):
    """Test that creating an existing wallet opens it instead."""
```

### 3. Test Edge Cases

Always test edge cases and error conditions:

```python
def test_invalid_node_id_raises_error(self):
    """Test that invalid node ID raises ValueError."""
    with self.assertRaises(ValueError):
        get_daemon_config("INVALID")
```

### 4. Use Assertions Effectively

Use specific assertions:

```python
# Good
self.assertEqual(response["height"], 12345)
self.assertIn("error", response)
self.assertIsNone(result)

# Less specific
self.assertTrue(response["height"] == 12345)
```

### 5. Mock External Dependencies

Always mock external services:

```python
@patch('socket.socket')
def test_connection(self, mock_socket):
    """Test socket connection."""
    mock_sock = TestFixtures.create_mock_socket(0)
    mock_socket.return_value = mock_sock
```

### 6. Test Documentation

Document what each test verifies:

```python
def test_sync_check_threshold(self):
    """
    Test that sync_check correctly identifies nodes as synchronized
    when their heights are within the threshold.
    """
```

## Coverage Goals

### Current Coverage Status

Run coverage report to see current status:

```bash
python run_all_tests.py --coverage
```

### Coverage Targets

- **Overall Coverage**: Aim for >80% coverage
- **Critical Modules**: 
  - `error_handling.py`: >90% coverage
  - `network_config.py`: >95% coverage
  - RPC functions: >85% coverage
- **New Code**: All new code should have tests

### Improving Coverage

1. Check coverage report for untested code:
   ```bash
   open scripts/htmlcov/index.html
   ```

2. Focus on:
   - Error handling paths
   - Edge cases
   - Configuration variations

3. Add tests for uncovered lines:
   ```python
   # If this line is uncovered:
   if error_code == -19:
       handle_fragmented_transaction()
   
   # Add a test:
   def test_fragmented_transaction_handling(self):
       """Test handling of fragmented transaction error."""
   ```

## Troubleshooting

### Common Issues

#### 1. Import Errors

If you get import errors:

```bash
# Ensure you're in the right directory
cd /home/lever65/monerosim_dev/monerosim

# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r scripts/requirements.txt
```

#### 2. Test Timeouts

For long-running tests, increase timeout:

```python
@pytest.mark.timeout(60)  # 60 second timeout
def test_long_operation(self):
    """Test that may take longer."""
```

#### 3. Mock Not Working

Ensure you're patching the right path:

```python
# Wrong
@patch('requests.post')

# Correct - patch where it's used
@patch('scripts.my_script.requests.post')
```

#### 4. Flaky Tests

For tests that occasionally fail:

```python
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_network_operation(self):
    """Test that may fail due to timing."""
```

### Debug Mode

Run tests with debugging:

```bash
# With pytest
pytest -vv --pdb  # Drop into debugger on failure

# With unittest
python -m pdb test_my_script.py
```

### Test Logs

Check test logs for details:

```bash
# Run with full output
python run_all_tests.py --verbose > test_output.log 2>&1

# Check specific test output
grep -A 10 -B 10 "FAILED" test_output.log
```

## Continuous Integration

For CI/CD integration, use:

```bash
# Run tests with JUnit output (when implemented)
python run_all_tests.py --junit test-results.xml

# Run with coverage and fail if below threshold
python run_all_tests.py --coverage --fail-under 80
```

## Contributing

When contributing new code:

1. Write tests for all new functionality
2. Ensure all tests pass: `python run_all_tests.py`
3. Check coverage: `python run_all_tests.py --coverage`
4. Follow the coding style (use `black` for formatting)
5. Update this guide if adding new test patterns

## Summary

The MoneroSim test suite ensures code quality and reliability. By following this guide and maintaining good test coverage, we can confidently make changes and add new features while preventing regressions.

Remember: **Good tests are as important as good code!**