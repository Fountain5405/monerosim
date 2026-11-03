#!/usr/bin/env bash
# test_clock_mode.sh - run_sim.sh's clock-mode flags and preflight.
#
# Drives the real argument loop (extracted from run_sim.sh) and the real
# check_clock_mode() with a fake Shadow binary:
#   no flag        -> bootfast (the default since v0.5.0)
#   --no-bootfast  -> Shadow's default clock charge
#   --bootfast     -> still accepted (explicit)
#   --allfast      -> allfast; any two different clock flags -> exit 1
#   preflight      -> implied bootfast on a Shadow without the busy-loop
#                     charge warns and falls back; explicit --bootfast exits 1
#
# Usage: ./scripts/test_clock_mode.sh   (from the repo root or anywhere)
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
T=$(mktemp -d "${TMPDIR:-/tmp}/clocktest.XXXX")
trap 'rm -rf "$T"' EXIT
fails=0
pass(){ echo "  PASS $*"; }
fail(){ echo "  FAIL $*"; fails=$((fails+1)); }

# The argument loop, verbatim, as a function: parse_args <args...>
ARG_LOOP=$(awk '/^while \[\[ \$# -gt 0 \]\]; do/{f=1} f{print} f&&/^done/{exit}' run_sim.sh)
[[ -n "$ARG_LOOP" ]] || { echo "could not extract the argument loop from run_sim.sh"; exit 1; }
eval "parse_args() { $ARG_LOOP
}"
eval "$(awk '/^check_clock_mode\(\) \{/{f=1} f{print} f&&/^\}/{exit}' run_sim.sh)"
type check_clock_mode >/dev/null 2>&1 || { echo "run_sim.sh has no check_clock_mode()"; }

YELLOW=""; NC=""
usage(){ exit 0; }
WARNS=""; ERRS=""; OKS=""
log_warn(){ WARNS+="$*"$'\n'; }
log_err(){ ERRS+="$*"$'\n'; }
log_info(){ :; }; log_ok(){ OKS+="$*"$'\n'; }

# Defaults as run_sim.sh declares them (the clock ones come from the script
# itself, so the test sees the real default).
defaults() {
    eval "$(grep -E '^(CLOCK_MODE|CLOCK_EXPLICIT)=' run_sim.sh | sed 's/ *#.*//')"
    CONFIG=""; RUN_NAME=""; REACHABLE=""; TURNOVER_SESSION=""; TURNOVER_DOWNTIME=""
    TURNOVER_MAX_SESSION=""; KSM_OPTIN=false; SHOW_MONITOR=true; RUN_ANALYZE=false
    DO_BUILD=true; BLOCKCHAIN_ARCHIVE_PCT=""; ARCHIVE_BASE=""; RUN_DIR_FILE=""
    PREFLIGHT_ONLY=false; NO_ARCHIVE=false; NO_CLEAN=false; ALLOW_SHARED_PATHS=false
    DATA_BASE=""; RAMDISK_REQUEST=""
    WARNS=""; ERRS=""; OKS=""
}
# parse <args...>: run the loop in this shell; echo nothing. exit 1 inside
# the loop must not kill the test, so conflicting-flag cases use parse_rc.
parse_rc() { ( defaults; parse_args "$@" ) >/dev/null 2>&1; }

echo "== parsing"
defaults; parse_args --config x.yaml
[[ "$CLOCK_MODE" == "bootfast" ]] && pass "default is bootfast" || fail "default is '$CLOCK_MODE'"
[[ "${CLOCK_EXPLICIT:-unset}" == "false" ]] && pass "default is not explicit" || fail "CLOCK_EXPLICIT='${CLOCK_EXPLICIT:-unset}'"

defaults; parse_args --config x.yaml --no-bootfast
[[ "$CLOCK_MODE" == "" ]] && pass "--no-bootfast -> Shadow default clock" || fail "--no-bootfast gave '$CLOCK_MODE'"
[[ "${CLOCK_EXPLICIT:-unset}" == "true" ]] && pass "--no-bootfast is explicit" || fail "CLOCK_EXPLICIT='${CLOCK_EXPLICIT:-unset}'"

