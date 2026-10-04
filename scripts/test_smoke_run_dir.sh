#!/usr/bin/env bash
# test_smoke_run_dir.sh - smoke_test.sh must grade the run it started, not the
# newest directory under archived_runs/. Two concurrent smoke tests (or a smoke
# test beside any other run from the same checkout) used to grade the same run.
#
#  1. run_sim.sh's real allocation lines write the run dir to --run-dir-file.
#  2. smoke_test.sh, driven against a fake project whose run_sim.sh creates its
#     own run plus a NEWER decoy dir (a concurrent run), grades its own run;
#     propagates run_sim.sh's exit code when no run dir was created; exits 5
#     when run_sim.sh succeeded but reported nothing.
#
# Usage: ./scripts/test_smoke_run_dir.sh [path/to/run_sim.sh] [path/to/smoke_test.sh]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RUN_SIM="${1:-$HERE/../run_sim.sh}"
SMOKE="${2:-$HERE/smoke_test.sh}"
T=$(mktemp -d "${TMPDIR:-/tmp}/smokedirtest.XXXX")
trap 'rm -rf "$T"' EXIT
fails=0
pass(){ echo "  PASS $*"; }
fail(){ echo "  FAIL $*"; fails=$((fails+1)); }

echo "== run_sim.sh writes its allocated run dir to --run-dir-file"
# shellcheck disable=SC1091
source "$HERE/run_dir_lib.sh"
log_err(){ echo "  ERR: $*"; }; log_warn(){ echo "  WARN: $*"; }
snippet=$(awk '/RUN_ID=\$\(allocate_run_dir/{f=1} f{print} f&&/RUN_DIR_FILE/{seen=1} f&&seen&&/^    fi$/{exit}' "$RUN_SIM")
if [[ "$snippet" != *RUN_DIR_FILE* ]]; then
    fail "no --run-dir-file write after allocate_run_dir in $RUN_SIM"
else
    eval "alloc_part() { $snippet
}"
    ARCHIVE_BASE="$T/archive"; mkdir -p "$ARCHIVE_BASE"; RUN_NAME=fake; RUN_DIR_FILE="$T/run_dir"
    alloc_part
    got=$(cat "$RUN_DIR_FILE" 2>/dev/null)
    [[ -n "$got" && "$got" == "$RUN_DIR" && -d "$got" ]] \
        && pass "wrote $got" || fail "file holds '$got', run dir is '$RUN_DIR'"
fi

# A fake project: smoke_test.sh cds to its parent dir and runs ./run_sim.sh there.
P="$T/proj"
mkdir -p "$P/scripts" "$P/test_configs" "$P/tests/baselines" "$P/archived_runs"
cp "$SMOKE" "$P/scripts/smoke_test.sh"; cp "$HERE/colors.sh" "$P/scripts/colors.sh"
: > "$P/test_configs/fake.yaml"; echo '{}' > "$P/tests/baselines/fake_metrics.json"
for stub in smoke_assertions append_run_history; do
    printf '#!/usr/bin/env python3\nimport sys\nopen(sys.argv[0] + ".log", "a").write(" ".join(sys.argv[1:]) + "\\n")\n' \
        > "$P/scripts/$stub.py"
done
cat > "$P/run_sim.sh" <<'EOF'
#!/bin/bash
# FAKE_MODE: ok | early_fail | no_report
file=""
while [[ $# -gt 0 ]]; do [[ $1 == --run-dir-file ]] && file=$2; shift; done
own="$PWD/archived_runs/20261002_000000_fake"
if [[ $FAKE_MODE != early_fail ]]; then
    mkdir -p "$own"
    [[ $FAKE_MODE == ok && -n $file ]] && echo "$own" > "$file"
fi
sleep 0.05; mkdir -p "$PWD/archived_runs/20261002_000001_fake"; touch "$PWD/archived_runs/20261002_000001_fake"
[[ $FAKE_MODE == early_fail ]] && exit 3
exit 0
EOF
chmod +x "$P/run_sim.sh"

run_smoke() {
    rm -rf "$P/archived_runs"/* "$P/scripts"/*.py.log
    FAKE_MODE=$1 bash "$P/scripts/smoke_test.sh" fake > "$T/out" 2>&1
    echo $?
}

echo "== a newer decoy run beside our own: grade our own"
rc=$(run_smoke ok)
graded=$(grep -o -- '--run-dir [^ ]*' "$P/scripts/smoke_assertions.py.log" 2>/dev/null | head -1 | cut -d' ' -f2)
[[ "$graded" == "$P/archived_runs/20261002_000000_fake" ]] \
    && pass "assertions ran on our run" || fail "assertions ran on '${graded:-nothing}'"
[[ $rc == 0 ]] && pass "exit 0" || fail "exit $rc (expected 0)"

echo "== run_sim.sh fails before creating a run dir: propagate, grade nothing"
rc=$(run_smoke early_fail)
[[ $rc == 3 ]] && pass "exit 3 propagated" || fail "exit $rc (expected 3)"
[[ ! -e "$P/scripts/smoke_assertions.py.log" ]] && pass "nothing graded" || fail "graded $(cat "$P/scripts/smoke_assertions.py.log")"

echo "== run_sim.sh exits 0 without reporting a run dir: exit 5, grade nothing"
rc=$(run_smoke no_report)
[[ $rc == 5 ]] && pass "exit 5" || fail "exit $rc (expected 5)"
[[ ! -e "$P/scripts/smoke_assertions.py.log" ]] && pass "nothing graded" || fail "graded $(cat "$P/scripts/smoke_assertions.py.log")"

echo "== $fails failure(s)"
exit $fails
