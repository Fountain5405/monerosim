#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# MoneroSim installation directory
MONEROSIM_HOME="$HOME/.monerosim"
MONEROSIM_BIN="$MONEROSIM_HOME/bin"

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

# Parse command line arguments
FULL_MONERO_COMPILE=false
CLEAN_START=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --full-monero-compile)
            FULL_MONERO_COMPILE=true
            shift
            ;;
        --clean)
            CLEAN_START=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./setup.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --clean                Remove venv, shadow_output, and target/ before setup"
            echo "                         Use this for a fresh start after failed setup"
            echo "  --full-monero-compile  Build all Monero binaries (slower)"
            echo "                         Default: only build monerod and monero-wallet-rpc"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if we're in the right directory
if [[ ! -f "Cargo.toml" ]] || [[ ! -d "src" ]]; then
    print_error "Please run this script from the monerosim project directory"
    print_error "Expected files: Cargo.toml, src/ directory"
    exit 1
fi

# Clean up previous artifacts if requested
if [[ "$CLEAN_START" == "true" ]]; then
    print_header "Cleaning Previous Setup"
    if [[ -d "$SCRIPT_DIR/venv" ]]; then
        print_status "Removing venv/..."
        rm -rf "$SCRIPT_DIR/venv"
    fi
    if [[ -d "$SCRIPT_DIR/shadow_output" ]]; then
        print_status "Removing shadow_output/..."
        rm -rf "$SCRIPT_DIR/shadow_output"
    fi
    if [[ -d "$SCRIPT_DIR/target" ]]; then
        print_status "Removing target/..."
        rm -rf "$SCRIPT_DIR/target"
    fi
    print_success "Cleanup complete"
fi

print_header "MoneroSim Setup Script"
print_status "Setting up MoneroSim from scratch..."
print_status "Binaries will be installed to: $MONEROSIM_BIN"

# Create the monerosim directories
mkdir -p "$MONEROSIM_BIN"

# Step 1: Check system dependencies
print_header "Step 1: Checking System Dependencies"

# Check for required tools
MISSING_DEPS=()

check_command() {
    if ! command -v "$1" &> /dev/null; then
        MISSING_DEPS+=("$1")
        print_warning "$1 is not installed"
    else
        print_success "$1 is available"
    fi
    # Always return 0 - we track missing deps in MISSING_DEPS array
    return 0
}

print_status "Checking required system tools..."
check_command "git"
check_command "cmake"
check_command "make"
check_command "gcc"
check_command "g++"
check_command "curl"
check_command "pkg-config"

# Minimum required Rust version
MIN_RUST_VERSION="1.82.0"

