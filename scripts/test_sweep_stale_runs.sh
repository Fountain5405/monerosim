#!/usr/bin/env bash
# test_sweep_stale_runs.sh - pins the classification rules of
# scripts/sweep_stale_runs.sh against a fake ROOT of monerosim-* dirs:
# live owner, dead owner, dead owner + .keep, generator namespace with and
# without daemon data, and a dir with no breadcrumb at all. Dry-run must
# delete nothing; --delete must remove exactly the stale ones; --include-kept
# widens to the kept ones.
#
# Usage: ./scripts/test_sweep_stale_runs.sh
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWEEP="$SCRIPT_DIR/sweep_stale_runs.sh"
# shellcheck source=run_dir_lib.sh
source "$SCRIPT_DIR/run_dir_lib.sh"
T=$(mktemp -d "${TMPDIR:-/tmp}/sweeptest.XXXX")
trap 'rm -rf "$T"' EXIT
fails=0
pass(){ echo "  PASS $*"; }
fail(){ echo "  FAIL $*"; fails=$((fails+1)); }
present(){ [[ -d "$T/monerosim-$1" ]] && pass "$1 still there ($2)" || fail "$1 was removed ($2)"; }
gone(){ [[ ! -d "$T/monerosim-$1" ]] && pass "$1 removed ($2)" || fail "$1 still there ($2)"; }

populate() {
    rm -rf "$T"/monerosim-*
    mkdir -p "$T"/monerosim-{live,dead,kept,gen_empty,gen_data,unknown}/shared
    write_owner_pid "$T/monerosim-live/.owner_pid"            # this shell: alive
    echo "999999 1" > "$T/monerosim-dead/.owner_pid"          # no such pid
    echo "999999 1" > "$T/monerosim-kept/.owner_pid"
    echo "kept by --no-clean: test" > "$T/monerosim-kept/.keep"
    echo "monerosim test" > "$T/monerosim-gen_empty/.generated_by"
    echo "monerosim test" > "$T/monerosim-gen_data/.generated_by"
    mkdir -p "$T/monerosim-gen_data/monero-relay-001"
}

echo "== dry run deletes nothing"
populate
out=$(bash "$SWEEP" "$T")
for d in live dead kept gen_empty gen_data unknown; do present "$d" "dry run"; done
grep -q "^live .*monerosim-live" <<<"$out" && pass "live classified" || fail "live classified: $out"
grep -q "^stale .*monerosim-dead" <<<"$out" && pass "dead classified stale" || fail "dead classified"
grep -q "^kept .*monerosim-kept" <<<"$out" && pass "kept classified" || fail "kept classified"
grep -q "^stale .*monerosim-gen_empty" <<<"$out" && pass "empty generator ns classified stale" || fail "gen_empty classified"
grep -q "^kept .*monerosim-gen_data" <<<"$out" && pass "generator ns with daemon data classified kept" || fail "gen_data classified"
grep -q "^skip .*monerosim-unknown" <<<"$out" && pass "unknown skipped" || fail "unknown skipped"
grep -q "^2 stale dir" <<<"$out" && pass "2 candidates counted" || fail "count line: $(grep 'stale dir' <<<"$out")"

echo "== --delete removes only stale"
populate
bash "$SWEEP" --delete "$T" > /dev/null
gone dead "--delete"; gone gen_empty "--delete"
present live "--delete"; present kept "--delete"; present gen_data "--delete"; present unknown "--delete"

echo "== --delete --include-kept also removes kept"
populate
bash "$SWEEP" --delete --include-kept "$T" > /dev/null
gone dead "include-kept"; gone gen_empty "include-kept"; gone kept "include-kept"; gone gen_data "include-kept"
present live "include-kept"; present unknown "include-kept"

echo "== $fails failure(s)"
exit $fails
