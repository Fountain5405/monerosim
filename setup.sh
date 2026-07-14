#!/bin/bash

set -euo pipefail

# Colors + shared logging vocabulary
source "$(dirname "${BASH_SOURCE[0]}")/scripts/log_lib.sh"

# MoneroSim installation directory
MONEROSIM_HOME="$HOME/.monerosim"
MONEROSIM_BIN="$MONEROSIM_HOME/bin"

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
            log_err "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if we're in the right directory
if [[ ! -f "Cargo.toml" ]] || [[ ! -d "src" ]]; then
    log_err "Please run this script from the monerosim project directory"
    log_err "Expected files: Cargo.toml, src/ directory"
    exit 1
fi

# Pick a parallel-build job count that won't OOM the C++ compile.
# Monero's heaviest TUs (blockchain.cpp, bulletproofs_plus.cc) can each
# need ~2GB of RAM in cc1plus. Running -j$(nproc) on low-memory machines
# kills the build with "Killed signal terminated program cc1plus".
# Rule: jobs = min(nproc, max(1, ram_gb / 2)).
# Honor a pre-set BUILD_JOBS env var so users can override with
# e.g. BUILD_JOBS=2 ./setup.sh on tight machines.
NPROC=$(nproc)
RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}')
[[ -z "$RAM_GB" || "$RAM_GB" -lt 1 ]] && RAM_GB=2
if [[ -z "${BUILD_JOBS:-}" ]]; then
    RAM_JOBS=$(( RAM_GB / 2 ))
    (( RAM_JOBS < 1 )) && RAM_JOBS=1
    if (( RAM_JOBS < NPROC )); then
        BUILD_JOBS=$RAM_JOBS
    else
        BUILD_JOBS=$NPROC
    fi
fi
export BUILD_JOBS

# Display welcome message and what the script will do
log_header "Welcome to MoneroSim Setup"
echo ""
echo "This script will:"
echo ""
echo -e "  1. ${BLUE}Check system dependencies${NC}"
echo "     - Required: git, cmake, cargo, python3, build-essential, libglib2.0-dev"
echo ""
echo -e "  2. ${BLUE}Build and install binaries${NC} (~30-60 minutes)"
echo "     - shadowformonero (network simulator fork)"
echo "     - monerod (Monero daemon)"
echo "     - monero-wallet-rpc (Monero wallet)"
echo "     - monerosim (Rust config generator)"
echo ""
echo -e "  3. ${BLUE}Set up Python environment${NC}"
echo "     - Create virtual environment"
echo "     - Install Python dependencies"
echo "     - Verify agent imports"
echo ""
echo ""
echo "Total installation size: ~30-50 GB"
echo "Estimated time: 30-60 minutes depending on system"
echo ""
echo -e "${YELLOW}Tip: Consider running this in a screen or tmux session${NC}"
echo -e "     (${YELLOW}screen${NC} or ${YELLOW}tmux${NC}) to prevent terminal buffer issues during long builds"
echo ""

# Ask for confirmation. Drain stdin first so a stray keypress doesn't auto-answer.
read -r -t 0.1 -N 1000 _ 2>/dev/null || true
read -p "Proceed with setup? (Y/n): " -r
if [[ $REPLY =~ ^[Nn]$ ]]; then
    log_info "Setup cancelled."
    exit 0
fi
echo ""

# Clean up previous artifacts if requested
if [[ "$CLEAN_START" == "true" ]]; then
    log_header "Cleaning Previous Setup"
    if [[ -d "$SCRIPT_DIR/venv" ]]; then
        log_info "Removing venv/..."
        rm -rf "$SCRIPT_DIR/venv"
    fi
    if [[ -d "$SCRIPT_DIR/shadow_output" ]]; then
        log_info "Removing shadow_output/..."
        rm -rf "$SCRIPT_DIR/shadow_output"
    fi
    if [[ -d "$SCRIPT_DIR/target" ]]; then
        log_info "Removing target/..."
        rm -rf "$SCRIPT_DIR/target"
    fi
    log_ok "Cleanup complete"
fi

log_header "MoneroSim Setup Script"
log_info "Setting up MoneroSim from scratch..."
log_info "Binaries will be installed to: $MONEROSIM_BIN"

# Create the monerosim directories
mkdir -p "$MONEROSIM_BIN"

# Step 1: Check system dependencies
log_header "Step 1: Checking System Dependencies"

# Check for required tools
MISSING_DEPS=()

check_command() {
    if ! command -v "$1" &> /dev/null; then
        MISSING_DEPS+=("$1")
        log_warn "$1 is not installed"
    else
        log_ok "$1 is available"
    fi
    # Always return 0 - we track missing deps in MISSING_DEPS array
    return 0
}

log_info "Checking required system tools..."
check_command "git"
check_command "cmake"
check_command "make"
check_command "gcc"
check_command "g++"
check_command "curl"
check_command "pkg-config"

# Detect whether the bulk dev-libs install is needed.
# Fix 6: previously only triggered when gcc/g++ were missing — but a user can have
# gcc preinstalled while still missing libssl-dev/libsodium-dev/etc., causing the
# Shadow/Monero compile to fail later with cryptic linker errors. Probe the dev
# headers via pkg-config so we install the bulk list when *any* are missing.
BULK_INSTALL_NEEDED=false
if command -v pkg-config &> /dev/null; then
    # If any core dev headers are missing, force the bulk install.
    if ! pkg-config --exists openssl libsodium libzmq libunbound 2>/dev/null; then
        log_warn "One or more core dev headers (openssl/libsodium/libzmq/libunbound) missing"
        BULK_INSTALL_NEEDED=true
    fi