# Function to compare version strings (returns 0 if $1 >= $2)
version_gte() {
    # Extract just the version numbers and compare
    local ver1=$(echo "$1" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    local ver2="$2"

    if [[ -z "$ver1" ]]; then
        return 1
    fi

    # Use sort -V for version comparison
    local lowest=$(printf '%s\n%s' "$ver1" "$ver2" | sort -V | head -n1)
    [[ "$lowest" == "$ver2" ]]
}

# Check for Rust (handled separately - doesn't need sudo)
NEED_RUST=false
if ! command -v rustc &> /dev/null || ! command -v cargo &> /dev/null; then
    NEED_RUST=true
    print_warning "Rust toolchain is not installed"
else
    RUST_VERSION=$(rustc --version)
    if version_gte "$RUST_VERSION" "$MIN_RUST_VERSION"; then
        print_success "Rust is available: $RUST_VERSION (>= $MIN_RUST_VERSION)"
    else
        NEED_RUST=true
        print_warning "Rust version too old: $RUST_VERSION (need >= $MIN_RUST_VERSION)"
    fi
fi

# Install or update Rust if needed (no sudo required)
if [[ "$NEED_RUST" == "true" ]]; then
    if command -v rustup &> /dev/null; then
        print_status "Updating Rust toolchain via rustup..."
        rustup update stable
    else
        print_status "Installing Rust toolchain (no sudo required)..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    fi
    source ~/.cargo/env

    RUST_VERSION=$(rustc --version 2>/dev/null)
    if [[ -n "$RUST_VERSION" ]] && version_gte "$RUST_VERSION" "$MIN_RUST_VERSION"; then
        print_success "Rust ready: $RUST_VERSION"
    else
        print_error "Failed to install/update Rust to >= $MIN_RUST_VERSION"
        print_error "Current version: $RUST_VERSION"
        exit 1
    fi
fi

# Install system dependencies if any are missing (requires sudo)
if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    print_warning "Missing system dependencies: ${MISSING_DEPS[*]}"
    print_status "Attempting to install missing dependencies (requires sudo)..."

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
            "git"|"cmake"|"make"|"curl"|"pkg-config"|"jq")
                print_status "Installing $dep..."
                $INSTALL_CMD $dep
                ;;
            "gcc"|"g++")
                print_status "Installing build-essential/development tools..."
                if [[ $PKG_MANAGER == "apt-get" ]]; then
                    $INSTALL_CMD build-essential libssl-dev libzmq3-dev libunbound-dev libsodium-dev libunwind8-dev liblzma-dev libreadline6-dev libexpat1-dev libpgm-dev qttools5-dev-tools libhidapi-dev libusb-1.0-0-dev libprotobuf-dev protobuf-compiler libudev-dev libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev libboost-locale-dev libboost-program-options-dev libboost-regex-dev libboost-serialization-dev libboost-system-dev libboost-thread-dev python3 python3-venv ccache
                elif [[ $PKG_MANAGER == "yum" ]]; then
                    $INSTALL_CMD gcc gcc-c++ make openssl-devel zeromq-devel unbound-devel sodium-devel libunwind-devel xz-devel readline-devel expat-devel pgm-devel qt5-linguist hidapi-devel libusbx-devel protobuf-devel protobuf-compiler systemd-devel boost-devel python3 ccache
                elif [[ $PKG_MANAGER == "pacman" ]]; then
                    $INSTALL_CMD base-devel openssl zeromq unbound sodium libunwind xz readline expat openpgm qt5-tools hidapi libusb protobuf systemd boost python ccache
                fi
                ;;
        esac
    done
fi

# Make sure we have Rust and monerosim binaries in PATH
if [[ -f ~/.cargo/env ]]; then
    source ~/.cargo/env
fi

# Add ~/.monerosim/bin to PATH
export PATH="$MONEROSIM_BIN:$PATH"

# Step 2: Install Python dependencies
print_header "Step 2: Installing Python Dependencies"

check_command "python3"

# Check if python3-venv/ensurepip is available (venv module exists but ensurepip may not)
if ! python3 -c "import ensurepip" &>/dev/null; then
    print_warning "python3-venv (ensurepip) is not available"
    print_status "Attempting to install python3-venv (requires sudo)..."

    if command -v apt-get &> /dev/null; then
        # Get the Python version to install the correct venv package
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        print_status "Installing python${PYTHON_VERSION}-venv..."
        sudo apt-get update && sudo apt-get install -y "python${PYTHON_VERSION}-venv"
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3-virtualenv
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm python-virtualenv
    else
        print_error "Could not install python3-venv automatically"
        print_error "Please install it manually and re-run setup.sh"
        exit 1
    fi

    # Verify it worked
    if ! python3 -c "import ensurepip" &>/dev/null; then
        print_error "Failed to install python3-venv"
        exit 1
    fi
    print_success "python3-venv installed successfully"
fi

# Check if we have a valid virtual environment
VENV_DIR="$SCRIPT_DIR/venv"
if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    # Remove incomplete venv if it exists
    if [[ -d "$VENV_DIR" ]]; then
        print_warning "Found incomplete virtual environment, recreating..."
        rm -rf "$VENV_DIR"
    fi
    print_status "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
        print_error "Failed to create Python virtual environment"
        print_error "Please ensure python3-venv is installed and try again"
        exit 1
    fi
fi

# Activate the virtual environment
print_status "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip within the virtual environment
print_status "Upgrading pip..."
pip install --upgrade pip

