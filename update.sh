#!/bin/bash

# Update script for monerosim and sister repositories
#
# Usage: ./update.sh [OPTIONS]
#
# Options:
#   --all           Update all repositories (monerosim + sister repos)
#   --rebuild       Rebuild binaries after updating
#   --shadow        Update shadowformonero only
#   --monero        Update monero-vanilla and monero-shadow only
#   -h, --help      Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Store script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Repository locations and their expected branches
declare -A REPOS
REPOS["monerosim"]="$SCRIPT_DIR:main"
REPOS["monero-vanilla"]="$PARENT_DIR/monero-vanilla:master"
REPOS["monero-shadow"]="$PARENT_DIR/monero-shadow:shadow-complete"
REPOS["shadowformonero"]="$PARENT_DIR/shadowformonero:optimize"

# Installation directory
MONEROSIM_HOME="$HOME/.monerosim"
MONEROSIM_BIN="$MONEROSIM_HOME/bin"

# Parse arguments
UPDATE_ALL=false
REBUILD=false
UPDATE_SHADOW=false
UPDATE_MONERO=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            UPDATE_ALL=true
            shift
            ;;
        --rebuild)
            REBUILD=true
            shift
            ;;
        --shadow)
            UPDATE_SHADOW=true
            shift
            ;;
        --monero)
            UPDATE_MONERO=true
            shift
            ;;
        -h|--help)
            echo "Update script for monerosim and sister repositories"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --all           Update all repositories (monerosim + sister repos)"
            echo "  --rebuild       Rebuild binaries after updating"
            echo "  --shadow        Update shadowformonero only"
            echo "  --monero        Update monero-vanilla and monero-shadow only"
            echo "  -h, --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0              Update monerosim only"
            echo "  $0 --all        Update all repositories"
            echo "  $0 --all --rebuild   Update all and rebuild binaries"
            echo ""
            echo "Sister repositories (expected in parent directory):"
            echo "  monero-vanilla    - Official Monero (branch: master)"
            echo "  monero-shadow     - Monero for Shadow (branch: shadow-complete)"
            echo "  shadowformonero   - Shadow simulator (branch: optimize)"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function to update a repository
update_repo() {
    local name=$1
    local path=$2
    local branch=$3

    if [[ ! -d "$path" ]]; then
        print_warning "$name not found at $path - skipping"
        return 1
    fi

    if [[ ! -d "$path/.git" ]]; then
        print_warning "$name at $path is not a git repository - skipping"
        return 1
    fi

    print_status "Updating $name..."
    cd "$path"

    # Check current branch
    local current_branch=$(git branch --show-current)
    if [[ "$current_branch" != "$branch" ]]; then
        print_warning "$name is on branch '$current_branch', expected '$branch'"
        read -p "  Switch to $branch? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git checkout "$branch"
        fi
    fi

    # Check for local changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        print_warning "$name has uncommitted changes"
        git status --short
        read -p "  Stash changes and continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git stash
            print_status "Changes stashed (use 'git stash pop' to restore)"
        else
            print_warning "Skipping $name update"
            cd "$SCRIPT_DIR"
            return 1
        fi
    fi

    # Fetch and pull
    local before_hash=$(git rev-parse HEAD)
    git fetch origin
    git pull origin "$branch"
    local after_hash=$(git rev-parse HEAD)

    if [[ "$before_hash" != "$after_hash" ]]; then
        local commit_count=$(git rev-list --count "$before_hash".."$after_hash")
        print_success "$name updated ($commit_count new commits)"
        git log --oneline "$before_hash".."$after_hash" | head -5
        if [[ $commit_count -gt 5 ]]; then
            echo "  ... and $((commit_count - 5)) more"
        fi
        cd "$SCRIPT_DIR"
        return 0  # Updated
    else
        print_success "$name is already up to date"
        cd "$SCRIPT_DIR"
        return 2  # No changes
    fi
}

# Function to rebuild monerosim
rebuild_monerosim() {
    print_status "Rebuilding monerosim..."
    cd "$SCRIPT_DIR"
    cargo build --release
    print_success "monerosim rebuilt"
}

