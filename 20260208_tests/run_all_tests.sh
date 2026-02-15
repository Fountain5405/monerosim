#!/bin/bash
# Run all scenario tests and capture results
set +e  # Don't exit on error — we want all tests to run

TESTDIR="$(cd "$(dirname "$0")" && pwd)"
PROJDIR="$(dirname "$TESTDIR")"
RESULTS="$TESTDIR/results.txt"

cd "$PROJDIR"

echo "=== Relay Node Test Suite — $(date) ===" > "$RESULTS"
echo "" >> "$RESULTS"

pass=0
fail=0

run_test() {
    local name="$1"
    local scenario="$2"
    local expanded="$TESTDIR/${name}.expanded.yaml"
    local shadow_dir="$TESTDIR/${name}_shadow"

    echo "--- $name ---" >> "$RESULTS"
    echo -n "[$name] expand... "

    # Step 1: Expand scenario
    if python3 scripts/generate_config.py --from "$scenario" -o "$expanded" 2>>"$RESULTS"; then
        echo "OK" | tee -a "$RESULTS"
    else
        echo "FAIL (expand)" | tee -a "$RESULTS"
        ((fail++))
        echo "" >> "$RESULTS"
        return
    fi

    # Step 2: Run monerosim to generate Shadow YAML
    echo -n "[$name] monerosim... "
    if target/release/monerosim --config "$expanded" --output "$shadow_dir" 2>>"$RESULTS"; then
        echo "OK" | tee -a "$RESULTS"
    else
        echo "FAIL (monerosim)" | tee -a "$RESULTS"
        ((fail++))
        echo "" >> "$RESULTS"
        return
    fi

    # Step 3: Validate — count processes per host
    echo "[$name] Process counts:" >> "$RESULTS"
    python3 -c "
import yaml, sys
with open('${shadow_dir}/shadow_agents.yaml') as f:
    config = yaml.safe_load(f)
for host_id, host in sorted(config['hosts'].items()):
    n = len(host.get('processes', []))
    print(f'  {host_id}: {n} process(es)')
" >> "$RESULTS" 2>&1

    # Step 4: Validate — check relay hosts have exactly 1 process
    echo -n "[$name] relay check... "
    relay_ok=$(python3 -c "
import yaml
with open('${shadow_dir}/shadow_agents.yaml') as f:
    config = yaml.safe_load(f)
ok = True
for host_id, host in config['hosts'].items():
    if 'relay' in host_id:
        n = len(host.get('processes', []))
        if n != 1:
            print(f'FAIL: {host_id} has {n} processes, expected 1')
            ok = False
if ok:
    print('OK')
" 2>&1)
    echo "$relay_ok" | tee -a "$RESULTS"

    # Step 5: Validate — check agent registry
    echo "[$name] Agent registry relay entries:" >> "$RESULTS"
    python3 -c "
import json
with open('/tmp/monerosim_shared/agent_registry.json') as f:
    reg = json.load(f)
for a in reg['agents']:
    if 'relay' in a['id']:
        wallet = a.get('wallet', False)
        script = a.get('user_script')
        wrpc = a.get('wallet_rpc_port')
        status = 'OK' if (not wallet and not script and not wrpc) else 'UNEXPECTED'
        print(f'  {a[\"id\"]}: wallet={wallet}, script={script}, wallet_rpc_port={wrpc} [{status}]')
" >> "$RESULTS" 2>&1

    # Step 6: Run validator
    echo "[$name] Validator:" >> "$RESULTS"
    python3 -c "
from scripts.ai_config.validator import ConfigValidator
v = ConfigValidator()
report = v.validate_file('${expanded}')
print(f'  relay_count={report.relay_count}, miner_count={report.miner_count}, user_count={report.user_count}')
print(f'  errors={len(report.errors)}, warnings={len(report.warnings)}')
for e in report.errors:
    print(f'  ERROR: {e}')
" >> "$RESULTS" 2>&1

    ((pass++))
    echo "" >> "$RESULTS"
}

# Tests 1-6, 8: scenario files
for f in "$TESTDIR"/*.scenario.yaml; do
    name=$(basename "$f" .scenario.yaml)
    run_test "$name" "$f"
done

# Test 7: generate_config.py --relay-nodes CLI flag (not a scenario file)
echo "--- 07_cli_relay_nodes ---" >> "$RESULTS"
echo -n "[07_cli_relay_nodes] generate... "
expanded="$TESTDIR/07_cli_relay_nodes.expanded.yaml"
shadow_dir="$TESTDIR/07_cli_relay_nodes_shadow"

if python3 scripts/generate_config.py --agents 10 --relay-nodes 5 --duration 2h -o "$expanded" 2>>"$RESULTS"; then
    echo "OK" | tee -a "$RESULTS"
else
    echo "FAIL" | tee -a "$RESULTS"
    ((fail++))
fi

echo -n "[07_cli_relay_nodes] monerosim... "
if target/release/monerosim --config "$expanded" --output "$shadow_dir" 2>>"$RESULTS"; then
    echo "OK" | tee -a "$RESULTS"
else
    echo "FAIL" | tee -a "$RESULTS"
    ((fail++))
fi

echo "[07_cli_relay_nodes] Process counts:" >> "$RESULTS"
python3 -c "
import yaml
with open('${shadow_dir}/shadow_agents.yaml') as f:
    config = yaml.safe_load(f)
for host_id, host in sorted(config['hosts'].items()):
    n = len(host.get('processes', []))
    print(f'  {host_id}: {n} process(es)')
" >> "$RESULTS" 2>&1

relay_ok=$(python3 -c "
import yaml
with open('${shadow_dir}/shadow_agents.yaml') as f:
    config = yaml.safe_load(f)
ok = True
for host_id, host in config['hosts'].items():
    if 'relay' in host_id:
        n = len(host.get('processes', []))
        if n != 1:
            print(f'FAIL: {host_id} has {n} processes, expected 1')
            ok = False
if ok:
    print('OK')
" 2>&1)
echo "[07_cli_relay_nodes] relay check... $relay_ok" | tee -a "$RESULTS"

echo "[07_cli_relay_nodes] Validator:" >> "$RESULTS"
python3 -c "
from scripts.ai_config.validator import ConfigValidator
v = ConfigValidator()
report = v.validate_file('${expanded}')
print(f'  relay_count={report.relay_count}, miner_count={report.miner_count}, user_count={report.user_count}')
print(f'  errors={len(report.errors)}, warnings={len(report.warnings)}')
" >> "$RESULTS" 2>&1

((pass++))
echo "" >> "$RESULTS"

# Summary
echo "========================================" >> "$RESULTS"
echo "TOTAL: $((pass + fail)) tests, $pass passed, $fail failed" >> "$RESULTS"
echo "" >> "$RESULTS"

echo ""
echo "========================================"
echo "TOTAL: $((pass + fail)) tests, $pass passed, $fail failed"
echo "Results: $RESULTS"