print_status "Installing Python packages from scripts/requirements.txt..."
if pip install -r scripts/requirements.txt; then
    print_success "Python dependencies installed successfully"
else
    print_error "Failed to install Python dependencies"
    print_error "Please check your pip installation and scripts/requirements.txt"
    exit 1
fi

# Step 3: Build MoneroSim
print_header "Step 3: Building MoneroSim"

print_status "Building MoneroSim with cargo..."
cargo build --release

if [[ $? -eq 0 ]]; then
    print_success "MoneroSim built successfully"
else
    print_error "Failed to build MoneroSim"
    exit 1
fi

# Step 4: Install Shadow Simulator
print_header "Step 4: Installing Shadow Simulator"

# Check for Shadow's build dependencies
SHADOW_DEPS_NEEDED=false

# Check glib-2.0
if ! pkg-config --exists "glib-2.0 >= 2.58" 2>/dev/null; then
    print_warning "glib-2.0 development library not found"
    SHADOW_DEPS_NEEDED=true
fi

# Check clang (required for bindgen)
if ! command -v clang &>/dev/null; then
    print_warning "clang not found (required for Shadow's bindgen)"
    SHADOW_DEPS_NEEDED=true
fi

# Install Shadow dependencies if needed
if [[ "$SHADOW_DEPS_NEEDED" == "true" ]]; then
    print_status "Installing Shadow build dependencies..."

    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y libglib2.0-dev clang libclang-dev
    elif command -v yum &> /dev/null; then
        sudo yum install -y glib2-devel clang clang-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm glib2 clang
    else
        print_error "Could not install Shadow dependencies automatically"
        print_error "Please install libglib2.0-dev, clang, libclang-dev and re-run setup.sh"
        exit 1
    fi

    # Verify
    if ! pkg-config --exists "glib-2.0 >= 2.58" 2>/dev/null; then
        print_error "Failed to install glib-2.0 development library"
        exit 1
    fi
    if ! command -v clang &>/dev/null; then
        print_error "Failed to install clang"
        exit 1
    fi
    print_success "Shadow build dependencies installed"
fi

# Helper function to install shadowformonero
install_shadowformonero() {
    # Setup directory for shadowformonero
    SHADOWFORMONERO_DIR="../shadowformonero"
    SHADOWFORMONERO_REPO="https://github.com/Fountain5405/shadowformonero.git"

    # Clone shadowformonero if not present
    if [[ -d "$SHADOWFORMONERO_DIR" ]] && [[ -d "$SHADOWFORMONERO_DIR/.git" ]]; then
        print_status "Found local shadowformonero repository"
        cd "$SHADOWFORMONERO_DIR"
        git checkout optimize 2>/dev/null || true
        git pull origin optimize
    else
        print_status "Cloning shadowformonero repository..."
        if [[ -d "$SHADOWFORMONERO_DIR" ]]; then
            rm -rf "$SHADOWFORMONERO_DIR"
        fi
        git clone -b optimize "$SHADOWFORMONERO_REPO" "$SHADOWFORMONERO_DIR"
        cd "$SHADOWFORMONERO_DIR"
    fi

    # Install shadowformonero to ~/.monerosim
    print_status "Building and installing shadowformonero to $MONEROSIM_HOME..."
    ./setup build --jobs $(nproc) --prefix "$MONEROSIM_HOME"
    ./setup install

    # Return to script directory
    cd "$SCRIPT_DIR"
}

# Check if Shadow is already installed in our location
if [[ -x "$MONEROSIM_BIN/shadow" ]]; then
    SHADOW_VERSION=$("$MONEROSIM_BIN/shadow" --version 2>&1 | head -n1)
    print_success "Shadow already installed: $SHADOW_VERSION"

    # Check if it's a shadowformonero version (dirty build from optimize branch)
    if "$MONEROSIM_BIN/shadow" --version 2>&1 | grep -qE "dirty|shadowformonero"; then
        print_success "Using shadowformonero version with Monero socket compatibility patches"
    else
        print_warning "Standard Shadow detected - consider reinstalling shadowformonero for vanilla monerod support"
    fi
