#!/bin/bash

# Update script for monerosim and sister repositories
#
# Usage: ./update.sh [OPTIONS]
#
# Options:
#   --all           Update all repositories (monerosim + sister repos)
#   --rebuild       Rebuild binaries after updating
#   --shadow        Update shadowformonero only
#   --monero        Update monero only
#   -h, --help      Show this help message

set -euo pipefail

# Colors + shared logging vocabulary
source "$(dirname "${BASH_SOURCE[0]}")/scripts/log_lib.sh"

# Store script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPS_DIR="$SCRIPT_DIR/sibling_repos"

# Repository locations and their expected branches
declare -A REPOS
REPOS["monerosim"]="$SCRIPT_DIR:main"
REPOS["monero"]="$DEPS_DIR/monero:master"
REPOS["shadowformonero"]="$DEPS_DIR/shadowformonero:main"

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
            echo "  --monero        Update monero only"
            echo "  -h, --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0              Update monerosim only"
            echo "  $0 --all        Update all repositories"
            echo "  $0 --all --rebuild   Update all and rebuild binaries"
            echo ""
            echo "Dependency repositories (in sibling_repos/):"
            echo "  monero            - Official Monero (branch: master)"
            echo "  shadowformonero   - Shadow simulator (branch: main)"
            exit 0
            ;;
        *)
            log_err "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Pick a parallel-build job count that won't OOM the C++ compile.
# Mirrors setup.sh's BUILD_JOBS calculation (setup.sh:77-96) verbatim — keep
# in sync if that logic changes.
# Monero's heaviest TUs (blockchain.cpp, bulletproofs_plus.cc) can each
# need ~2GB of RAM in cc1plus. Running -j$(nproc) on low-memory machines
# kills the build with "Killed signal terminated program cc1plus".
# Rule: jobs = min(nproc, max(1, ram_gb / 2)).
# Honor a pre-set BUILD_JOBS env var so users can override with
# e.g. BUILD_JOBS=2 ./update.sh on tight machines.
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

# Pin shadowformonero to the same ref setup.sh installs (setup.sh:607's
# SHADOWFORMONERO_REF). Must be bumped in lock-step with that value —
# update.sh checks out this tag rather than pulling the branch tip so a
# rebuild here never silently un-pins the fork commit setup.sh installed.
SHADOWFORMONERO_REF="v0.1.0"

# Function to update a repository
update_repo() {
    local name=$1
    local path=$2
    local branch=$3

    if [[ ! -d "$path" ]]; then
        log_warn "$name not found at $path - skipping"
        return 1
    fi

    if [[ ! -d "$path/.git" ]]; then
        log_warn "$name at $path is not a git repository - skipping"
        return 1
    fi

    log_info "Updating $name..."
    cd "$path"

    # Check current branch
    local current_branch=$(git branch --show-current)
    if [[ "$current_branch" != "$branch" ]]; then
        log_warn "$name is on branch '$current_branch', expected '$branch'"
        read -p "  Switch to $branch? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git checkout "$branch"
        fi
    fi

    # Check for local changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        log_warn "$name has uncommitted changes"
        git status --short
        read -p "  Stash changes and continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git stash
            log_info "Changes stashed (use 'git stash pop' to restore)"
        else
            log_warn "Skipping $name update"
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
        log_ok "$name updated ($commit_count new commits)"
        git log --oneline "$before_hash".."$after_hash" | head -5
        if [[ $commit_count -gt 5 ]]; then
            echo "  ... and $((commit_count - 5)) more"
        fi
        cd "$SCRIPT_DIR"
        return 0  # Updated
    else
        log_ok "$name is already up to date"
        cd "$SCRIPT_DIR"
        return 2  # No changes
    fi
}