# Function to rebuild monero binaries
rebuild_monero() {
    local monero_dir=$1
    local name=$2

    if [[ ! -d "$monero_dir" ]]; then
        print_warning "$name directory not found - skipping rebuild"
        return 1
    fi

    print_status "Rebuilding $name (this may take several minutes)..."
    cd "$monero_dir"

    # Update submodules if needed
    git submodule update --init --recursive

    mkdir -p build/release
    cd build/release
    cmake -DCMAKE_BUILD_TYPE=Release ../..
    make -j$(nproc) daemon wallet_rpc_server

    # Install to ~/.monerosim/bin
    if [[ -f "bin/monerod" ]]; then
        cp bin/monerod "$MONEROSIM_BIN/monerod"
        print_success "Installed monerod to $MONEROSIM_BIN/"
    fi
    if [[ -f "bin/monero-wallet-rpc" ]]; then
        cp bin/monero-wallet-rpc "$MONEROSIM_BIN/monero-wallet-rpc"
        print_success "Installed monero-wallet-rpc to $MONEROSIM_BIN/"
    fi

    cd "$SCRIPT_DIR"
}

# Function to rebuild shadowformonero
rebuild_shadow() {
    local shadow_dir="$PARENT_DIR/shadowformonero"

    if [[ ! -d "$shadow_dir" ]]; then
        print_warning "shadowformonero directory not found - skipping rebuild"
        return 1
    fi

    print_status "Rebuilding shadowformonero (this may take 10-20 minutes)..."
    cd "$shadow_dir"
    ./setup build --jobs $(nproc) --prefix "$MONEROSIM_HOME"
    ./setup install
    print_success "shadowformonero rebuilt and installed"
    cd "$SCRIPT_DIR"
}

# Main logic
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}MoneroSim Update Script${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Track what was updated for rebuild decisions
MONEROSIM_UPDATED=false
MONERO_UPDATED=false
SHADOW_UPDATED=false

# Always update monerosim
IFS=':' read -r path branch <<< "${REPOS[monerosim]}"
if update_repo "monerosim" "$path" "$branch"; then
    MONEROSIM_UPDATED=true
fi

# Update sister repos based on flags
if [[ "$UPDATE_ALL" == "true" ]] || [[ "$UPDATE_SHADOW" == "true" ]]; then
    IFS=':' read -r path branch <<< "${REPOS[shadowformonero]}"
    if update_repo "shadowformonero" "$path" "$branch"; then
        SHADOW_UPDATED=true
    fi
fi

if [[ "$UPDATE_ALL" == "true" ]] || [[ "$UPDATE_MONERO" == "true" ]]; then
    IFS=':' read -r path branch <<< "${REPOS[monero-vanilla]}"
    update_repo "monero-vanilla" "$path" "$branch" || true

    IFS=':' read -r path branch <<< "${REPOS[monero-shadow]}"
    if update_repo "monero-shadow" "$path" "$branch"; then
        MONERO_UPDATED=true
    fi
fi

# Rebuild if requested or if there were updates
echo ""
if [[ "$REBUILD" == "true" ]]; then
    print_status "Rebuilding as requested..."

    if [[ "$MONEROSIM_UPDATED" == "true" ]] || [[ "$UPDATE_ALL" == "true" ]]; then
        rebuild_monerosim
    fi

    if [[ "$SHADOW_UPDATED" == "true" ]] || [[ "$UPDATE_SHADOW" == "true" ]]; then
        rebuild_shadow
    fi

    if [[ "$MONERO_UPDATED" == "true" ]] || [[ "$UPDATE_MONERO" == "true" ]]; then
        # Prefer monero-shadow if it exists, otherwise use monero-vanilla
        if [[ -d "$PARENT_DIR/monero-shadow" ]]; then
            rebuild_monero "$PARENT_DIR/monero-shadow" "monero-shadow"
        elif [[ -d "$PARENT_DIR/monero-vanilla" ]]; then
            rebuild_monero "$PARENT_DIR/monero-vanilla" "monero-vanilla"
        fi
    fi
elif [[ "$MONEROSIM_UPDATED" == "true" ]] || [[ "$SHADOW_UPDATED" == "true" ]] || [[ "$MONERO_UPDATED" == "true" ]]; then
    echo ""
    print_warning "Some repositories were updated. Consider running with --rebuild to update binaries."
fi

echo ""
print_success "Update complete!"