elif command -v shadow &> /dev/null; then
    # Shadow exists elsewhere - check version and offer to install to our location
    SHADOW_VERSION=$(shadow --version 2>&1 | head -n1)
    print_warning "Shadow found at $(which shadow): $SHADOW_VERSION"
    print_status ""
    print_status "MoneroSim requires shadowformonero installed to $MONEROSIM_BIN"
    print_status ""
    print_status "Choose an option:"
    echo "  y/Y - Install shadowformonero to $MONEROSIM_BIN (recommended)"
    echo "  n/N - Skip (you'll need to ensure shadow is in PATH)"
    echo ""
    read -p "Install shadowformonero? (Y/n): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        print_status "Installing shadowformonero..."
        print_status "This will take 10-20 minutes..."
        install_shadowformonero
    else
        print_warning "Skipping Shadow installation"
        print_warning "Make sure 'shadow' is in your PATH when running simulations"
    fi
else
    print_status "Shadow not found - installing shadowformonero..."
    print_status "This will take 10-20 minutes..."
    install_shadowformonero
fi

# Verify Shadow installation
if [[ -x "$MONEROSIM_BIN/shadow" ]]; then
    SHADOW_VERSION=$("$MONEROSIM_BIN/shadow" --version 2>&1 | head -n1)
    print_success "shadowformonero installed successfully: $SHADOW_VERSION"
elif command -v shadow &> /dev/null; then
    print_success "Shadow available in PATH: $(which shadow)"
else
    print_error "Shadow not found"
    print_error "Please install shadowformonero manually or check your PATH"
    exit 1
fi

# Ensure Shadow libraries are in the correct location
# Shadow binary uses RPATH=$ORIGIN/../lib, so libraries must be in ~/.monerosim/lib/
MONEROSIM_LIB="$MONEROSIM_HOME/lib"
LOCAL_LIB="$HOME/.local/lib"

if [[ -x "$MONEROSIM_BIN/shadow" ]]; then
    print_status "Verifying Shadow library configuration..."
    mkdir -p "$MONEROSIM_LIB"

    # List of required Shadow libraries
    SHADOW_LIBS=(
        "libshadow_injector.so"
        "libshadow_libc.so"
        "libshadow_shim.so"
        "libshadow_openssl_crypto.so"
        "libshadow_openssl_rng.so"
    )

    for lib in "${SHADOW_LIBS[@]}"; do
        if [[ ! -e "$MONEROSIM_LIB/$lib" ]]; then
            # Check if library exists in ~/.local/lib (common alternate location)
            if [[ -e "$LOCAL_LIB/$lib" ]]; then
                print_status "Symlinking $lib from $LOCAL_LIB to $MONEROSIM_LIB"
                ln -sf "$LOCAL_LIB/$lib" "$MONEROSIM_LIB/$lib"
            else
                print_warning "Shadow library not found: $lib"
            fi
        fi
    done

    # Verify shadow can find its libraries
    if "$MONEROSIM_BIN/shadow" --version &>/dev/null; then
        print_success "Shadow libraries configured correctly"
    else
        print_error "Shadow cannot find required libraries"
        print_error "Please check $MONEROSIM_LIB for missing .so files"
    fi
fi

# Step 5: Clone Monero Source Code
print_header "Step 5: Setting Up Monero Source Code"

# Setup directory for Monero
MONERO_DIR="../monero"
MONERO_REPO="https://github.com/monero-project/monero.git"

print_status "Setting up official Monero source..."

# Check if monero directory already exists
if [[ -d "$MONERO_DIR" ]] && [[ -d "$MONERO_DIR/.git" ]]; then
    print_status "Found existing Monero repository"
    cd "$MONERO_DIR"

    # Update to latest
    print_status "Pulling latest changes..."
    git pull origin master || git pull origin main || print_warning "Could not pull latest changes"

    cd "$SCRIPT_DIR"
