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
UPDATE_CUPRATE=false
UPDATE_SIM_BINARY=false

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
        --cuprate)
            UPDATE_CUPRATE=true
            shift
            ;;
        --sim-binary|--hardfork)
            UPDATE_SIM_BINARY=true
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
            echo "  --cuprate       Update cuprate only (optional dep; skipped if not installed)"
            echo "  --sim-binary    Rebuild monerod-sim (vanilla monero.pin + hard fork schedule"
            echo "                  and native-mining patches, aliased as monerod-hf) with"
            echo "                  --rebuild. Also rebuilt automatically whenever monero is"
            echo "                  rebuilt and a monerod-sim/monerod-hf is installed."
            echo "  --hardfork      Synonym for --sim-binary."
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
            echo "  cuprate           - Rust Monero node, OPTIONAL (pinned by cuprate.pin)"
            echo "                      Install with ./setup.sh --cuprate"
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

# Pin shadowformonero to the same ref setup.sh installs. Single source of
# truth: shadowformonero.pin at the repo root (also read by setup.sh and
# run_sim.sh's preflight version check). update.sh checks out this tag
# rather than pulling the branch tip so a rebuild here never silently
# un-pins the fork commit setup.sh installed.
if [[ ! -f "$SCRIPT_DIR/shadowformonero.pin" ]]; then
    log_err "shadowformonero.pin not found at the repo root — cannot determine the pinned fork version"
    exit 1
fi
SHADOWFORMONERO_REF="$(tr -d '[:space:]' < "$SCRIPT_DIR/shadowformonero.pin")"

# Pin monero the same way (monero.pin — single source of truth, also read by
# setup.sh and run_sim.sh's preflight). Pinned checkout, never a master pull.
if [[ ! -f "$SCRIPT_DIR/monero.pin" ]]; then
    log_err "monero.pin not found at the repo root — cannot determine the pinned monero version"
    exit 1
fi
MONERO_REF="$(tr -d '[:space:]' < "$SCRIPT_DIR/monero.pin")"

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
    # Stamp the installed ref so setup.sh's drift detection stays accurate
    # (mirrors install_shadowformonero() in setup.sh).
    echo "$SHADOWFORMONERO_REF" > "$MONEROSIM_HOME/SHADOWFORMONERO_VERSION"
    log_ok "shadowformonero rebuilt and installed ($SHADOWFORMONERO_REF)"
    cd "$SCRIPT_DIR"
}

