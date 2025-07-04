#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Store the script directory for reliable navigation
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if we're in the right directory
if [[ ! -f "Cargo.toml" ]] || [[ ! -d "src" ]]; then
    print_error "Please run this script from the monerosim project directory"
    print_error "Expected files: Cargo.toml, src/ directory"
    exit 1
fi

print_header "MoneroSim Setup Script"
print_status "Setting up MoneroSim from scratch..."

# Step 1: Check system dependencies
print_header "Step 1: Checking System Dependencies"

# Check for required tools
MISSING_DEPS=()

check_command() {
    if ! command -v "$1" &> /dev/null; then
        MISSING_DEPS+=("$1")
        print_warning "$1 is not installed"
        return 1
    else
        print_success "$1 is available"
        return 0
    fi
}

print_status "Checking required system tools..."
check_command "git"
check_command "cmake"
check_command "make"
check_command "gcc"
check_command "g++"
check_command "curl"
check_command "pkg-config"

# Check for Rust
if ! command -v rustc &> /dev/null || ! command -v cargo &> /dev/null; then
    MISSING_DEPS+=("rust")
    print_warning "Rust toolchain is not installed"
else
    RUST_VERSION=$(rustc --version)
    print_success "Rust is available: $RUST_VERSION"
fi

# Check for Shadow
if ! command -v shadow &> /dev/null; then
    MISSING_DEPS+=("shadow")
    print_warning "Shadow simulator is not installed"
else
    SHADOW_VERSION=$(shadow --version 2>&1 | head -n1)
    print_success "Shadow is available: $SHADOW_VERSION"
fi

# Install missing dependencies
if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    print_warning "Missing dependencies: ${MISSING_DEPS[*]}"
    print_status "Attempting to install missing dependencies..."
    
    # Detect package manager
    if command -v apt-get &> /dev/null; then
        PKG_MANAGER="apt-get"
        UPDATE_CMD="sudo apt-get update"
        INSTALL_CMD="sudo apt-get install -y"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
        UPDATE_CMD="sudo yum update"
        INSTALL_CMD="sudo yum install -y"
    elif command -v pacman &> /dev/null; then
        PKG_MANAGER="pacman"
        UPDATE_CMD="sudo pacman -Sy"
        INSTALL_CMD="sudo pacman -S --noconfirm"
    else
        print_error "Could not detect package manager (apt, yum, or pacman)"
        print_error "Please install the following dependencies manually: ${MISSING_DEPS[*]}"
        exit 1
    fi
    
    print_status "Using package manager: $PKG_MANAGER"
    
    # Update package lists
    print_status "Updating package lists..."
    $UPDATE_CMD
    
    # Install basic dependencies
    for dep in "${MISSING_DEPS[@]}"; do
        case $dep in
            "git"|"cmake"|"make"|"curl"|"pkg-config")
                print_status "Installing $dep..."
                $INSTALL_CMD $dep
                ;;
            "gcc"|"g++")
                print_status "Installing build-essential/development tools..."
                if [[ $PKG_MANAGER == "apt-get" ]]; then
                    $INSTALL_CMD build-essential libssl-dev libzmq3-dev libunbound-dev libsodium-dev libunwind8-dev liblzma-dev libreadline6-dev libexpat1-dev libpgm-dev qttools5-dev-tools libhidapi-dev libusb-1.0-0-dev libprotobuf-dev protobuf-compiler libudev-dev libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev libboost-locale-dev libboost-program-options-dev libboost-regex-dev libboost-serialization-dev libboost-system-dev libboost-thread-dev python3 ccache
                elif [[ $PKG_MANAGER == "yum" ]]; then
                    $INSTALL_CMD gcc gcc-c++ make openssl-devel zeromq-devel unbound-devel sodium-devel libunwind-devel xz-devel readline-devel expat-devel pgm-devel qt5-linguist hidapi-devel libusbx-devel protobuf-devel protobuf-compiler systemd-devel boost-devel python3 ccache
                elif [[ $PKG_MANAGER == "pacman" ]]; then
                    $INSTALL_CMD base-devel openssl zeromq unbound sodium libunwind xz readline expat openpgm qt5-tools hidapi libusb protobuf systemd boost python ccache
                fi
                ;;
            "rust")
                print_status "Installing Rust toolchain..."
                curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
                source ~/.cargo/env
                ;;
            "shadow")
                print_warning "Shadow needs to be installed manually from https://shadow.github.io/docs/guide/install/"
                print_warning "Please install Shadow and run this script again"
                exit 1
                ;;
        esac
    done
