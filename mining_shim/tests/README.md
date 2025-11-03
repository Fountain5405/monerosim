# Mining Shim Testing Suite

This directory contains comprehensive tests for the mining shim implementation.

## Test Overview

### 1. Build System Testing (`test_build.sh`)
Tests the build system, symbol verification, and installation process.

**What it tests:**
- Library compilation
- Required symbol exports (`start_mining`, `stop_mining`, `handle_new_block_notify`)
- Library size validation
- Dynamic linking verification
- Installation command functionality

**Usage:**
```bash
cd mining_shim/tests
./test_build.sh
```

### 2. Integration Testing (`test_integration.py`)
Tests Monerosim integration with mining shim configuration.

**What it tests:**
- Shadow YAML generation with mining shim environment variables
- LD_PRELOAD injection for miners only
- Environment variable validation (MINER_HASHRATE, AGENT_ID, SIMULATION_SEED)
- Registry file generation
- Non-miner agents remain unaffected

**Usage:**
```bash
cd mining_shim/tests
python3 test_integration.py
```

### 3. Unit Testing (`test_determinism.c`)
C-based unit tests for deterministic behavior and mathematical correctness.

**What it tests:**
- PRNG determinism with seeded initialization
- Exponential distribution properties
- Configuration loading from environment variables
- Mining time calculation accuracy

**Usage:**
```bash
cd mining_shim/tests
gcc -I.. test_determinism.c ../libminingshim.c -o test_determinism -lpthread -lm -ldl
./test_determinism
```

### 4. End-to-End Testing (`test_e2e.sh`)
Complete simulation test with mining shim integration.

**What it tests:**
- Full simulation execution
- Mining shim log generation
- Metrics file creation and validation
- Block discovery within expected ranges
- Normal simulation termination

**Usage:**
```bash
cd mining_shim/tests
./test_e2e.sh
```

## Test Configuration

The tests use `test_mining_shim.yaml` which defines:
- 1 miner agent (10 MH/s hashrate)
- 1 regular user agent
- 30-second simulation duration
- Switch-based network topology

## Running All Tests

### Automated Test Suite
```bash
cd mining_shim/tests
./run_all_tests.sh  # (if created)
```

### Manual Test Execution
```bash
# Build tests
./test_build.sh

# Integration tests
python3 test_integration.py

# Unit tests
gcc -I.. test_determinism.c ../libminingshim.c -o test_determinism -lpthread -lm -ldl
./test_determinism

# End-to-end tests
./test_e2e.sh
```

## Test Requirements

### System Dependencies
- GCC compiler
- Python 3.6+
- Shadow simulator
- Monerosim built and configured

### File Dependencies
- `mining_shim/libminingshim.c` and `libminingshim.h`
- `test_mining_shim.yaml` configuration file
- Built Monerosim binary

## Expected Test Results

### Successful Test Run
- All tests pass without errors
- Mining shim logs show initialization and mining activity
- Metrics files contain reasonable block counts (1-10 for 30s simulation)
- Shadow simulation terminates normally

### Common Test Failures

**Build Test Failures:**
- Missing symbols: Check function implementations in `libminingshim.c`
- Linking errors: Verify library dependencies (pthread, dl, m)

**Integration Test Failures:**
- Missing environment variables: Check Monerosim miner processing logic
- Invalid YAML: Verify `test_mining_shim.yaml` syntax

**Unit Test Failures:**
- PRNG non-deterministic: Check seed initialization
- Distribution errors: Verify exponential calculation logic

**E2E Test Failures:**
- Simulation timeout: Check Shadow installation and configuration
- No metrics: Verify mining shim library loading
- Abnormal termination: Check Shadow logs for errors

## Debugging Failed Tests

### Enable Debug Logging
```bash
export MININGSHIM_LOG_LEVEL=DEBUG
export MININGSHIM_LOG_FILE=/tmp/debug_shim.log
```

### Check Shadow Logs
```bash
tail -f shadow.log
grep "ERROR" shadow.data/hosts/*/mining_shim.log
```

### Validate Environment
```bash
# Check library loading
ldd mining_shim/libminingshim.so

# Check symbol exports
nm -D mining_shim/libminingshim.so | grep mining

# Verify configuration
python3 -c "import yaml; yaml.safe_load(open('test_mining_shim.yaml'))"
```

## Test Coverage

The test suite covers:
- ✅ Build system validation
- ✅ Symbol export verification
- ✅ Monerosim integration
- ✅ Environment variable handling
- ✅ Deterministic PRNG behavior
- ✅ Exponential distribution accuracy
- ✅ Mining time calculations
- ✅ End-to-end simulation execution
- ✅ Log file generation
- ✅ Metrics export and validation

## Continuous Integration

These tests are designed to be run in CI/CD pipelines:
- No external dependencies beyond the project
- Clear pass/fail criteria
- Comprehensive error reporting
- Reasonable execution time (< 5 minutes)

## Adding New Tests

When adding new test files:
1. Follow naming convention: `test_*.sh` or `test_*.py` or `test_*.c`
2. Include clear success/failure messages
3. Document test purpose and requirements
4. Update this README with new test information