else
    # pkg-config is itself missing (and thus already in MISSING_DEPS) — we can't
    # probe headers, so be safe and run the bulk install.
    BULK_INSTALL_NEEDED=true
fi

# Boost doesn't expose itself via pkg-config, but we still need to verify the
# component .so files exist — on openSUSE Leap 16 the bulk install is skipped
# silently when other deps are present, leaving Monero's CMake to fail with
# "Could NOT find Boost (missing: filesystem thread date_time ...)" later. Probe
# for libboost_filesystem.so in any of the standard arch-specific lib paths.
if [[ "$BULK_INSTALL_NEEDED" == "false" ]]; then
    if ! ls /usr/lib64/libboost_filesystem.so 2>/dev/null \
        && ! ls /usr/lib/libboost_filesystem.so 2>/dev/null \
        && ! ls /usr/lib/x86_64-linux-gnu/libboost_filesystem.so 2>/dev/null \
        ; then
        # All three lookups silenced; if none returned a path, we need the bulk install.
        if ! find /usr/lib /usr/lib64 -maxdepth 3 -name 'libboost_filesystem.so' 2>/dev/null | grep -q .; then
            log_warn "Boost component libraries (libboost_filesystem.so) not found — bulk install will run"
            BULK_INSTALL_NEEDED=true
        fi
    fi
fi

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
    log_warn "Rust toolchain is not installed"
else
    RUST_VERSION=$(rustc --version)
    if version_gte "$RUST_VERSION" "$MIN_RUST_VERSION"; then
        log_ok "Rust is available: $RUST_VERSION (>= $MIN_RUST_VERSION)"
    else
        NEED_RUST=true
        log_warn "Rust version too old: $RUST_VERSION (need >= $MIN_RUST_VERSION)"
    fi
fi

# Install or update Rust if needed (no sudo required)
if [[ "$NEED_RUST" == "true" ]]; then
    if command -v rustup &> /dev/null; then
        log_info "Updating Rust toolchain via rustup..."
        rustup update stable
    else
        log_info "Installing Rust toolchain (no sudo required)..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    fi
    source ~/.cargo/env

    RUST_VERSION=$(rustc --version 2>/dev/null)
    if [[ -n "$RUST_VERSION" ]] && version_gte "$RUST_VERSION" "$MIN_RUST_VERSION"; then
        log_ok "Rust ready: $RUST_VERSION"
    else
        log_err "Failed to install/update Rust to >= $MIN_RUST_VERSION"
        log_err "Current version: $RUST_VERSION"
        exit 1
    fi
fi