fi

# Make sure we have Rust in PATH
if [[ -f ~/.cargo/env ]]; then
    source ~/.cargo/env
fi

# Step 2: Build MoneroSim
print_header "Step 2: Building MoneroSim"

print_status "Building MoneroSim with cargo..."
cargo build --release

if [[ $? -eq 0 ]]; then
    print_success "MoneroSim built successfully"
else
    print_error "Failed to build MoneroSim"
    exit 1
fi

# Step 3: Setup Monero Source Code for Shadow Compatibility
print_header "Step 3: Setting Up Monero Source Code"

# Setup directory for Shadow-compatible Monero
MONERO_SHADOW_DIR="../monero-shadow"
MONERO_SHADOW_REPO="https://github.com/YOUR_USERNAME/monero-shadow.git"
SHADOW_BRANCH="shadow-complete"

print_status "Setting up Shadow-compatible Monero source..."

# Try to use local repository first, then fallback to GitHub clone
if [[ -d "../monero-shadow" ]] && [[ -d "../monero-shadow/.git" ]]; then
    print_status "Found local monero-shadow repository"
    
    cd "../monero-shadow"
    
    # Ensure we're on the shadow-complete branch with all modifications
    if git show-ref --verify --quiet refs/heads/$SHADOW_BRANCH; then
        print_status "Switching to $SHADOW_BRANCH branch with all Shadow modifications..."
        git checkout $SHADOW_BRANCH
        print_success "Using $SHADOW_BRANCH branch with:"
        print_success "  • Shadow compatibility patches"
        print_success "  • Seed node disabling functionality"
        print_success "  • Testnet from scratch (quick hard fork activation)"
    else
        print_warning "$SHADOW_BRANCH branch not found, using current branch"
        print_warning "Some Shadow modifications may be missing"
    fi
    
    cd "$SCRIPT_DIR"
    MONERO_SHADOW_DIR="../monero-shadow"
    
else
    print_status "Local monero-shadow repository not found"
    print_status "Attempting to clone from GitHub fork..."
    
    # Remove any existing incomplete directory
    if [[ -d "$MONERO_SHADOW_DIR" ]]; then
        rm -rf "$MONERO_SHADOW_DIR"
    fi
    
    # Clone from GitHub with the comprehensive branch
    git clone --depth 1 --branch $SHADOW_BRANCH "$MONERO_SHADOW_REPO" "$MONERO_SHADOW_DIR"
    
    if [[ $? -eq 0 ]]; then
        print_success "Successfully cloned Shadow-compatible Monero fork"
        print_success "Using $SHADOW_BRANCH branch with all Shadow modifications"
    else
        print_warning "Failed to clone from $SHADOW_BRANCH branch, trying default branch..."
        
        # Try cloning default branch and switching
        git clone --depth 1 "$MONERO_SHADOW_REPO" "$MONERO_SHADOW_DIR"
        
        if [[ $? -eq 0 ]]; then
            cd "$MONERO_SHADOW_DIR"
            
            # Try to switch to shadow-complete branch
            if git show-ref --verify --quiet refs/remotes/origin/$SHADOW_BRANCH; then
                git checkout -b $SHADOW_BRANCH origin/$SHADOW_BRANCH
                print_success "Successfully switched to $SHADOW_BRANCH branch"
            else
                print_error "GitHub repository does not contain $SHADOW_BRANCH branch"
                print_error ""
                print_error "SETUP REQUIRED:"
                print_error "1. Push your local ../monero-shadow repository to GitHub"
                print_error "2. Ensure the $SHADOW_BRANCH branch is pushed"
                print_error "3. Update MONERO_SHADOW_REPO variable in this script"
                print_error "4. Run this setup script again"
                print_error ""
                print_error "Alternatively, set up the local repository at ../monero-shadow"
                exit 1
            fi
            
            # Return to script directory
            cd "$SCRIPT_DIR"
        else
            print_error "Failed to clone Monero repository from GitHub"
            print_error ""
            print_error "Please either:"
            print_error "1. Set up local repository at ../monero-shadow with $SHADOW_BRANCH branch"
            print_error "2. Update MONERO_SHADOW_REPO variable to point to your fork"
            print_error "3. Ensure your GitHub fork contains the $SHADOW_BRANCH branch"
            exit 1
        fi
    fi
