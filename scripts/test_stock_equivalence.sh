#!/usr/bin/env bash
# test_stock_equivalence.sh - scripts/stock_equivalence.sh against a fake
# project: a run_sim.sh that writes synthetic daemon logs, stubbed smoke
# assertions and a fake ~/.monerosim/bin.
#
#  1. refuses a config that stock monerod cannot run (native mining, --sim-* flags)
#  2. runs the scenario twice: as committed (stock), and with every
#     `daemon: monerod` rewritten to monerod-sim and nothing else changed
#  3. PASS (exit 0) when both runs pass the smoke assertions and every daemon
#     node's chain is identical over the common heights; a history row is
#     appended with the binary's sha256 and patch count
#  4. exit 1 naming the node and height when a chain diverges
#  5. a failing smoke assertion fails the test
#
# Usage: ./scripts/test_stock_equivalence.sh   (from the repo root or anywhere)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
T=$(mktemp -d "${TMPDIR:-/tmp}/stockeq.XXXX")
trap 'rm -rf "$T"' EXIT
fails=0
pass(){ echo "  PASS $*"; }
fail(){ echo "  FAIL $*"; fails=$((fails+1)); }

# --- fake project -----------------------------------------------------------
P="$T/proj"
mkdir -p "$P/scripts" "$P/test_configs" "$P/tests/baselines" "$P/archived_runs"
cp "$HERE/stock_equivalence.sh" "$P/scripts/" 2>/dev/null || { echo "scripts/stock_equivalence.sh missing"; exit 1; }
cp "$HERE/compare_chains.py" "$P/scripts/" 2>/dev/null || { echo "scripts/compare_chains.py missing"; exit 1; }
cp "$HERE/colors.sh" "$P/scripts/"
cat > "$P/test_configs/fake.yaml" <<'EOF'
general:
  stop_time: 1h
  daemon_defaults:
    log-level: 1
agents:
  miner-001:
    daemon: monerod
    hashrate: 20
  user-01:
    daemon: monerod
  relay-001:
    daemon: monerod
  monitor:
    script: agents.simulation_monitor
EOF
cat > "$P/test_configs/native.yaml" <<'EOF'
general:
  stop_time: 1h
  mining:
    mode: native
agents:
  miner-001:
    daemon: monerod
EOF
cat > "$P/test_configs/flagged.yaml" <<'EOF'
general:
  stop_time: 1h
  daemon_defaults:
    sim-subnet-dedup: 16
agents:
  relay-001:
    daemon: monerod
EOF
echo '{}' > "$P/tests/baselines/fake_metrics.json"
# smoke_assertions stub: exit $SMOKE_RC (default 0), log its args
printf '#!/usr/bin/env python3\nimport os, sys\nopen(sys.argv[0] + ".log", "a").write(" ".join(sys.argv[1:]) + "\\n")\nsys.exit(int(os.environ.get("SMOKE_RC", "0")))\n' \
    > "$P/scripts/smoke_assertions.py"
# fake run_sim.sh: one run dir per call, named after the config stem, with
# synthetic chains for every daemon in the config. The sim-binary run diverges
# at height 3 on relay-001 when FAKE_DIVERGE=1.
cat > "$P/run_sim.sh" <<'EOF'
#!/bin/bash
cfg=""; file=""
while [[ $# -gt 0 ]]; do
    case $1 in --config) cfg=$2; shift 2;; --run-dir-file) file=$2; shift 2;; *) shift;; esac