# Install system dependencies if any are missing (requires sudo).
# Fix 6: also enter this branch when BULK_INSTALL_NEEDED=true even if MISSING_DEPS
# is empty — handles the "gcc present, dev headers missing" case.
if [[ ${#MISSING_DEPS[@]} -gt 0 || "$BULK_INSTALL_NEEDED" == "true" ]]; then
    if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
        log_warn "Missing system dependencies: ${MISSING_DEPS[*]}"
    fi
    if [[ "$BULK_INSTALL_NEEDED" == "true" ]]; then
        log_warn "Bulk dev-libs install needed (missing pkg-config-detectable dev headers)"
    fi
    log_info "Attempting to install missing dependencies (requires sudo)..."

    # Detect package manager
    # Note: dnf is checked before yum because on modern RHEL/Fedora both may
    # exist (yum is often a symlink to dnf); we want to prefer the modern tool.
    if command -v apt-get &> /dev/null; then
        PKG_MANAGER="apt-get"
        UPDATE_CMD="sudo apt-get update"
        INSTALL_CMD="sudo apt-get install -y"
    elif command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
        UPDATE_CMD="sudo dnf makecache"
        INSTALL_CMD="sudo dnf install -y"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
        # `yum update` upgrades all installed packages; `yum makecache` is the
        # actual equivalent of `apt-get update` (cache refresh only).
        UPDATE_CMD="sudo yum makecache"
        INSTALL_CMD="sudo yum install -y"
    elif command -v pacman &> /dev/null; then
        PKG_MANAGER="pacman"
        UPDATE_CMD="sudo pacman -Sy"
        INSTALL_CMD="sudo pacman -S --noconfirm"
    elif command -v zypper &> /dev/null; then
        PKG_MANAGER="zypper"
        UPDATE_CMD="sudo zypper refresh"
        INSTALL_CMD="sudo zypper install -y --no-recommends"
    else
        log_err "Could not detect package manager (apt-get, dnf, yum, pacman, or zypper)"
        log_err "Please install the following dependencies manually: ${MISSING_DEPS[*]}"
        exit 1
    fi

    log_info "Using package manager: $PKG_MANAGER"

    # RHEL family (RHEL/CentOS/Rocky/Alma) splits dev headers across the default
    # repos plus EPEL (Extra Packages for Enterprise Linux) and CRB / PowerTools
    # (CodeReady Builder). Enable both before the cache refresh, otherwise
    # libsodium-devel, libunwind-devel, zeromq-devel, openpgm-devel, protobuf-devel,
    # ccache, etc. won't be findable. Fedora ships these in its main repos and is
    # skipped here. CRB is the modern repo name (EL9+); PowerTools is the EL8 name.
    if [[ "$PKG_MANAGER" == "dnf" || "$PKG_MANAGER" == "yum" ]] && [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        case "$ID" in
            rhel|centos|rocky|almalinux)
                log_info "Enabling EPEL and CRB/PowerTools for RHEL-family Monero deps..."
                $INSTALL_CMD dnf-plugins-core epel-release || true
                sudo dnf config-manager --set-enabled crb 2>/dev/null \
                    || sudo dnf config-manager --enable crb 2>/dev/null \
                    || sudo dnf config-manager --set-enabled powertools 2>/dev/null \
                    || sudo dnf config-manager --enable powertools 2>/dev/null \
                    || true
                ;;
        esac
    fi

    # Update package lists
    log_info "Updating package lists..."
    $UPDATE_CMD

    # Install single-package dependencies via the per-dep loop.
    # The bulk dev-libs install is handled separately below (see Fix 6).
    BULK_TRIGGERED=false
    for dep in "${MISSING_DEPS[@]}"; do
        case $dep in
            "git"|"cmake"|"make"|"curl"|"pkg-config"|"jq")
                log_info "Installing $dep..."
                $INSTALL_CMD $dep
                ;;
            "gcc"|"g++")
                # Defer to the bulk install below — it includes the compilers.
                BULK_TRIGGERED=true
                ;;
        esac
    done

    # Fix 6: install the full bulk dev-libs list when either (a) gcc/g++ were
    # in MISSING_DEPS, or (b) pkg-config probing detected missing dev headers.
    # This prevents the prior bug where a user with gcc preinstalled but missing
    # libssl-dev/libsodium-dev/etc. would silently skip the bulk install and hit
    # cryptic linker errors during the Shadow/Monero compile.
    if [[ "$BULK_TRIGGERED" == "true" || "$BULK_INSTALL_NEEDED" == "true" ]]; then
        log_info "Installing build-essential/development tools..."
        if [[ $PKG_MANAGER == "apt-get" ]]; then
            $INSTALL_CMD build-essential libssl-dev libzmq3-dev libunbound-dev libsodium-dev libunwind8-dev liblzma-dev libreadline6-dev libexpat1-dev libpgm-dev qttools5-dev-tools libhidapi-dev libusb-1.0-0-dev libprotobuf-dev protobuf-compiler libudev-dev libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev libboost-locale-dev libboost-program-options-dev libboost-regex-dev libboost-serialization-dev libboost-system-dev libboost-thread-dev python3 python3-venv ccache
        elif [[ $PKG_MANAGER == "yum" || $PKG_MANAGER == "dnf" ]]; then
            # EPEL + CRB/PowerTools enabled above (for RHEL-family) so that
            # libsodium-devel, libunwind-devel, zeromq-devel, openpgm-devel,
            # protobuf-devel, ccache, etc. resolve. On Fedora these are in the
            # main repos and the EPEL/CRB block is a no-op.
            # NOTE: qt5-linguist removed — Qt5 is deprecated on EL10 (Rocky 10 /
            # CentOS Stream 10) and the headless monerod + monero-wallet-rpc
            # build does not need it. Re-add as a separate `|| true` install
            # only if --full-monero-compile reveals a hard requirement.
            # NOTE: libusbx-devel may be libusb1-devel on newer Fedora/EL9+;
            # adjust per distro version if installation fails.
            $INSTALL_CMD gcc gcc-c++ make openssl-devel zeromq-devel unbound-devel libsodium-devel libunwind-devel xz-devel readline-devel expat-devel openpgm-devel hidapi-devel libusbx-devel protobuf-devel protobuf-compiler systemd-devel boost-devel python3 ccache
        elif [[ $PKG_MANAGER == "pacman" ]]; then
            $INSTALL_CMD base-devel openssl zeromq unbound libsodium libunwind xz readline expat openpgm qt5-tools hidapi libusb protobuf systemd boost python ccache
        elif [[ $PKG_MANAGER == "zypper" ]]; then
            # NOTE: openSUSE splits Boost into per-component -devel packages.
            # `boost-devel` alone gives headers + version probe but not the
            # individual libboost_filesystem/thread/etc. .so files that
            # Monero's CMake `find_package(Boost COMPONENTS ...)` looks up.
            # Without these, CMake fails with "Could NOT find Boost (missing:
            # filesystem thread date_time chrono serialization program_options)"
            # even though the version probe succeeds. Verified on Leap 16.
            # NOTE: qt5-linguist dropped — Qt5 deprecated on Leap 16 and not
            # needed for the headless monerod + monero-wallet-rpc build.
            # NOTE: if the unversioned libboost_*-devel names don't resolve
            # on a given Leap version, the versioned form is e.g.
            # libboost_filesystem1_86_0-devel. Run `zypper search libboost_<comp>`
            # to find what's actually available.
            $INSTALL_CMD gcc gcc-c++ make libopenssl-devel zeromq-devel unbound-devel libsodium-devel libunwind-devel xz-devel readline-devel libexpat-devel openpgm-devel libhidapi-devel libusb-1_0-devel libprotobuf-devel protobuf-devel libudev-devel python3 ccache \
                libboost_filesystem-devel libboost_thread-devel libboost_date_time-devel libboost_chrono-devel libboost_serialization-devel libboost_program_options-devel libboost_regex-devel libboost_system-devel libboost_locale-devel
        fi
    fi
fi

# Make sure we have Rust and monerosim binaries in PATH
if [[ -f ~/.cargo/env ]]; then
    source ~/.cargo/env
fi

# Add ~/.monerosim/bin to PATH for this setup session only
export PATH="$MONEROSIM_BIN:$PATH"

# Step 2: Install Python dependencies
log_header "Step 2: Installing Python Dependencies"

check_command "python3"

# Find a Python interpreter >= 3.10. The default `python3` is too old on
# RHEL/Rocky/Alma 9 (ships 3.9), so probe versioned binaries too. If none is
# found and we're on EL8/EL9, try installing python3.11 from AppStream.
find_python_310plus() {
    local cand
    for cand in python3 python3.13 python3.12 python3.11 python3.10; do
        if command -v "$cand" >/dev/null 2>&1 \
            && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

PYTHON_BIN=$(find_python_310plus || true)
if [[ -z "$PYTHON_BIN" ]] && [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    case "${ID:-}:${VERSION_ID:-}" in
        rhel:[89]*|centos:[89]*|rocky:[89]*|almalinux:[89]*)
            log_warn "System python3 is older than 3.10 (default on EL${VERSION_ID%%.*})."
            log_info "Installing python3.11 from AppStream..."
            if command -v dnf &>/dev/null; then
                sudo dnf install -y python3.11 || true
            elif command -v yum &>/dev/null; then
                sudo yum install -y python3.11 || true
            fi
            PYTHON_BIN=$(find_python_310plus || true)
            ;;
    esac
fi

if [[ -z "$PYTHON_BIN" ]]; then
    log_err "Python 3.10+ is required but no usable interpreter was found."
    log_err "Tried: python3, python3.13, python3.12, python3.11, python3.10."
    log_err "Install one for your distro, e.g.:"
    log_err "  Debian/Ubuntu: sudo apt install python3.11"
    log_err "  Rocky/Alma 9:  sudo dnf install python3.11"
    log_err "  Fedora:        default python3 is already >= 3.10 (reinstall if missing)"
    log_err "  Arch:          sudo pacman -S python"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log_info "Python version check passed: $PYTHON_VERSION (using $PYTHON_BIN)"

# Check if python3-venv/ensurepip is available (venv module exists but ensurepip may not)
if ! "$PYTHON_BIN" -c "import ensurepip" &>/dev/null; then
    log_warn "$PYTHON_BIN venv (ensurepip) is not available"
    log_info "Attempting to install the venv module (requires sudo)..."

    if command -v apt-get &> /dev/null; then
        # On Debian/Ubuntu the package name is e.g. python3.11-venv.
        log_info "Installing ${PYTHON_BIN}-venv..."
        sudo apt-get update && sudo apt-get install -y "${PYTHON_BIN}-venv"
    elif command -v dnf &> /dev/null; then
        log_err "On RHEL/Fedora, the venv module ships with the main python3 package;"
        log_err "if ensurepip is missing, try reinstalling python3 (e.g. \`sudo dnf reinstall python3\`)"
        exit 1
    elif command -v yum &> /dev/null; then
        log_err "On RHEL/CentOS, the venv module ships with the main python3 package;"
        log_err "if ensurepip is missing, try reinstalling python3 (e.g. \`sudo yum reinstall python3\`)"
        exit 1
    elif command -v pacman &> /dev/null; then
        log_err "On Arch, the venv module ships with the main python package;"
        log_err "if ensurepip is missing, try reinstalling python (e.g. \`sudo pacman -S python\`)"
        exit 1
    elif command -v zypper &> /dev/null; then
        log_err "On openSUSE, the venv module ships with the main python3 package;"
        log_err "if ensurepip is missing, try reinstalling python3 (e.g. \`sudo zypper install -f python3\`)"
        exit 1
    else
        log_err "Could not install python3-venv automatically"
        log_err "Please install it manually and re-run setup.sh"
        exit 1
    fi

    # Verify it worked
    if ! "$PYTHON_BIN" -c "import ensurepip" &>/dev/null; then
        log_err "Failed to install the venv module for $PYTHON_BIN"
        exit 1
    fi
    log_ok "venv module for $PYTHON_BIN installed successfully"
fi

# Check if we have a valid virtual environment
VENV_DIR="$SCRIPT_DIR/venv"
if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    # Remove incomplete venv if it exists
    if [[ -d "$VENV_DIR" ]]; then
        log_warn "Found incomplete virtual environment, recreating..."
        rm -rf "$VENV_DIR"
    fi
    log_info "Creating Python virtual environment with $PYTHON_BIN..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
        log_err "Failed to create Python virtual environment"
        log_err "Please ensure python3-venv is installed and try again"
        exit 1
    fi
fi

# Activate the virtual environment
log_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip within the virtual environment
log_info "Upgrading pip..."
pip install --upgrade pip

log_info "Installing Python packages from scripts/requirements.txt..."
if pip install -r scripts/requirements.txt; then
    log_ok "Python dependencies installed successfully"
else
    log_err "Failed to install Python dependencies"
    log_err "Please check your pip installation and scripts/requirements.txt"
    exit 1
fi

# Step 3: Build MoneroSim
log_header "Step 3: Building MoneroSim"

log_info "Building MoneroSim with cargo..."
cargo build --release

if [[ $? -eq 0 ]]; then
    log_ok "MoneroSim built successfully"
else
    log_err "Failed to build MoneroSim"
    exit 1
fi

# Step 4: Install Shadow Simulator
log_header "Step 4: Installing Shadow Simulator"

# Check for Shadow's build dependencies
SHADOW_DEPS_NEEDED=false

# Check glib-2.0
if ! pkg-config --exists "glib-2.0 >= 2.58" 2>/dev/null; then
    log_warn "glib-2.0 development library not found"
    SHADOW_DEPS_NEEDED=true
fi

# Check clang (required for bindgen)
if ! command -v clang &>/dev/null; then
    log_warn "clang not found (required for Shadow's bindgen)"
    SHADOW_DEPS_NEEDED=true
fi

# Install Shadow dependencies if needed
if [[ "$SHADOW_DEPS_NEEDED" == "true" ]]; then
    log_info "Installing Shadow build dependencies..."

    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y libglib2.0-dev clang libclang-dev
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y glib2-devel clang clang-devel pkgconfig
    elif command -v yum &> /dev/null; then
        sudo yum install -y glib2-devel clang clang-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm glib2 clang
    elif command -v zypper &> /dev/null; then
        sudo zypper install -y --no-recommends glib2-devel clang clang-devel pkg-config
    else
        log_err "Could not install Shadow dependencies automatically"
        log_err "Please install libglib2.0-dev, clang, libclang-dev and re-run setup.sh"
        exit 1
    fi

    # Verify
    if ! pkg-config --exists "glib-2.0 >= 2.58" 2>/dev/null; then
        log_err "Failed to install glib-2.0 development library"
        exit 1
    fi
    if ! command -v clang &>/dev/null; then
        log_err "Failed to install clang"
        exit 1
    fi
    log_ok "Shadow build dependencies installed"
fi

# Pin shadowformonero to the tag matching this monerosim release.
# Bump in lock-step with monerosim's own tag so a given monerosim
# version always installs the exact fork commit it was tested against.
# install_shadowformonero() stamps this into
# $MONEROSIM_HOME/SHADOWFORMONERO_VERSION so subsequent runs can detect
# a stale install and prompt for reinstall.
SHADOWFORMONERO_REF="v0.1.0"

# Helper function to install shadowformonero
install_shadowformonero() {
    # Setup directory for shadowformonero
    SHADOWFORMONERO_DIR="$SCRIPT_DIR/sibling_repos/shadowformonero"
    SHADOWFORMONERO_REPO="https://github.com/Fountain5405/shadowformonero.git"

    mkdir -p "$SCRIPT_DIR/sibling_repos"

    # Clone shadowformonero if not present
    if [[ -d "$SHADOWFORMONERO_DIR" ]] && [[ -d "$SHADOWFORMONERO_DIR/.git" ]]; then
        log_info "Found local shadowformonero repository; syncing to $SHADOWFORMONERO_REF"
        cd "$SHADOWFORMONERO_DIR"
        git fetch origin --tags
        git checkout "$SHADOWFORMONERO_REF"
    else
        log_info "Cloning shadowformonero repository (pinned to $SHADOWFORMONERO_REF)..."
        if [[ -d "$SHADOWFORMONERO_DIR" ]]; then
            rm -rf "$SHADOWFORMONERO_DIR"
        fi
        # --branch accepts tags; --depth keeps the clone small since the
        # full upstream Shadow history is heavy and we only build one ref.
        git clone --branch "$SHADOWFORMONERO_REF" --depth 1 \
            "$SHADOWFORMONERO_REPO" "$SHADOWFORMONERO_DIR"
        cd "$SHADOWFORMONERO_DIR"
    fi

    # Install shadowformonero to ~/.monerosim
    log_info "Building and installing shadowformonero to $MONEROSIM_HOME (using -j${BUILD_JOBS}, capped by RAM=${RAM_GB}GB)..."
    ./setup build --jobs "$BUILD_JOBS" --prefix "$MONEROSIM_HOME"
    ./setup install

    # Stamp the installed ref so future runs can detect a stale install.
    echo "$SHADOWFORMONERO_REF" > "$MONEROSIM_HOME/SHADOWFORMONERO_VERSION"

    # Return to script directory
    cd "$SCRIPT_DIR"
}

# Check if Shadow is already installed in our location
if [[ -x "$MONEROSIM_BIN/shadow" ]]; then
    SHADOW_VERSION=$("$MONEROSIM_BIN/shadow" --version 2>&1 | head -n1)
    log_ok "Shadow already installed: $SHADOW_VERSION"

    # Decide whether the install matches what this monerosim release
    # expects. Three cases warrant a reinstall prompt:
    #   1. Binary is stock Shadow, not shadowformonero (missing patches)
    #   2. shadowformonero is installed but the stamp file is missing
    #      (pre-versioning install — can't verify the ref it was built from)
    #   3. shadowformonero is installed but the stamp differs from the
    #      pinned $SHADOWFORMONERO_REF for this monerosim release
    STAMP_FILE="$MONEROSIM_HOME/SHADOWFORMONERO_VERSION"
    REINSTALL_REASON=""
    if ! "$MONEROSIM_BIN/shadow" --version 2>&1 | grep -qE "dirty|shadowformonero"; then
        REINSTALL_REASON="installed binary is stock Shadow, not shadowformonero — it lacks the Monero socket-compatibility patches"
    elif [[ ! -f "$STAMP_FILE" ]]; then
        REINSTALL_REASON="installed shadowformonero predates version stamping; cannot verify it matches the pinned ref ($SHADOWFORMONERO_REF)"
    else
        INSTALLED_REF=$(cat "$STAMP_FILE")
        if [[ "$INSTALLED_REF" != "$SHADOWFORMONERO_REF" ]]; then
            REINSTALL_REASON="installed shadowformonero is $INSTALLED_REF; this monerosim release expects $SHADOWFORMONERO_REF"
        else
            log_ok "shadowformonero $INSTALLED_REF matches pinned ref"
        fi
    fi

    if [[ -n "$REINSTALL_REASON" ]]; then
        log_warn ""
        log_warn "shadowformonero install needs attention:"
        log_warn "  $REINSTALL_REASON"
        log_warn ""
        log_warn "Reinstalling will rebuild from source and takes 10-20 minutes."
        # Drain stdin so a stray keypress during earlier phases doesn't auto-answer.
        read -r -t 0.1 -N 1000 _ 2>/dev/null || true
        read -p "Reinstall shadowformonero now? (Y/n): " -r
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            log_info "Reinstalling shadowformonero..."
            install_shadowformonero
        else
            log_warn "Keeping existing shadowformonero install. Simulations may fail or behave unexpectedly."
        fi
    fi
elif command -v shadow &> /dev/null; then
    # Shadow exists elsewhere - check version and offer to install to our location
    SHADOW_VERSION=$(shadow --version 2>&1 | head -n1)
    log_warn "Shadow found at $(which shadow): $SHADOW_VERSION"
    log_info ""
    log_info "MoneroSim requires shadowformonero installed to $MONEROSIM_BIN"
    log_info ""
    log_info "Choose an option:"
    echo "  y/Y - Install shadowformonero to $MONEROSIM_BIN (recommended)"
    echo "  n/N - Skip (you'll need shadow installed at ~/.monerosim/bin/shadow)"
    echo ""
    # Drain stdin so a stray keypress during the previous build phases doesn't auto-answer.
    read -r -t 0.1 -N 1000 _ 2>/dev/null || true
    read -p "Install shadowformonero? (Y/n): " -r

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        log_info "Installing shadowformonero..."
        log_info "This will take 10-20 minutes..."
        install_shadowformonero
    else
        log_warn "Skipping Shadow installation"
        log_warn "Make sure shadow is installed at ~/.monerosim/bin/shadow"
    fi
else
    log_info "Shadow not found - installing shadowformonero..."
    log_info "This will take 10-20 minutes..."
    install_shadowformonero
fi

# Verify Shadow installation
if [[ -x "$MONEROSIM_BIN/shadow" ]]; then
    SHADOW_VERSION=$("$MONEROSIM_BIN/shadow" --version 2>&1 | head -n1)
    log_ok "shadowformonero installed successfully: $SHADOW_VERSION"
elif command -v shadow &> /dev/null; then
    log_ok "Shadow available in PATH: $(which shadow)"
else
    log_err "Shadow not found"
    log_err "Please install shadowformonero manually to ~/.monerosim/bin/"
    exit 1
fi

# Ensure Shadow libraries are in the correct location
# Shadow binary uses RPATH=$ORIGIN/../lib, so libraries must be in ~/.monerosim/lib/
MONEROSIM_LIB="$MONEROSIM_HOME/lib"
LOCAL_LIB="$HOME/.local/lib"

if [[ -x "$MONEROSIM_BIN/shadow" ]]; then
    log_info "Verifying Shadow library configuration..."
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
                log_info "Symlinking $lib from $LOCAL_LIB to $MONEROSIM_LIB"
                ln -sf "$LOCAL_LIB/$lib" "$MONEROSIM_LIB/$lib"
            else
                log_warn "Shadow library not found: $lib"
            fi
        fi
    done

    # Verify shadow can find its libraries
    if "$MONEROSIM_BIN/shadow" --version &>/dev/null; then
        log_ok "Shadow libraries configured correctly"
    else
        log_err "Shadow cannot find required libraries"
        log_err "Please check $MONEROSIM_LIB for missing .so files"
    fi
fi

# Step 5: Clone Monero Source Code
log_header "Step 5: Setting Up Monero Source Code"

# Setup directory for Monero
MONERO_DIR="$SCRIPT_DIR/sibling_repos/monero"
MONERO_REPO="https://github.com/monero-project/monero.git"

mkdir -p "$SCRIPT_DIR/sibling_repos"

log_info "Setting up official Monero source..."

# Check if monero directory already exists
if [[ -d "$MONERO_DIR" ]] && [[ -d "$MONERO_DIR/.git" ]]; then
    log_info "Found existing Monero repository"
    cd "$MONERO_DIR"

    # Update to latest
    log_info "Pulling latest changes..."
    git pull origin master || git pull origin main || log_warn "Could not pull latest changes"

    cd "$SCRIPT_DIR"
else
    log_info "Cloning official Monero repository..."
    log_info "This may take a few minutes..."

    # Remove any existing incomplete directory
    if [[ -d "$MONERO_DIR" ]]; then
        rm -rf "$MONERO_DIR"
    fi

    # Clone official Monero repository
    git clone --recursive "$MONERO_REPO" "$MONERO_DIR"

    if [[ $? -ne 0 ]]; then
        log_err "Failed to clone Monero repository"
        log_err "Please check your internet connection and try again"
        exit 1
    fi

    log_ok "Successfully cloned official Monero repository"
fi

# Initialize/update submodules
log_info "Initializing Monero submodules..."
cd "$MONERO_DIR"
git submodule update --init --recursive

# Return to monerosim directory explicitly
cd "$SCRIPT_DIR"
log_ok "Monero source ready"

# Step 6: Build Monero Binaries
log_header "Step 6: Building Monero Binaries"

# Check for Monero build dependencies
log_info "Checking Monero build dependencies..."
MONERO_DEPS_MISSING=false

# Check key libraries using pkg-config
check_pkg() {
    if ! pkg-config --exists "$1" 2>/dev/null; then
        log_warn "Missing: $1"
        MONERO_DEPS_MISSING=true
    fi
}

check_pkg "libunbound"
check_pkg "libsodium"
check_pkg "libzmq"
check_pkg "openssl"

# Install if needed
if [[ "$MONERO_DEPS_MISSING" == "true" ]]; then
    log_info "Installing Monero build dependencies..."

    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y \
            libssl-dev libzmq3-dev libunbound-dev libsodium-dev \
            libunwind8-dev liblzma-dev libreadline-dev libexpat1-dev \
            libpgm-dev libhidapi-dev libusb-1.0-0-dev \
            libprotobuf-dev protobuf-compiler libudev-dev \
            libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev \
            libboost-locale-dev libboost-program-options-dev libboost-regex-dev \
            libboost-serialization-dev libboost-system-dev libboost-thread-dev
    elif command -v dnf &> /dev/null; then
        # NOTE: openpgm-devel is in EPEL on RHEL/Rocky/Alma (enable EPEL first);
        # in main repos on Fedora.
        # NOTE: libusbx-devel name varies by RHEL version (EL7 vs EL8/9/Fedora).
        sudo dnf install -y \
            openssl-devel zeromq-devel unbound-devel libsodium-devel \
            libunwind-devel xz-devel readline-devel expat-devel \
            openpgm-devel hidapi-devel libusbx-devel protobuf-devel protobuf-compiler \
            systemd-devel boost-devel
    elif command -v yum &> /dev/null; then
        # NOTE: openpgm-devel is in EPEL on RHEL/Rocky/Alma (enable EPEL first).
        # NOTE: libusbx-devel name varies by RHEL version (EL7 vs EL8/9/Fedora).
        sudo yum install -y \
            openssl-devel zeromq-devel unbound-devel libsodium-devel \
            libunwind-devel xz-devel readline-devel expat-devel \
            openpgm-devel hidapi-devel libusbx-devel protobuf-devel protobuf-compiler \
            systemd-devel boost-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm \
            openssl zeromq unbound libsodium libunwind xz readline expat \
            hidapi libusb protobuf systemd boost
    elif command -v zypper &> /dev/null; then
        # TODO: verify on openSUSE Leap — package splits/names may differ
        # (e.g. libusb-1_0-devel vs libusb-1.0-devel, libexpat-devel vs expat-devel).
        sudo zypper install -y --no-recommends \
            libopenssl-devel zeromq-devel unbound-devel libsodium-devel \
            libunwind-devel xz-devel readline-devel libexpat-devel \
            libhidapi-devel libusb-1_0-devel libprotobuf-devel protobuf-devel \
            libudev-devel boost-devel
    else
        log_err "Could not install Monero dependencies automatically"
        log_err "Please install libunbound-dev, libsodium-dev, libzmq3-dev, libboost-all-dev"
        exit 1
    fi
    log_ok "Monero build dependencies installed"
fi

if [[ "$FULL_MONERO_COMPILE" == "true" ]]; then
    log_info "Building ALL Monero binaries..."
    log_info "This will take 15-30 minutes depending on system..."
else
    log_info "Building Monero binaries (monerod and monero-wallet-rpc only)..."
    log_info "This will take 5-15 minutes depending on system..."
fi

# Navigate to monero directory
cd "$MONERO_DIR"

# Create build directory
mkdir -p build/release
cd build/release

# Configure with CMake
log_info "Configuring Monero build..."
cmake -DCMAKE_BUILD_TYPE=Release ../..

if [[ $? -ne 0 ]]; then
    log_err "Failed to configure Monero with CMake"
    exit 1
fi

# Build Monero binaries
# Use BUILD_JOBS (RAM-capped) instead of $(nproc) to avoid OOM-killing
# cc1plus on low-memory machines. blockchain.cpp + bulletproofs_plus.cc
# can each peak at ~2GB during compile.
if [[ "$FULL_MONERO_COMPILE" == "true" ]]; then
    log_info "Compiling ALL Monero binaries (--full-monero-compile enabled, -j${BUILD_JOBS})..."
    make -j"$BUILD_JOBS"
else
    # Build only the binaries we need (daemon and wallet_rpc_server)
    # This is much faster than building everything
    log_info "Compiling monerod and monero-wallet-rpc only (use --full-monero-compile for all, -j${BUILD_JOBS})..."
    make -j"$BUILD_JOBS" daemon wallet_rpc_server
fi

if [[ $? -ne 0 ]]; then
    log_err "Failed to build Monero binaries"
    exit 1
fi

log_ok "Monero binaries built successfully"

# Return to script directory
cd "$SCRIPT_DIR"

# Verify the binaries were built
MONEROD_BINARIES=()
if [[ -f "$MONERO_DIR/build/release/bin/monerod" ]]; then
    MONEROD_BINARIES+=("$MONERO_DIR/build/release/bin/monerod")
    log_ok "Found Monero binary: $MONERO_DIR/build/release/bin/monerod"
else
    # Check for other possible locations
    FOUND_BINARY=$(find "$MONERO_DIR" -name monerod -type f -executable 2>/dev/null | head -n1)
    if [[ -n "$FOUND_BINARY" ]]; then
        MONEROD_BINARIES+=("$FOUND_BINARY")
        log_ok "Found Monero binary: $FOUND_BINARY"
    else
        log_err "No Monero binaries found after build"
        log_err "Build may have failed - check the CMake and make output above"
        exit 1
    fi
fi

# Also check for monero-wallet-rpc binary
MONERO_WALLET_BINARIES=()
if [[ -f "$MONERO_DIR/build/release/bin/monero-wallet-rpc" ]]; then
    MONERO_WALLET_BINARIES+=("$MONERO_DIR/build/release/bin/monero-wallet-rpc")
    log_ok "Found Monero wallet binary: $MONERO_DIR/build/release/bin/monero-wallet-rpc"
else
    # Check for other possible locations
    FOUND_WALLET_BINARY=$(find "$MONERO_DIR" -name monero-wallet-rpc -type f -executable 2>/dev/null | head -n1)
    if [[ -n "$FOUND_WALLET_BINARY" ]]; then
        MONERO_WALLET_BINARIES+=("$FOUND_WALLET_BINARY")
        log_ok "Found Monero wallet binary: $FOUND_WALLET_BINARY"
    else
        log_warn "No Monero wallet binary found after build"
    fi
fi

# Step 7: Install Monero binaries to ~/.monerosim/bin
log_header "Step 7: Installing Monero Binaries"

log_info "Installing Monero binaries to $MONEROSIM_BIN..."

# Install the monerod binary
MAIN_BINARY="${MONEROD_BINARIES[0]}"
log_info "Installing monerod binary: $MAIN_BINARY -> $MONEROSIM_BIN/monerod"
cp "$MAIN_BINARY" "$MONEROSIM_BIN/monerod"
chmod +x "$MONEROSIM_BIN/monerod"

# Install monero-wallet-rpc if found
if [[ ${#MONERO_WALLET_BINARIES[@]} -gt 0 ]]; then
    MAIN_WALLET_BINARY="${MONERO_WALLET_BINARIES[0]}"
    log_info "Installing monero-wallet-rpc binary: $MAIN_WALLET_BINARY -> $MONEROSIM_BIN/monero-wallet-rpc"
    cp "$MAIN_WALLET_BINARY" "$MONEROSIM_BIN/monero-wallet-rpc"
    chmod +x "$MONEROSIM_BIN/monero-wallet-rpc"
fi

# Verify the binaries work
if "$MONEROSIM_BIN/monerod" --version >/dev/null 2>&1; then
    log_ok "Successfully installed monerod to $MONEROSIM_BIN/"
else
    log_err "monerod installation may have issues"
fi

# Verify the wallet binary works if installed
if [[ -f "$MONEROSIM_BIN/monero-wallet-rpc" ]] && "$MONEROSIM_BIN/monero-wallet-rpc" --version >/dev/null 2>&1; then
    log_ok "Successfully installed monero-wallet-rpc to $MONEROSIM_BIN/"
else
    log_warn "monero-wallet-rpc installation may have issues"
fi

# Step 8: Generate Shadow configuration
log_header "Step 8: Generating Shadow Configuration"

log_info "Generating Shadow configuration from test_configs/quickstart.yaml..."

# Ensure we're in the right directory and the binary exists
cd "$SCRIPT_DIR"
if [[ ! -f "./target/release/monerosim" ]]; then
    log_err "MoneroSim binary not found at ./target/release/monerosim"
    log_err "Current directory: $(pwd)"
    log_err "Please ensure MoneroSim was built successfully"
    exit 1
fi

./target/release/monerosim --config test_configs/quickstart.yaml --output shadow_output

if [[ $? -eq 0 ]] && [[ -f "shadow_output/shadow_agents.yaml" ]]; then
    log_ok "Shadow configuration generated successfully"
else
    log_err "Failed to generate Shadow configuration"
    exit 1
fi

# Step 9: Calibrate crypto timing for this machine
# This builds Monero's performance_tests binary and measures CLSAG +
# Bulletproofs+ verification time, which is used by the auto-config
# guardrail to predict wall time and warn if a scenario won't fit.
# If we don't do it here, it will run lazily (with ~30 s pause) the
# first time someone generates/expands a scenario.
log_header "Step 9: Calibrating Crypto Timing"
log_info "Measuring crypto verification time (~30 s)..."
if python3 -m scripts.calibrate; then
    log_ok "Calibration saved to ~/.monerosim/calibration.json"
else
    log_warn "Calibration failed — will retry lazily on first config expansion."
    log_warn "Auto-config will fall back to pessimistic defaults until then."
fi

# Step 10: Optional Test Simulation
log_header "Step 10: Optional Test Simulation"

log_info "Setup is complete! You can now run a test simulation to verify everything works."
log_warn "The test simulation (test_configs/quickstart.yaml) runs for 6 hours simulated time"
log_warn "This is a quickstart test with 10 agents (~10-15 min wall clock)"
log_info ""
log_info "Choose an option:"
echo "  y/Y - Run the full test simulation"
echo "  n/N - Skip test simulation and exit setup"
echo ""
# Drain stdin so a stray keypress during the long build doesn't auto-answer the prompt.
read -r -t 0.1 -N 1000 _ 2>/dev/null || true
read -p "Run test simulation? (y/N): " -r

if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Delegating to ./run_sim.sh — the same path users run day-to-day."
    log_info "run_sim.sh handles preflight, ramdisk, archiving, OOM detection,"
    log_info "and live progress display. Scroll up after it finishes for the summary."
    echo ""

    if ./run_sim.sh --config test_configs/quickstart.yaml; then
        log_ok "Test simulation completed successfully."
        log_info "Per-host logs and run summary archived under archived_runs/<latest>/."
        log_info "For deeper validation: ./scripts/smoke_test.sh quickstart"
    else
        log_err "Test simulation failed (run_sim.sh exited non-zero)."
        log_info "Check archived_runs/<latest>/ for shadow.log, monerosim.log, and per-host stdout."
        exit 1
    fi
else
    log_info "Skipping test simulation as requested."
fi

# Final success message
log_header "Setup Complete!"
log_ok "MoneroSim is now ready to use!"
echo ""
log_info "Verify installation:"
echo "  ~/.monerosim/bin/shadow --version      # shadowformonero version"
echo "  ~/.monerosim/bin/monerod --version     # Monero daemon version"
echo "  ./target/release/monerosim --help      # monerosim CLI usage"
echo ""
log_info "Run your first simulation:"
echo "  ./run_sim.sh --config test_configs/quickstart.yaml           # Quick test (~10-15 min)"
echo ""
log_info "Monitor a running simulation:"
echo "  tail shadow.log                        # Shadow progress"
echo "  ./scripts/check_sim.sh                 # Detailed status dashboard"
echo ""
log_info "Installed binaries: $MONEROSIM_BIN/"
echo "  - shadow"
echo "  - monerod"
echo "  - monero-wallet-rpc"
echo ""
log_ok "Happy simulating!"
