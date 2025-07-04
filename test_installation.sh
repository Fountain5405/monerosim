#!/bin/bash

# Test script to verify MoneroSim installation
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

FAILED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    print_test "$test_name"
    
    if eval "$test_command" &>/dev/null; then
        print_pass "$test_name"
        return 0
    else
        print_fail "$test_name"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

print_header "MoneroSim Installation Test"

# Test 1: Check if we're in the right directory
run_test "Project directory structure" "[[ -f Cargo.toml && -d src && -f config.yaml ]]"

# Test 2: Check if MoneroSim binary exists
run_test "MoneroSim binary exists" "[[ -f target/release/monerosim ]]"

# Test 3: Check if MoneroSim binary runs
run_test "MoneroSim binary executes" "./target/release/monerosim --help"

# Test 4: Check if monerod is installed
run_test "Monerod binary accessible" "which monerod || [[ -f /usr/local/bin/monerod ]]"

# Test 5: Check if monerod runs
run_test "Monerod version check" "monerod --version || /usr/local/bin/monerod --version"

# Test 6: Check if Shadow is available
run_test "Shadow simulator available" "shadow --version"

# Test 7: Check if Rust toolchain works
run_test "Rust toolchain" "cargo --version"

# Test 8: Test configuration generation
print_test "Configuration generation"
if ./target/release/monerosim --config config.yaml --output test_output &>/dev/null; then
    if [[ -f "test_output/shadow.yaml" ]]; then
        print_pass "Configuration generation"
        rm -rf test_output/
    else
        print_fail "Configuration generation - no output file"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    print_fail "Configuration generation - command failed"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test 9: Validate configuration file
print_test "Configuration file validation"
if [[ -f "config.yaml" ]] && grep -q "stop_time" config.yaml && grep -q "nodes" config.yaml; then
    print_pass "Configuration file validation"
else
    print_fail "Configuration file validation"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Summary
print_header "Test Results"

if [[ $FAILED_TESTS -eq 0 ]]; then
    echo -e "${GREEN}✅ All tests passed! MoneroSim is ready to use.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run a simulation: shadow shadow_output/shadow.yaml"
    echo "  2. Analyze results: ls shadow.data/hosts/"
    echo "  3. Read the README.md for more information"
    exit 0
else
    echo -e "${RED}❌ $FAILED_TESTS test(s) failed. Please check the installation.${NC}"
    echo ""
    echo "Common fixes:"
    echo "  - Run ./setup.sh to reinstall"
    echo "  - Check if you have sudo access"
    echo "  - Verify Shadow is installed from https://shadow.github.io/"
    echo "  - Make sure you're in the monerosim directory"
    exit 1
fi 