fi

# Initialize submodules
print_status "Initializing Monero submodules..."
cd "$MONERO_SHADOW_DIR"
git submodule update --init --recursive

# Return to monerosim directory explicitly
cd "$SCRIPT_DIR"
print_success "Monero source ready for Shadow compatibility"

# Step 4: Build Monero Binaries with MoneroSim
print_header "Step 4: Building Monero Binaries"

print_status "Using MoneroSim to build Shadow-compatible Monero binaries..."
print_status "This will take several minutes (15-30 minutes depending on system)..."

# Ensure we're in the right directory and the binary exists
if [[ ! -f "./target/release/monerosim" ]]; then
    print_error "MoneroSim binary not found at ./target/release/monerosim"
    print_error "Current directory: $(pwd)"
    print_error "Please ensure MoneroSim was built successfully"
    exit 1
fi

# Generate configuration and build Monero
./target/release/monerosim --config config.yaml --output shadow_output

if [[ $? -eq 0 ]]; then
    print_success "MoneroSim configuration generated and Monero built successfully"
else
    print_error "Failed to build Monero with MoneroSim"
    print_error "Check the output above for build errors"
    exit 1
fi

# Verify the binaries were built
MONEROD_BINARIES=()
if [[ -f "builds/A/monero/bin/monerod" ]]; then
    MONEROD_BINARIES+=("builds/A/monero/bin/monerod")
    print_success "Found Monero binary: builds/A/monero/bin/monerod"
elif [[ -f "builds/A/monero/build/Linux/_HEAD_detached_at_v0.18.4.0_/release/bin/monerod" ]]; then
    MONEROD_BINARIES+=("builds/A/monero/build/Linux/_HEAD_detached_at_v0.18.4.0_/release/bin/monerod")
    print_success "Found Monero binary: builds/A/monero/build/Linux/_HEAD_detached_at_v0.18.4.0_/release/bin/monerod"
else
    # Check for other possible locations
    FOUND_BINARY=$(find builds/ -name monerod -type f 2>/dev/null | head -n1)
    if [[ -n "$FOUND_BINARY" ]]; then
        MONEROD_BINARIES+=("$FOUND_BINARY")
        print_success "Found Monero binary: $FOUND_BINARY"
    else
        print_error "No Monero binaries found after build"
        print_error "Build may have failed - check the MoneroSim output above"
        exit 1
    fi
fi

# Step 5: Install Monero binaries to system path
print_header "Step 5: Installing Monero Binaries"

print_status "Installing monerod binaries to /usr/local/bin/ for Shadow compatibility..."

# Check if we have sudo access
if ! sudo -n true 2>/dev/null; then
    print_warning "This script requires sudo access to install binaries to /usr/local/bin/"
    print_status "You will be prompted for your password..."
fi