rebuild_sim_binary() {
    # monerod-sim = vanilla monero (monero.pin) + every vendored patch, each
    # flag-gated and stock when its flag is absent:
    #   patches/monero-fakechain-hardforks.patch  --fakechain-hard-forks
    #   patches/monero-sim-mining.patch           --sim-hash-interval-ms / --sim-rx-full-dataset
    # One build serves the fork-schedule and native-mining features; monerod-hf
    # is kept as a symlink alias so existing fork configs keep working.
    local monero_dir="$1"
    local patches=(
        "$SCRIPT_DIR/patches/monero-fakechain-hardforks.patch"
        "$SCRIPT_DIR/patches/monero-sim-mining.patch"
    )
    local p
    for p in "${patches[@]}"; do
        if [[ ! -f "$p" ]]; then
            log_err "Patch not found: $p"
            return
        fi
    done
    if [[ ! -d "$monero_dir/.git" ]]; then
        log_err "Monero checkout not found at $monero_dir (run the main setup first)"
        return
    fi
    local monero_ref
    monero_ref=$(tr -d '[:space:]' < "$SCRIPT_DIR/monero.pin")
    log_info "Rebuilding monerod-sim ($monero_ref + vendored patches)..."

    # Build in a DETACHED WORKTREE of the pinned checkout. The patches are
    # applied there and only there: the main checkout — and the primary
    # monerod built from it — stays byte-for-byte vanilla. Recreated from
    # scratch every run so no stale patch state can survive; ccache keeps the
    # rebuild cheap.
    local sim_build_dir="$MONEROSIM_HOME/build/monero-sim"
    mkdir -p "$MONEROSIM_HOME/build"
    local d
    for d in "$sim_build_dir" "$MONEROSIM_HOME/build/monero-hf"; do
        if [[ -d "$d" ]]; then
            git -C "$monero_dir" worktree remove --force "$d" 2>/dev/null || rm -rf "$d"
        fi
    done
    git -C "$monero_dir" worktree prune 2>/dev/null || true
    git -C "$monero_dir" fetch --tags --force origin >/dev/null 2>&1 || true
    if ! git -C "$monero_dir" worktree add --detach "$sim_build_dir" "$monero_ref"; then
        log_err "Could not create monero worktree at $monero_ref (see monero.pin)"
        return
    fi

    # Tripwire: when monero.pin moves past what a patch applies to, fail
    # loudly here instead of drifting silently. Applied in order.
    for p in "${patches[@]}"; do
        if ! git -C "$sim_build_dir" apply --check "$p"; then
            log_err "$(basename "$p") no longer applies to monero $monero_ref"
            log_err "The patch must be rebased onto the new pin (or upstreamed)."
            return
        fi
        git -C "$sim_build_dir" apply "$p"
    done
    (cd "$sim_build_dir" && git submodule update --init --recursive)

    log_info "Building patched monerod (monerod-sim, -j${BUILD_JOBS}) — this takes a while..."
    if ! (cd "$sim_build_dir" && mkdir -p build/release && cd build/release \
          && cmake -DCMAKE_BUILD_TYPE=Release ../.. > cmake.log 2>&1 \
          && nice -n10 make -j"$BUILD_JOBS" daemon); then
        log_err "monerod-sim build failed (see $sim_build_dir/build/release/cmake.log)"
        return
    fi

    cp -f "$sim_build_dir/build/release/bin/monerod" "$MONEROSIM_BIN/monerod-sim"
    # Alias for configs that predate the combined build (daemon: monerod-hf).
    ln -sfn monerod-sim "$MONEROSIM_BIN/monerod-hf"
    rm -f "$MONEROSIM_BIN/monerod-hf.provenance"
    {
        echo "binary: monerod-sim (alias: monerod-hf)"
        echo "base: $monero_ref (monero.pin)"
        for p in "${patches[@]}"; do
            echo "patch: patches/$(basename "$p")"
            echo "patch_sha256: $(sha256sum "$p" | cut -d' ' -f1)"
        done
        echo "built: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "$MONEROSIM_BIN/monerod-sim.provenance"
    log_ok "Installed monerod-sim to $MONEROSIM_BIN/monerod-sim (alias monerod-hf)"
    cd "$SCRIPT_DIR"
}

rebuild_cuprate() {
    local cuprate_dir="$1"
    log_info "Rebuilding cuprated (this takes a while)..."
    if (cd "$cuprate_dir" && cargo build --release -p cuprated -j "$BUILD_JOBS"); then
        cp -f "$cuprate_dir/target/release/cuprated" "$MONEROSIM_BIN/cuprated"
        log_ok "cuprated rebuilt and installed to $MONEROSIM_BIN/cuprated"
    else
        log_err "cuprated build failed"
    fi
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
CUPRATE_UPDATED=false

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
    # Pinned checkout (monero.pin), not a master pull — mirrors
    # update_shadowformonero_pinned so `update.sh` can never un-pin monero.
    monero_path="$DEPS_DIR/monero"
    if [[ -d "$monero_path/.git" ]]; then
        log_info "Updating monero (pinned to $MONERO_REF)..."
        cd "$monero_path"
        if ! git diff --quiet || ! git diff --cached --quiet; then
            log_warn "monero has uncommitted changes; skipping monero update"
        else
            monero_before=$(git rev-parse HEAD)
            git fetch --tags --force origin
            if git checkout "$MONERO_REF"; then
                git submodule update --init --recursive
                [[ "$(git rev-parse HEAD)" != "$monero_before" ]] && MONERO_UPDATED=true
                log_ok "monero at $MONERO_REF"
            else
                log_warn "Could not checkout monero $MONERO_REF (see monero.pin)"
            fi
        fi
        cd "$SCRIPT_DIR"
    else
        log_warn "monero not found at $monero_path - skipping"
    fi
fi

if [[ "$UPDATE_ALL" == "true" ]] || [[ "$UPDATE_CUPRATE" == "true" ]]; then
    # Pinned checkout, mirroring monero above. cuprate is OPTIONAL, so a missing
    # checkout is a skip and never an error — most setups never install it.
    cuprate_path="${CUPRATE_DIR:-$DEPS_DIR/cuprate}"
    CUPRATE_REF=""
    if [[ -f "$SCRIPT_DIR/cuprate.pin" ]]; then
        CUPRATE_REF=$(grep -vE '^[[:space:]]*(#|$)' "$SCRIPT_DIR/cuprate.pin" | head -n1 | tr -d '[:space:]')
    fi
    if [[ -z "$CUPRATE_REF" ]]; then
        log_warn "cuprate.pin missing or empty - skipping cuprate update"
    elif [[ -d "$cuprate_path/.git" ]]; then
        log_info "Updating cuprate (pinned to $CUPRATE_REF)..."
        cd "$cuprate_path"
        if ! git diff --quiet || ! git diff --cached --quiet; then
            log_warn "cuprate has uncommitted changes; skipping cuprate update"
        else
            cuprate_before=$(git rev-parse HEAD)
            # --all: a reused checkout may carry a fork on `origin` with the
            # canonical repo on `upstream`.
            git fetch --all --tags --force
            if git checkout "$CUPRATE_REF"; then
                [[ "$(git rev-parse HEAD)" != "$cuprate_before" ]] && CUPRATE_UPDATED=true
                log_ok "cuprate at $CUPRATE_REF"
            else
                log_warn "Could not checkout cuprate $CUPRATE_REF (see cuprate.pin)"
            fi
        fi
        cd "$SCRIPT_DIR"
    else
        log_warn "cuprate not found at $cuprate_path - skipping (install with ./setup.sh --cuprate)"
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

    if [[ "$CUPRATE_UPDATED" == "true" ]] || [[ "$UPDATE_CUPRATE" == "true" ]]; then
        cuprate_rebuild_path="${CUPRATE_DIR:-$DEPS_DIR/cuprate}"
        if [[ -d "$cuprate_rebuild_path/.git" ]]; then
            rebuild_cuprate "$cuprate_rebuild_path"
        fi
    fi

    # monerod-sim goes stale whenever monero moves: rebuild it when explicitly
    # asked (--sim-binary / --hardfork) OR whenever monero was rebuilt and a
    # monerod-sim or monerod-hf is already installed (otherwise fork/native
    # sims would silently run an old base).
    if [[ "$UPDATE_SIM_BINARY" == "true" ]] \
        || { [[ -x "$MONEROSIM_BIN/monerod-sim" || -x "$MONEROSIM_BIN/monerod-hf" ]] && { [[ "$MONERO_UPDATED" == "true" ]] || [[ "$UPDATE_MONERO" == "true" ]]; }; }; then
        if [[ -d "$DEPS_DIR/monero/.git" ]]; then
            rebuild_sim_binary "$DEPS_DIR/monero"
        else
            log_warn "monero checkout not found at $DEPS_DIR/monero — cannot rebuild monerod-sim"
        fi
    fi
elif [[ "$MONEROSIM_UPDATED" == "true" ]] || [[ "$SHADOW_UPDATED" == "true" ]] || [[ "$MONERO_UPDATED" == "true" ]] || [[ "$CUPRATE_UPDATED" == "true" ]]; then
    echo ""
    log_warn "Some repositories were updated. Consider running with --rebuild to update binaries."
fi

echo ""
log_ok "Update complete!"