defaults; parse_args --config x.yaml --bootfast
[[ "$CLOCK_MODE" == "bootfast" && "${CLOCK_EXPLICIT:-}" == "true" ]] && pass "--bootfast still accepted, explicit" || fail "--bootfast: mode '$CLOCK_MODE' explicit '${CLOCK_EXPLICIT:-unset}'"

defaults; parse_args --config x.yaml --allfast
[[ "$CLOCK_MODE" == "allfast" ]] && pass "--allfast" || fail "--allfast gave '$CLOCK_MODE'"

parse_rc --config x.yaml --bootfast --allfast; rc=$?
[[ $rc -eq 1 ]] && pass "--bootfast --allfast -> exit 1" || fail "--bootfast --allfast rc $rc"
parse_rc --config x.yaml --no-bootfast --allfast; rc=$?
[[ $rc -eq 1 ]] && pass "--no-bootfast --allfast -> exit 1" || fail "--no-bootfast --allfast rc $rc"
parse_rc --config x.yaml --allfast --no-bootfast; rc=$?
[[ $rc -eq 1 ]] && pass "--allfast --no-bootfast -> exit 1" || fail "--allfast --no-bootfast rc $rc"
parse_rc --config x.yaml --bootfast --bootfast; rc=$?
[[ $rc -eq 0 ]] && pass "--bootfast twice is fine" || fail "--bootfast --bootfast rc $rc"

echo "== preflight: check_clock_mode with a fake Shadow"
mk_shadow() {   # $1 = yes|no: does --help list --unblocked-vdso-busy-threshold
    SHADOW_BIN="$T/shadow_$1"
    if [[ "$1" == yes ]]; then
        printf '#!/bin/sh\necho "  --unblocked-vdso-busy-threshold <n>"\n' > "$SHADOW_BIN"
    else
        printf '#!/bin/sh\necho "  --parallelism <n>"\n' > "$SHADOW_BIN"
    fi
    chmod +x "$SHADOW_BIN"
}
# Runs check_clock_mode in this shell so CLOCK_MODE changes are visible;
# exits are caught by running the explicit case in a subshell.
mk_shadow yes; defaults; CLOCK_MODE=bootfast; CLOCK_EXPLICIT=false
check_clock_mode; rc=$?
[[ $rc -eq 0 && "$CLOCK_MODE" == "bootfast" ]] && pass "implied bootfast, Shadow has it: kept" || fail "rc $rc mode '$CLOCK_MODE'"
[[ "$OKS" == *bootfast* ]] && pass "logs the clock mode" || fail "no log_ok: '$OKS'"

mk_shadow no; defaults; CLOCK_MODE=bootfast; CLOCK_EXPLICIT=false
check_clock_mode; rc=$?
[[ $rc -eq 0 ]] && pass "implied bootfast, old Shadow: continues" || fail "rc $rc"
[[ "$CLOCK_MODE" == "" ]] && pass "falls back to the default clock" || fail "mode still '$CLOCK_MODE'"
[[ "$WARNS" == *bootfast* ]] && pass "warns" || fail "no warning: '$WARNS'"

mk_shadow no; defaults; CLOCK_MODE=bootfast; CLOCK_EXPLICIT=true
( check_clock_mode ) >/dev/null 2>&1; rc=$?
[[ $rc -eq 1 ]] && pass "explicit --bootfast, old Shadow: exit 1" || fail "rc $rc"

mk_shadow no; defaults; CLOCK_MODE=allfast; CLOCK_EXPLICIT=true
check_clock_mode; rc=$?
[[ $rc -eq 0 && "$CLOCK_MODE" == "allfast" ]] && pass "--allfast needs no Shadow support" || fail "rc $rc mode '$CLOCK_MODE'"

mk_shadow no; defaults; CLOCK_MODE=""; CLOCK_EXPLICIT=true
check_clock_mode; rc=$?
[[ $rc -eq 0 && "$CLOCK_MODE" == "" ]] && pass "--no-bootfast: rc 0, stays default" || fail "rc $rc mode '$CLOCK_MODE'"

echo
if (( fails == 0 )); then echo "ALL PASS"; else echo "$fails FAILED"; exit 1; fi