# Install the first available binary as the default
MAIN_BINARY="${MONEROD_BINARIES[0]}"
print_status "Installing primary binary: $MAIN_BINARY -> /usr/local/bin/monerod"
sudo cp "$MAIN_BINARY" /usr/local/bin/monerod
sudo chmod +x /usr/local/bin/monerod

# Verify the binary works
if /usr/local/bin/monerod --version >/dev/null 2>&1; then
    print_success "Successfully installed monerod to /usr/local/bin/"
else
    print_error "monerod installation may have issues"
fi

# Step 6: Verify Shadow configuration
print_header "Step 6: Verifying Shadow Configuration"

if [[ -f "shadow_output/shadow.yaml" ]]; then
    print_success "Shadow configuration already generated"
else
    print_status "Regenerating Shadow configuration files..."
    
    # Ensure we're in the right directory and the binary exists
    cd "$SCRIPT_DIR"
    if [[ ! -f "./target/release/monerosim" ]]; then
        print_error "MoneroSim binary not found at ./target/release/monerosim"
        print_error "Current directory: $(pwd)"
        print_error "Please ensure MoneroSim was built successfully"
        exit 1
    fi
    
    ./target/release/monerosim --config config.yaml --output shadow_output
    
    if [[ $? -eq 0 ]] && [[ -f "shadow_output/shadow.yaml" ]]; then
        print_success "Shadow configuration generated successfully"
    else
        print_error "Failed to generate Shadow configuration"
        exit 1
    fi
fi

# Step 7: Run test simulation
print_header "Step 7: Running Test Simulation"

print_status "Running a test Shadow simulation (this may take a few minutes)..."
print_status "Simulation will run for the duration specified in config.yaml"

# Clean up any existing shadow data
if [[ -d "shadow.data" ]]; then
    print_status "Cleaning up previous simulation data..."
    rm -rf shadow.data/
fi

# Run the simulation
shadow shadow_output/shadow.yaml

if [[ $? -eq 0 ]]; then
    print_success "Simulation completed successfully!"
    
    # Quick analysis of results
    print_header "Step 8: Basic Results Analysis"
    
    if [[ -d "shadow.data/hosts" ]]; then
        NODE_COUNT=$(ls shadow.data/hosts/ | wc -l)
        print_status "Simulation created $NODE_COUNT node(s)"
        
        # Check for successful RPC initialization
        RPC_SUCCESS=$(grep -r "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout 2>/dev/null | wc -l)
        print_status "Nodes with successful RPC initialization: $RPC_SUCCESS"
        
        # Check for P2P connections
        P2P_CONNECTIONS=$(grep -r "Connected success" shadow.data/hosts/*/monerod.*.stdout 2>/dev/null | wc -l)
        print_status "Successful P2P connections established: $P2P_CONNECTIONS"
        
        if [[ $RPC_SUCCESS -gt 0 ]]; then
            print_success "Monero nodes started successfully!"
        fi
        
        if [[ $P2P_CONNECTIONS -gt 0 ]]; then
            print_success "P2P connections are working!"
        else
            print_warning "No P2P connections detected - this may be expected for short simulations"
        fi
    fi
else
    print_error "Simulation failed"
    print_status "Check shadow.data/shadow.log for details"
    exit 1
fi

# Final success message
print_header "Setup Complete!"
print_success "MoneroSim is now ready to use!"
echo ""
print_status "Quick usage guide:"
echo "  1. Edit config.yaml to adjust simulation parameters"
echo "  2. Generate new configuration: ./target/release/monerosim --config config.yaml --output shadow_output"
echo "  3. Run simulation: shadow shadow_output/shadow.yaml"
echo "  4. Analyze results in shadow.data/ directory"
echo ""
print_status "Configuration files: shadow_output/"
print_status "Simulation logs: shadow.data/hosts/*/monerod.*.stdout"
print_status "Shadow log: shadow.data/shadow.log"
echo ""
print_success "Happy simulating!" 