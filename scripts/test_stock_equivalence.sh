#!/usr/bin/env bash
# test_stock_equivalence.sh - scripts/stock_equivalence.sh against a fake
# project: a run_sim.sh that writes synthetic archived chains, stubbed smoke
# assertions and a fake ~/.monerosim/bin whose monerod serves the headers of
# the archive it is pointed at.
#
#  1. refuses a config that stock monerod cannot run (native mining, --sim-* flags)
#  2. runs the scenario twice: as committed (stock), and with every
#     `daemon: monerod` rewritten to monerod-sim and nothing else changed
#  3. PASS (exit 0) when both runs pass the smoke assertions and every archived
#     chain has the same block timeline; a history row is appended with the
#     binary's sha256 and patch count
#  4. exit 1 naming the chain, height and field when a timeline differs
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
cp "$HERE/compare_block_timeline.py" "$P/scripts/" 2>/dev/null || { echo "scripts/compare_block_timeline.py missing"; exit 1; }
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
# fake run_sim.sh: one run dir per call, named after the config stem, with an
# archived chain (data.mdb + the headers the fake monerod will serve) for
# miner-001 and relay-001. The sim-binary run's relay-001 chain has a
# different timestamp at height 3 when FAKE_DIVERGE=1; block hashes always
# differ between the two runs, as they do for real.
cat > "$P/run_sim.sh" <<'EOF'
#!/bin/bash
cfg=""; file=""
while [[ $# -gt 0 ]]; do
    case $1 in --config) cfg=$2; shift 2;; --run-dir-file) file=$2; shift 2;; *) shift;; esac
done
stem=$(basename "$cfg" .yaml)
n=$(ls -d "$PWD"/archived_runs/* 2>/dev/null | wc -l)
run="$PWD/archived_runs/2026110${n}_000000_$stem"
mkdir -p "$run/blockchain"
cp "$cfg" "$run/input_config.yaml"
echo "Wall time: 1m 0s" > "$run/summary.txt"
[[ -n $file ]] && echo "$run" > "$file"
is_sim=0; grep -q 'daemon: monerod-sim' "$cfg" && is_sim=1
for node in monero-miner-001 monero-relay-001; do
    d="$run/blockchain/$node"; mkdir -p "$d"; echo fake > "$d/data.mdb"
    python3 - "$d/headers.json" "$is_sim" "${FAKE_DIVERGE:-0}" "$node" <<'PY'
import json, sys
out, is_sim, diverge, node = sys.argv[1], sys.argv[2] == "1", sys.argv[3] == "1", sys.argv[4]
hs = []
for h in range(5):
    ts = h * 120
    if is_sim and diverge and node == "monero-relay-001" and h == 3:
        ts += 7
    hs.append({"height": h, "timestamp": ts, "major_version": 16, "minor_version": 16, "difficulty": 1,
               "cumulative_difficulty": h + 1, "num_txes": 1 if h else 0, "block_size": 85, "block_weight": 85,
               "nonce": h, "reward": 35, "hash": f"{h + (500 if is_sim else 0):064x}", "miner_tx_hash": f"{h + 1000:064x}"})
json.dump(hs, open(out, "w"))
PY
done
echo "$cfg" >> "$PWD/run_sim.calls"
exit 0
EOF
chmod +x "$P/run_sim.sh" "$P/scripts/stock_equivalence.sh"
# fake installed binaries: HOME points here. monerod serves the headers next
# to the data.mdb it is started on (compare_block_timeline.py copies the
# archived chain dir to a scratch data dir and starts monerod offline on it).
export HOME="$T/home"
mkdir -p "$HOME/.monerosim/bin"
cat > "$HOME/.monerosim/bin/monerod" <<'EOF'
#!/usr/bin/env python3
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
args = sys.argv[1:]
data_dir = args[args.index("--data-dir") + 1]
port = int(args[args.index("--rpc-bind-port") + 1])
headers = json.load(open(f"{data_dir}/fake/lmdb/headers.json"))
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        self._send({"height": len(headers), "status": "OK"})
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); req = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/get_height": return self._send({"height": len(headers), "status": "OK"})
        p = req.get("params", {})
        self._send({"jsonrpc": "2.0", "id": req.get("id"), "result": {"headers": headers[p["start_height"]:p["end_height"] + 1], "status": "OK"}})
HTTPServer(("127.0.0.1", port), H).serve_forever()
EOF
chmod +x "$HOME/.monerosim/bin/monerod"
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

echo "== same timeline -> PASS"
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
[[ "$out" == *"timeline identical over 5 common heights"* ]] && pass "reports the identical timeline" || fail "no timeline report: $out"
[[ "$out" == *"hash 0"* ]] && pass "reports that the hashes differ (not judged)" || fail "hash report missing: $out"
[[ "$out" == *"2 archived chains"* ]] && pass "compared 2 chains" || fail "chain count missing: $out"
H="$P/tests/baselines/stock_equivalence_history.csv"
if [[ -f "$H" ]]; then
    row=$(tail -1 "$H")
    [[ "$row" == *",fake,PASS,"* ]] && pass "history row: PASS" || fail "history row: $row"
    [[ "$row" == *"$SIM_SHA"* ]] && pass "history row has the binary sha256" || fail "no sha256 in: $row"
    [[ "$row" == *",2,2,,"* ]] && pass "history row: 2 patches, 2 chains, no difference" || fail "row fields: $row"
    [[ $(head -1 "$H") == date,* ]] && pass "csv header" || fail "header: $(head -1 "$H")"
else
    fail "no history csv at $H"
fi

echo "== timeline differs -> FAIL, names chain, height and field"
reset; out=$(FAKE_DIVERGE=1 run_eq fake 2>&1); rc=$?
[[ $rc -eq 1 ]] && pass "exit 1" || fail "rc $rc"
[[ "$out" == *"monero-relay-001: timeline DIFFERS at height 3: timestamp 360 vs 367"* ]] && pass "names relay-001, height 3, timestamp" || fail "report: $out"
[[ "$out" == *"monero-miner-001: timeline identical"* ]] && pass "miner-001 still identical" || fail "report: $out"
row=$(tail -1 "$P/tests/baselines/stock_equivalence_history.csv" 2>/dev/null)
[[ "$row" == *",fake,FAIL,"* && "$row" == *"monero-relay-001@3:timestamp=360/367"* ]] && pass "history row: FAIL with relay-001@3:timestamp" || fail "history row: $row"

echo "== smoke assertion failure -> FAIL"
reset; out=$(SMOKE_RC=1 run_eq fake 2>&1); rc=$?
[[ $rc -eq 1 ]] && pass "exit 1" || fail "rc $rc"
[[ "$out" == *"smoke assertions failed"* ]] && pass "names the assertions" || fail "report: $out"

echo
if (( fails == 0 )); then echo "ALL PASS"; else echo "$fails FAILED"; exit 1; fi