else
    print_status "Cloning official Monero repository..."
    print_status "This may take a few minutes..."

    # Remove any existing incomplete directory
    if [[ -d "$MONERO_DIR" ]]; then
        rm -rf "$MONERO_DIR"
    fi

    # Clone official Monero repository
    git clone --recursive "$MONERO_REPO" "$MONERO_DIR"

    if [[ $? -ne 0 ]]; then
        print_error "Failed to clone Monero repository"
        print_error "Please check your internet connection and try again"
        exit 1
    fi

    print_success "Successfully cloned official Monero repository"
fi

# Initialize/update submodules
print_status "Initializing Monero submodules..."
cd "$MONERO_DIR"
git submodule update --init --recursive

# Return to monerosim directory explicitly
cd "$SCRIPT_DIR"
print_success "Monero source ready"

# Step 6: Build Monero Binaries
print_header "Step 6: Building Monero Binaries"

# Check for Monero build dependencies
print_status "Checking Monero build dependencies..."
MONERO_DEPS_MISSING=false

# Check key libraries using pkg-config
check_pkg() {
    if ! pkg-config --exists "$1" 2>/dev/null; then
        print_warning "Missing: $1"
        MONERO_DEPS_MISSING=true
    fi
}

check_pkg "libunbound"
check_pkg "libsodium"
check_pkg "libzmq"
check_pkg "openssl"

# Install if needed
if [[ "$MONERO_DEPS_MISSING" == "true" ]]; then
    print_status "Installing Monero build dependencies..."

    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y \
            libssl-dev libzmq3-dev libunbound-dev libsodium-dev \
            libunwind8-dev liblzma-dev libreadline-dev libexpat1-dev \
            libpgm-dev libhidapi-dev libusb-1.0-0-dev \
            libprotobuf-dev protobuf-compiler libudev-dev \
            libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev \
            libboost-locale-dev libboost-program-options-dev libboost-regex-dev \
            libboost-serialization-dev libboost-system-dev libboost-thread-dev
    elif command -v yum &> /dev/null; then
        sudo yum install -y \
            openssl-devel zeromq-devel unbound-devel libsodium-devel \
            libunwind-devel xz-devel readline-devel expat-devel \
            hidapi-devel libusbx-devel protobuf-devel protobuf-compiler \
            systemd-devel boost-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm \
            openssl zeromq unbound libsodium libunwind xz readline expat \
            hidapi libusb protobuf systemd boost
    else
        print_error "Could not install Monero dependencies automatically"
        print_error "Please install libunbound-dev, libsodium-dev, libzmq3-dev, libboost-all-dev"
        exit 1
    fi
    print_success "Monero build dependencies installed"
fi

if [[ "$FULL_MONERO_COMPILE" == "true" ]]; then
    print_status "Building ALL Monero binaries..."
    print_status "This will take 15-30 minutes depending on system..."
else
    print_status "Building Monero binaries (monerod and monero-wallet-rpc only)..."
    print_status "This will take 5-15 minutes depending on system..."
fi

# Navigate to monero directory
cd "$MONERO_DIR"

# Create build directory
mkdir -p build/release
cd build/release

# Configure with CMake
print_status "Configuring Monero build..."
cmake -DCMAKE_BUILD_TYPE=Release ../..

if [[ $? -ne 0 ]]; then
    print_error "Failed to configure Monero with CMake"
    exit 1
fi

# Build Monero binaries
if [[ "$FULL_MONERO_COMPILE" == "true" ]]; then
    print_status "Compiling ALL Monero binaries (--full-monero-compile enabled)..."
    make -j$(nproc)
else
    # Build only the binaries we need (daemon and wallet_rpc_server)
    # This is much faster than building everything
    print_status "Compiling monerod and monero-wallet-rpc only (use --full-monero-compile for all)..."
    make -j$(nproc) daemon wallet_rpc_server
fi

if [[ $? -ne 0 ]]; then
    print_error "Failed to build Monero binaries"
    exit 1
fi

print_success "Monero binaries built successfully"

# Return to script directory
cd "$SCRIPT_DIR"

