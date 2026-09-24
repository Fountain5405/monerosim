#!/usr/bin/env bash
# test_pinned_paths.sh - drives run_sim.sh's real check_pinned_paths() with
# crafted configs: no pins (silent), a pinned-but-empty dir (warn, continue),
# a pinned dir already holding run state (refuse, exit 1, run dir removed),
# the same with --allow-shared-paths (warn, continue), and an env-pinned
# daemon dir holding monero-* dirs (refuse).
#
# Usage: ./scripts/test_pinned_paths.sh   (from the repo root or anywhere)
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
T=$(mktemp -d "${TMPDIR:-/tmp}/pintest.XXXX")
trap 'rm -rf "$T"' EXIT
fails=0
pass(){ echo "  PASS $*"; }
fail(){ echo "  FAIL $*"; fails=$((fails+1)); }

eval "$(awk '/^check_pinned_paths\(\) \{/{f=1} f{print} f&&/^\}/{exit}' run_sim.sh)"
WARNS=""; ERRS=""
log_warn(){ WARNS+="$*"$'\n'; }
log_err(){ ERRS+="$*"$'\n'; }
log_info(){ :; }; log_ok(){ :; }

setup() {   # $1 = yaml general block extra lines
    rm -rf "$T"/*; WARNS=""; ERRS=""
    RUN_ID=20260101_000000_pintest; RUN_TMP_DIR="$T/tmp/monerosim-$RUN_ID"
    SHARED_DIR="$RUN_TMP_DIR/shared"; DAEMON_DATA_BASE="$RUN_TMP_DIR"
    RUN_DIR="$T/archived_runs/$RUN_ID"; mkdir -p "$RUN_DIR"; echo "$$ 1" > "$RUN_DIR/.owner_pid"
    DATA_BASE=""; ALLOW_SHARED_PATHS=false; CONFIG="$T/cfg.yaml"
    printf 'general:\n  stop_time: 1h\n%b\nagents:\n  relay-001: {daemon: monerod}\n' "$1" > "$CONFIG"
}
run_check() { ( check_pinned_paths ); }   # subshell: exit 1 must not kill us

echo "== no pins"
setup ""
run_check; rc=$?
[[ $rc -eq 0 ]] && pass "rc 0" || fail "rc $rc"
[[ -z "$WARNS" ]] && pass "silent" || fail "unexpected warning: $WARNS"

echo "== yaml pins shared_dir to an empty dir"
setup "  shared_dir: $T/pinned_shared"
mkdir -p "$T/pinned_shared"
out=$(run_check 2>&1); rc=$?
[[ $rc -eq 0 ]] && pass "rc 0 (warn only)" || fail "rc $rc"
[[ -d "$RUN_DIR" ]] && pass "run dir kept" || fail "run dir removed"

echo "== yaml pins shared_dir holding a registry -> refuse"
setup "  shared_dir: $T/pinned_shared"
mkdir -p "$T/pinned_shared"; echo '{}' > "$T/pinned_shared/agent_registry.json"
run_check >/dev/null 2>&1; rc=$?
[[ $rc -eq 1 ]] && pass "exit 1" || fail "rc $rc"
[[ ! -d "$RUN_DIR" ]] && pass "run dir removed on refusal" || fail "run dir left behind"
[[ -f "$T/pinned_shared/agent_registry.json" ]] && pass "pinned state untouched" || fail "pinned state damaged"

echo "== same with --allow-shared-paths -> proceed"
setup "  shared_dir: $T/pinned_shared"; ALLOW_SHARED_PATHS=true
mkdir -p "$T/pinned_shared"; echo '{}' > "$T/pinned_shared/agent_registry.json"
run_check >/dev/null 2>&1; rc=$?
[[ $rc -eq 0 ]] && pass "rc 0" || fail "rc $rc"
[[ -d "$RUN_DIR" ]] && pass "run dir kept" || fail "run dir removed"

echo "== env-pinned daemon dir holding monero-* -> refuse"
setup ""; DAEMON_DATA_BASE="$T/pinned_daemon"
mkdir -p "$T/pinned_daemon/monero-relay-001"
run_check >/dev/null 2>&1; rc=$?
[[ $rc -eq 1 ]] && pass "exit 1" || fail "rc $rc"
[[ -d "$T/pinned_daemon/monero-relay-001" ]] && pass "daemon state untouched" || fail "daemon state damaged"

echo "== env-pinned daemon dir, empty -> warn only"
setup ""; DAEMON_DATA_BASE="$T/pinned_daemon_empty"
mkdir -p "$T/pinned_daemon_empty"
run_check >/dev/null 2>&1; rc=$?
[[ $rc -eq 0 ]] && pass "rc 0" || fail "rc $rc"

echo "== $fails failure(s)"
exit $fails
