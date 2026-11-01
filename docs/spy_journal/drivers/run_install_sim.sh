#!/bin/bash
# Run setup.sh's install_sim_monerod() alone (worktree recreated, every patch applied in order, rebuild, install,
# provenance), without the rest of setup.sh and its prompts. Used on simbox3 for the fixed-RandomX-seed patch.
set -u
SCRIPT_DIR="$HOME/monerosim"
MONEROSIM_HOME="$HOME/.monerosim"
MONEROSIM_BIN="$MONEROSIM_HOME/bin"
MONERO_DIR="$SCRIPT_DIR/sibling_repos/monero"
BUILD_JOBS=${BUILD_JOBS:-$(nproc)}
log_info() { echo "[info] $*"; }
log_ok()   { echo "[ok] $*"; }
log_err()  { echo "[err] $*" >&2; }
eval "$(sed -n '/^install_sim_monerod() {/,/^}/p' "$SCRIPT_DIR/setup.sh")"
install_sim_monerod
echo "EXIT $?"