done
echo "ARGS: $ORIG" >/dev/null
stem=$(basename "$cfg" .yaml)
n=$(ls -d "$PWD"/archived_runs/* 2>/dev/null | wc -l)
run="$PWD/archived_runs/2026110${n}_000000_$stem"
mkdir -p "$run/daemon_logs"
cp "$cfg" "$run/input_config.yaml"
echo "Wall time: 1m 0s" > "$run/summary.txt"
[[ -n $file ]] && echo "$run" > "$file"
is_sim=0; grep -q 'daemon: monerod-sim' "$cfg" && is_sim=1
for node in $(awk '/^  [a-z0-9-]+:$/{name=$1} /daemon: monerod/{sub(":","",name); print name}' "$cfg"); do
    d="$run/daemon_logs/$node"; mkdir -p "$d"
    for h in 1 2 3 4; do
        id=$(printf '%064x' "$h")
        if [[ $is_sim == 1 && ${FAKE_DIVERGE:-0} == 1 && $node == relay-001 && $h -ge 3 ]]; then id=$(printf '%064x' $((h + 100))); fi
        printf '2000-01-01 00:00:0%s.000\t[P2P1]\tINFO\tblockchain\tsrc/x.cpp:1\t+++++ BLOCK SUCCESSFULLY ADDED\n' "$h" >> "$d/bitmonero.log"
        printf '2000-01-01 00:00:0%s.000\t[P2P1]\tINFO\tblockchain\tsrc/x.cpp:1\tid:\t<%s>\n' "$h" "$id" >> "$d/bitmonero.log"
        printf '2000-01-01 00:00:0%s.000\t[P2P1]\tINFO\tblockchain\tsrc/x.cpp:1\tHEIGHT %s, difficulty:\t1\n' "$h" "$h" >> "$d/bitmonero.log"
    done
done
echo "$cfg" >> "$PWD/run_sim.calls"
exit 0
EOF
chmod +x "$P/run_sim.sh" "$P/scripts/stock_equivalence.sh"
# fake installed binaries: HOME points here
export HOME="$T/home"
mkdir -p "$HOME/.monerosim/bin"
printf 'fake monerod-sim\n' > "$HOME/.monerosim/bin/monerod-sim"
printf 'binary: monerod-sim\npatch: a.patch\npatch_sha256: 1111\npatch: b.patch\npatch_sha256: 2222\n' > "$HOME/.monerosim/bin/monerod-sim.provenance"
SIM_SHA=$(sha256sum "$HOME/.monerosim/bin/monerod-sim" | cut -c1-64)

run_eq() { ( cd "$P" && ./scripts/stock_equivalence.sh "$@" ); }
reset() { rm -rf "$P/archived_runs"/* "$P/run_sim.calls" "$P/scripts/smoke_assertions.py.log" "$P/tests/baselines/stock_equivalence_history.csv"; }

echo "== refuses configs stock monerod cannot run"
reset; out=$(run_eq native 2>&1); rc=$?
[[ $rc -eq 4 ]] && pass "native mining: exit 4" || fail "native: rc $rc: $out"
[[ ! -f "$P/run_sim.calls" ]] && pass "no run started" || fail "a run was started"
reset; out=$(run_eq flagged 2>&1); rc=$?
[[ $rc -eq 4 ]] && pass "--sim-* in daemon_defaults: exit 4" || fail "flagged: rc $rc: $out"

echo "== identical chains -> PASS"
reset; out=$(run_eq fake 2>&1); rc=$?
[[ $rc -eq 0 ]] && pass "exit 0" || fail "rc $rc: $out"
calls=$(cat "$P/run_sim.calls" 2>/dev/null)
[[ $(wc -l <<< "$calls") -eq 2 ]] && pass "two runs" || fail "runs: $calls"
stock_cfg=$(sed -n 1p <<< "$calls"); sim_cfg=$(sed -n 2p <<< "$calls")
[[ "$stock_cfg" == *fake_stock.yaml ]] && pass "first run is the stock config ($(basename "$stock_cfg"))" || fail "first config $stock_cfg"
[[ "$sim_cfg" == *fake_sim.yaml ]] && pass "second run is the sim config ($(basename "$sim_cfg"))" || fail "second config $sim_cfg"
stock_run=$(ls -d "$P"/archived_runs/*_fake_stock); sim_run=$(ls -d "$P"/archived_runs/*_fake_sim)
if diff <(sed 's/daemon: monerod-sim$/daemon: monerod/' "$sim_run/input_config.yaml") "$stock_run/input_config.yaml" >/dev/null \
   && [[ $(grep -c 'daemon: monerod-sim$' "$sim_run/input_config.yaml") -eq 3 && $(grep -c 'daemon: monerod$' "$sim_run/input_config.yaml") -eq 0 ]]; then
    pass "sim config = stock config with every daemon: monerod -> monerod-sim"
else
    fail "sim config rewrite wrong"; diff "$stock_run/input_config.yaml" "$sim_run/input_config.yaml"
fi
diff "$stock_run/input_config.yaml" "$P/test_configs/fake.yaml" >/dev/null && pass "stock config unchanged" || fail "stock config differs from test_configs/fake.yaml"
[[ $(grep -c . "$P/scripts/smoke_assertions.py.log") -eq 2 ]] && pass "smoke assertions ran on both runs" || fail "assertions log: $(cat "$P/scripts/smoke_assertions.py.log" 2>&1)"
[[ "$out" == *"identical over 4 common heights"* ]] && pass "reports identical chains" || fail "no identical report: $out"
[[ "$out" == *"3 nodes"* || "$out" == *"3 daemon"* ]] && pass "compared 3 nodes" || fail "node count missing: $out"
H="$P/tests/baselines/stock_equivalence_history.csv"
if [[ -f "$H" ]]; then
    row=$(tail -1 "$H")
    [[ "$row" == *",fake,PASS,"* ]] && pass "history row: PASS" || fail "history row: $row"
    [[ "$row" == *"$SIM_SHA"* ]] && pass "history row has the binary sha256" || fail "no sha256 in: $row"
    [[ "$row" == *",2,"* ]] && pass "history row has the patch count (2)" || fail "no patch count in: $row"
    [[ $(head -1 "$H") == date,* ]] && pass "csv header" || fail "header: $(head -1 "$H")"
else
    fail "no history csv at $H"
fi

echo "== divergent chain -> FAIL, names node and height"
reset; out=$(FAKE_DIVERGE=1 run_eq fake 2>&1); rc=$?
[[ $rc -eq 1 ]] && pass "exit 1" || fail "rc $rc"
[[ "$out" == *relay-001* && "$out" == *"height 3"* ]] && pass "names relay-001 and height 3" || fail "report: $out"
[[ "$out" == *"stock against stock"* ]] && pass "says how to check for noise" || fail "no noise hint: $out"
row=$(tail -1 "$P/tests/baselines/stock_equivalence_history.csv" 2>/dev/null)
[[ "$row" == *",fake,FAIL,"* && "$row" == *"relay-001@3"* ]] && pass "history row: FAIL with relay-001@3" || fail "history row: $row"

echo "== smoke assertion failure -> FAIL"
reset; out=$(SMOKE_RC=1 run_eq fake 2>&1); rc=$?
[[ $rc -eq 1 ]] && pass "exit 1" || fail "rc $rc"
[[ "$out" == *"smoke assertions"* ]] && pass "names the assertions" || fail "report: $out"

echo
if (( fails == 0 )); then echo "ALL PASS"; else echo "$fails FAILED"; exit 1; fi