# Verify the binaries were built
MONEROD_BINARIES=()
if [[ -f "$MONERO_DIR/build/release/bin/monerod" ]]; then
    MONEROD_BINARIES+=("$MONERO_DIR/build/release/bin/monerod")
    print_success "Found Monero binary: $MONERO_DIR/build/release/bin/monerod"
else
    # Check for other possible locations
    FOUND_BINARY=$(find "$MONERO_DIR" -name monerod -type f -executable 2>/dev/null | head -n1)
    if [[ -n "$FOUND_BINARY" ]]; then
        MONEROD_BINARIES+=("$FOUND_BINARY")
        print_success "Found Monero binary: $FOUND_BINARY"
    else
        print_error "No Monero binaries found after build"
        print_error "Build may have failed - check the CMake and make output above"
        exit 1
    fi
fi

# Also check for monero-wallet-rpc binary
MONERO_WALLET_BINARIES=()
if [[ -f "$MONERO_DIR/build/release/bin/monero-wallet-rpc" ]]; then
    MONERO_WALLET_BINARIES+=("$MONERO_DIR/build/release/bin/monero-wallet-rpc")
    print_success "Found Monero wallet binary: $MONERO_DIR/build/release/bin/monero-wallet-rpc"
else
    # Check for other possible locations
    FOUND_WALLET_BINARY=$(find "$MONERO_DIR" -name monero-wallet-rpc -type f -executable 2>/dev/null | head -n1)
    if [[ -n "$FOUND_WALLET_BINARY" ]]; then
        MONERO_WALLET_BINARIES+=("$FOUND_WALLET_BINARY")
        print_success "Found Monero wallet binary: $FOUND_WALLET_BINARY"
    else
        print_warning "No Monero wallet binary found after build"
    fi
fi

# Step 7: Install Monero binaries to ~/.monerosim/bin
print_header "Step 7: Installing Monero Binaries"

print_status "Installing Monero binaries to $MONEROSIM_BIN..."

# Install the monerod binary
MAIN_BINARY="${MONEROD_BINARIES[0]}"
print_status "Installing monerod binary: $MAIN_BINARY -> $MONEROSIM_BIN/monerod"
cp "$MAIN_BINARY" "$MONEROSIM_BIN/monerod"
chmod +x "$MONEROSIM_BIN/monerod"