# Function to update shadowformonero. Unlike update_repo(), this pins to
# SHADOWFORMONERO_REF (a tag) instead of pulling the branch tip, so it stays
# in sync with the exact fork commit setup.sh installs.
update_shadowformonero_pinned() {
    local path="$DEPS_DIR/shadowformonero"

    if [[ ! -d "$path" ]]; then
        log_warn "shadowformonero not found at $path - skipping"
        return 1
    fi

    if [[ ! -d "$path/.git" ]]; then
        log_warn "shadowformonero at $path is not a git repository - skipping"
        return 1
    fi

    log_info "Updating shadowformonero (pinned to $SHADOWFORMONERO_REF)..."
    cd "$path"

    # Check for local changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        log_warn "shadowformonero has uncommitted changes"
        git status --short
        read -p "  Stash changes and continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git stash
            log_info "Changes stashed (use 'git stash pop' to restore)"
        else
            log_warn "Skipping shadowformonero update"
            cd "$SCRIPT_DIR"
            return 1
        fi
    fi

    # Fetch and checkout the pinned ref (not the branch tip)
    local before_hash=$(git rev-parse HEAD)
    git fetch origin --tags
    git checkout "$SHADOWFORMONERO_REF"
    local after_hash=$(git rev-parse HEAD)

    if [[ "$before_hash" != "$after_hash" ]]; then
        log_ok "shadowformonero updated to $SHADOWFORMONERO_REF"
        cd "$SCRIPT_DIR"
        return 0  # Updated
    else
        log_ok "shadowformonero is already at $SHADOWFORMONERO_REF"
        cd "$SCRIPT_DIR"
        return 2  # No changes
    fi
}

# Function to rebuild monerosim
rebuild_monerosim() {
    log_info "Rebuilding monerosim..."
    cd "$SCRIPT_DIR"
    cargo build --release
    log_ok "monerosim rebuilt"
}

# Function to rebuild monero binaries
rebuild_monero() {
    local monero_dir=$1
    local name=$2

    if [[ ! -d "$monero_dir" ]]; then
        log_warn "$name directory not found - skipping rebuild"
        return 1
    fi

    log_info "Rebuilding $name (this may take several minutes)..."
    cd "$monero_dir"

    # Update submodules if needed
    git submodule update --init --recursive

    mkdir -p build/release
    cd build/release
    cmake -DCMAKE_BUILD_TYPE=Release ../..
    make -j"$BUILD_JOBS" daemon wallet_rpc_server

    # Install to ~/.monerosim/bin
    if [[ -f "bin/monerod" ]]; then
        cp bin/monerod "$MONEROSIM_BIN/monerod"
        log_ok "Installed monerod to $MONEROSIM_BIN/"
    fi
    if [[ -f "bin/monero-wallet-rpc" ]]; then
        cp bin/monero-wallet-rpc "$MONEROSIM_BIN/monero-wallet-rpc"
        log_ok "Installed monero-wallet-rpc to $MONEROSIM_BIN/"
    fi

    cd "$SCRIPT_DIR"
}

# Function to rebuild shadowformonero
rebuild_shadow() {
    local shadow_dir="$DEPS_DIR/shadowformonero"

    if [[ ! -d "$shadow_dir" ]]; then
        log_warn "shadowformonero directory not found - skipping rebuild"
        return 1
    fi

    log_info "Rebuilding shadowformonero (this may take 10-20 minutes)..."
    cd "$shadow_dir"
    ./setup build --jobs "$BUILD_JOBS" --prefix "$MONEROSIM_HOME"
    ./setup install
    log_ok "shadowformonero rebuilt and installed"
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
    if update_shadowformonero_pinned; then
        SHADOW_UPDATED=true
    fi
fi

if [[ "$UPDATE_ALL" == "true" ]] || [[ "$UPDATE_MONERO" == "true" ]]; then
    IFS=':' read -r path branch <<< "${REPOS[monero]}"
    if update_repo "monero" "$path" "$branch"; then
        MONERO_UPDATED=true
    fi
fi

# Rebuild if requested or if there were updates
echo ""
if [[ "$REBUILD" == "true" ]]; then
    log_info "Rebuilding as requested..."

    if [[ "$MONEROSIM_UPDATED" == "true" ]] || [[ "$UPDATE_ALL" == "true" ]]; then
        rebuild_monerosim
    fi

    if [[ "$SHADOW_UPDATED" == "true" ]] || [[ "$UPDATE_SHADOW" == "true" ]]; then
        rebuild_shadow
    fi

    if [[ "$MONERO_UPDATED" == "true" ]] || [[ "$UPDATE_MONERO" == "true" ]]; then
        if [[ -d "$DEPS_DIR/monero" ]]; then
            rebuild_monero "$DEPS_DIR/monero" "monero"
        fi
    fi
elif [[ "$MONEROSIM_UPDATED" == "true" ]] || [[ "$SHADOW_UPDATED" == "true" ]] || [[ "$MONERO_UPDATED" == "true" ]]; then
    echo ""
    log_warn "Some repositories were updated. Consider running with --rebuild to update binaries."
fi

echo ""
log_ok "Update complete!"
