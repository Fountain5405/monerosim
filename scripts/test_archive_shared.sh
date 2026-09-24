#!/usr/bin/env bash
# test_archive_shared.sh - drives run_sim.sh's real archive_results() (plus
# archive_transaction_registry and archive_shared_leftovers) against a fake
# run layout, with the Shadow-dependent steps stubbed. Guards the shared-dir
# sweep: an agent sidecar nobody added an archive line for must still reach
# archived_runs/<run_id>/shared/ instead of dying with cleanup_tmp_monero.
#
# Usage: ./scripts/test_archive_shared.sh [path/to/run_sim.sh]
set -uo pipefail
RUN_SIM="${1:-$(dirname "$0")/../run_sim.sh}"
T=$(mktemp -d "${TMPDIR:-/tmp}/archtest.XXXX")
trap 'rm -rf "$T"' EXIT
fails=0

extract() { awk -v fn="^$1\\(\\) \\{" '$0 ~ fn {f=1} f{print} f&&/^\}/{exit}' "$RUN_SIM"; }
eval "$(extract archive_results)"
eval "$(extract archive_transaction_registry)"
if grep -q '^archive_shared_leftovers()' "$RUN_SIM"; then eval "$(extract archive_shared_leftovers)"; fi
log_step(){ :; }; log_info(){ :; }; log_warn(){ echo "  WARN: $*"; }; log_ok(){ echo "  OK: $*"; }
for fn in archive_blockchain_snapshots archive_daemon_logs generate_summary_report \
          run_analysis cleanup_tmp_monero; do eval "$fn(){ :; }"; done

pass(){ echo "  PASS $*"; }
fail(){ echo "  FAIL $*"; fails=$((fails+1)); }
expect_file(){ [[ -f "$1" ]] && pass "$2" || fail "$2 (missing $1)"; }
expect_gone(){ [[ ! -e "$1" ]] && pass "$2" || fail "$2 (still there: $1)"; }

setup() {
    rm -rf "$T"/*; mkdir -p "$T/run/shadow.data" "$T/shared" "$T/run/shadow_output"
    RUN_DIR="$T/run"; ARCHIVE_DIR="$RUN_DIR"; DATA_DIR="$RUN_DIR/shadow.data"
    SHARED_DIR="$T/shared"; SHADOW_OUTPUT="$RUN_DIR/shadow_output"; RUN_ANALYZE=false
}

echo "== eclipse run: metrics + raw_probe + registry + monitoring"
setup
printf '{"t":1}\n{"t":2}\n{"t":3}\n' > "$SHARED_DIR/eclipse_metrics.jsonl"
mkdir -p "$SHARED_DIR/raw_probe" "$SHARED_DIR/monitoring"
echo x | gzip > "$SHARED_DIR/raw_probe/raw_eclipse-probe-001.jsonl.gz"
echo '{}' > "$SHARED_DIR/agent_registry.json"; : > "$SHARED_DIR/agent_registry.lock"
echo '{}' > "$SHARED_DIR/monitoring/final_report.json"
: > "$SHARED_DIR/monerosim_monitor.log"
archive_results
expect_file "$ARCHIVE_DIR/eclipse_metrics.jsonl" "eclipse_metrics.jsonl at run root"
[[ $(wc -l < "$ARCHIVE_DIR/eclipse_metrics.jsonl" 2>/dev/null) == 3 ]] && pass "3 polls intact" || fail "poll count"
expect_gone "$SHARED_DIR/eclipse_metrics.jsonl" "metrics moved, not copied"
expect_file "$ARCHIVE_DIR/shared/raw_probe/raw_eclipse-probe-001.jsonl.gz" "raw_probe swept into shared/"
expect_file "$ARCHIVE_DIR/transaction_registry/agent_registry.json" "registry still lands in transaction_registry/"
expect_gone "$ARCHIVE_DIR/shared/agent_registry.json" "registry not double-archived by sweep"
expect_file "$ARCHIVE_DIR/monitoring/final_report.json" "monitoring copied"
expect_gone "$ARCHIVE_DIR/shared/monitoring" "monitoring not double-archived by sweep"
expect_file "$SHARED_DIR/monitoring/final_report.json" "monitoring left in shared/ for later readers"
expect_gone "$ARCHIVE_DIR/shared/monerosim_monitor.log" "monitor log not double-archived"

echo "== plain run: nothing unexpected"
setup
echo '{}' > "$SHARED_DIR/agent_registry.json"
archive_results
expect_gone "$ARCHIVE_DIR/eclipse_metrics.jsonl" "no spurious metrics file"
expect_gone "$ARCHIVE_DIR/shared" "no shared/ dir when nothing left over"

echo "== unknown future sidecar"
setup
mkdir -p "$SHARED_DIR/some_new_agent"; echo hi > "$SHARED_DIR/some_new_agent/out.csv"; echo hi > "$SHARED_DIR/.hidden_state"
archive_results
expect_file "$ARCHIVE_DIR/shared/some_new_agent/out.csv" "unknown dir preserved"
expect_file "$ARCHIVE_DIR/shared/.hidden_state" "dotfile preserved"

echo "== $fails failure(s)"
exit $fails