# Install monero-wallet-rpc if found
if [[ ${#MONERO_WALLET_BINARIES[@]} -gt 0 ]]; then
    MAIN_WALLET_BINARY="${MONERO_WALLET_BINARIES[0]}"
    print_status "Installing monero-wallet-rpc binary: $MAIN_WALLET_BINARY -> $MONEROSIM_BIN/monero-wallet-rpc"
    cp "$MAIN_WALLET_BINARY" "$MONEROSIM_BIN/monero-wallet-rpc"
    chmod +x "$MONEROSIM_BIN/monero-wallet-rpc"
fi

# Verify the binaries work
if "$MONEROSIM_BIN/monerod" --version >/dev/null 2>&1; then
    print_success "Successfully installed monerod to $MONEROSIM_BIN/"
else
    print_error "monerod installation may have issues"
fi

# Verify the wallet binary works if installed
if [[ -f "$MONEROSIM_BIN/monero-wallet-rpc" ]] && "$MONEROSIM_BIN/monero-wallet-rpc" --version >/dev/null 2>&1; then
    print_success "Successfully installed monero-wallet-rpc to $MONEROSIM_BIN/"
else
    print_warning "monero-wallet-rpc installation may have issues"
fi

# Step 8: Setup PATH in shell configuration
print_header "Step 8: Configuring PATH"

# Add to .bashrc if not already present
BASHRC_LINE='export PATH="$HOME/.monerosim/bin:$PATH"'
if ! grep -q '.monerosim/bin' ~/.bashrc 2>/dev/null; then
    print_status "Adding $MONEROSIM_BIN to PATH in ~/.bashrc..."
    echo "" >> ~/.bashrc
    echo "# MoneroSim binaries" >> ~/.bashrc
    echo "$BASHRC_LINE" >> ~/.bashrc
    print_success "PATH updated in ~/.bashrc"
else
    print_success "PATH already configured in ~/.bashrc"
fi

# Also add to .zshrc if it exists
if [[ -f ~/.zshrc ]]; then
    if ! grep -q '.monerosim/bin' ~/.zshrc 2>/dev/null; then
        print_status "Adding $MONEROSIM_BIN to PATH in ~/.zshrc..."
        echo "" >> ~/.zshrc
        echo "# MoneroSim binaries" >> ~/.zshrc
        echo "$BASHRC_LINE" >> ~/.zshrc
        print_success "PATH updated in ~/.zshrc"
    else
        print_success "PATH already configured in ~/.zshrc"
    fi
fi

# Step 9: Generate Shadow configuration
print_header "Step 9: Generating Shadow Configuration"

print_status "Generating Shadow configuration from test_configs/config_32_agents.yaml..."

# Ensure we're in the right directory and the binary exists
cd "$SCRIPT_DIR"
if [[ ! -f "./target/release/monerosim" ]]; then
    print_error "MoneroSim binary not found at ./target/release/monerosim"
    print_error "Current directory: $(pwd)"
    print_error "Please ensure MoneroSim was built successfully"
    exit 1
fi

./target/release/monerosim --config test_configs/config_32_agents.yaml --output shadow_output

if [[ $? -eq 0 ]] && [[ -f "shadow_output/shadow_agents.yaml" ]]; then
    print_success "Shadow configuration generated successfully"
else
    print_error "Failed to generate Shadow configuration"
    exit 1
fi

# Step 10: Optional Test Simulation
print_header "Step 10: Optional Test Simulation"

print_status "Setup is complete! You can now run a test simulation to verify everything works."
print_warning "The test simulation (test_configs/config_32_agents.yaml) runs for approximately 4 hours"
print_warning "This is a comprehensive test with 32 agents and complex network topology"
print_status ""
print_status "Choose an option:"
echo "  y/Y - Run the full test simulation"
echo "  n/N - Skip test simulation and exit setup"
echo ""
read -p "Run test simulation? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Running test simulation..."
    print_status "You can monitor progress with: tail -f shadow.data/shadow.log"
    print_status "Or check agent logs in: shadow.data/hosts/*/"

    # Clean up any existing shadow data
    if [[ -d "shadow.data" ]]; then
        print_status "Cleaning up previous simulation data..."
        rm -rf shadow.data/
    fi

    # Run the simulation (use our shadow binary)
    if [[ -x "$MONEROSIM_BIN/shadow" ]]; then
        "$MONEROSIM_BIN/shadow" shadow_output/shadow_agents.yaml
    else
        shadow shadow_output/shadow_agents.yaml
    fi

    if [[ $? -eq 0 ]]; then
        print_success "Simulation completed successfully!"

        # Quick analysis of results
        print_header "Basic Results Analysis"

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
else
    print_status "Skipping test simulation as requested."
fi

# Final success message
print_header "Setup Complete!"
print_success "MoneroSim is now ready to use!"
echo ""
print_status "Quick usage guide:"
echo "  1. Edit test_configs/config_32_agents.yaml to adjust simulation parameters"
echo "  2. Generate configuration: ./target/release/monerosim --config test_configs/config_32_agents.yaml --output shadow_output"
echo "  3. Run simulation: shadow shadow_output/shadow_agents.yaml"
echo "  4. Analyze results in shadow.data/ directory"
echo ""
print_status "Installed binaries: $MONEROSIM_BIN/"
echo "  - shadow"
echo "  - monerod"
echo "  - monero-wallet-rpc"
echo ""
print_status "Configuration: test_configs/config_32_agents.yaml"
print_status "Simulation logs: shadow.data/hosts/*/monerod.*.stdout"
print_status "Shadow log: shadow.data/shadow.log"
echo ""
print_warning "IMPORTANT: Restart your shell or run 'source ~/.bashrc' to update PATH"
echo ""
print_success "Happy simulating!"
