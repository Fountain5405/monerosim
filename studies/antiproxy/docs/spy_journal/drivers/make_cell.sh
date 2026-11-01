#!/bin/bash
# Generate an X0 cell on any box as if on phantom: pins the two host inputs of the user stagger
# (phantom's ~/.monerosim/calibration.json and its 32 cores via MONEROSIM_CORES) and prints the
# yaml's md5 for the journal. Usage: make_cell.sh <make_lean.py args...>
# Verified 2026-10-24 on the control box: lean_legacy_none_h71_k1_s12345 -> 8a79b809 and
# lean_24_none_h300_k42_w24h_m1_n600_fx_s12345 -> dd1f63eb, phantom's bytes.
set -u
PHANTOM_CAL_MD5=e5276ee06c11
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
cal=$HOME/.monerosim/calibration.json
[ "$(md5sum "$cal" 2>/dev/null | cut -c1-12)" = "$PHANTOM_CAL_MD5" ] \
  || { echo "make_cell: $cal is not phantom's calibration (md5 $PHANTOM_CAL_MD5); copy it first" >&2; exit 2; }
cd "$REPO" || exit 1
out=$(MONEROSIM_CORES=32 venv/bin/python -I test_configs/x0/make_lean.py "$@") || exit $?
echo "$out"
cell=$(echo "$out" | grep -oE '[^ ]+/cells/[^ ]+\.yaml' | tail -1)
[ -n "$cell" ] && md5sum "$cell"
