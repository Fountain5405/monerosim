#!/bin/bash
# Run all Shadow simulations for 20260209_425d4 tests
set +e

TESTDIR="$(cd "$(dirname "$0")" && pwd)"
PROJDIR="$(dirname "$TESTDIR")"
SHADOW="/home/lever65/.local/bin/shadow"
RESULTS="$TESTDIR/simulation_results.txt"

cd "$PROJDIR"

echo "=== Shadow Simulation Test Suite — $(date) ===" > "$RESULTS"
echo "Shadow binary: $SHADOW" >> "$RESULTS"
echo "Commit: $(git rev-parse --short HEAD)" >> "$RESULTS"
echo "" >> "$RESULTS"

pass=0
fail=0
total_start=$(date +%s)

MONEROSIM="$PROJDIR/target/release/monerosim"

for shadow_dir in "$TESTDIR"/*_shadow; do
    name=$(basename "$shadow_dir" _shadow)
    yaml="$shadow_dir/shadow_agents.yaml"
    expanded="$TESTDIR/${name}.expanded.yaml"

    if [ ! -f "$yaml" ]; then
        echo "[$name] SKIP — no shadow_agents.yaml" | tee -a "$RESULTS"
        continue
    fi

    # Clean up previous shadow.data
    rm -rf "$PROJDIR/shadow.data"

    # Regenerate shadow config to refresh /tmp/monerosim_shared/ for this test
    if [ -f "$expanded" ]; then
        "$MONEROSIM" --config "$expanded" --output "$shadow_dir" > /dev/null 2>&1
    fi

    sim_time=$(grep 'stop_time' "$yaml" | head -1 | awk '{print $2}')
    host_count=$(grep -c 'network_node_id' "$yaml")

    echo "" >> "$RESULTS"
    echo "--- $name ---" >> "$RESULTS"
    echo "  sim_time=${sim_time}s, hosts=${host_count}" >> "$RESULTS"

    echo -n "[$name] (${sim_time}s sim, ${host_count} hosts) running... "
    start_ts=$(date +%s)

    output=$("$SHADOW" "$yaml" 2>&1)
    exit_code=$?

    end_ts=$(date +%s)
    elapsed=$((end_ts - start_ts))

    # Extract progress lines
    last_progress=$(echo "$output" | grep "^Progress:" | tail -1)

    if [ $exit_code -ne 0 ]; then
        echo "FAIL (${elapsed}s, shadow exit=$exit_code)" | tee -a "$RESULTS"
        echo "  result: FAIL in ${elapsed}s (shadow exit code $exit_code)" >> "$RESULTS"
        echo "$output" | grep -E "(ERROR|unexpected final state|FAIL)" | tail -10 >> "$RESULTS"
        ((fail++))
        continue
    fi

    # Shadow completed — now verify simulation results
    echo -n "analyzing... "
    analysis_output=$(python3 -m scripts.analyze_success_criteria --log-dir "$PROJDIR/shadow.data" 2>&1)
    analysis_exit=$?

    if [ $analysis_exit -eq 0 ]; then
        echo "PASS (${elapsed}s)" | tee -a "$RESULTS"
        echo "  result: PASS in ${elapsed}s" >> "$RESULTS"
        echo "  $last_progress" >> "$RESULTS"
        # Extract criteria lines from analysis
        echo "$analysis_output" | grep -E "^\s+•" >> "$RESULTS"
        ((pass++))
    else
        echo "FAIL (${elapsed}s, analysis failed)" | tee -a "$RESULTS"
        echo "  result: FAIL in ${elapsed}s (shadow OK, analysis failed)" >> "$RESULTS"
        echo "  $last_progress" >> "$RESULTS"
        echo "$analysis_output" | grep -E "(FAIL|FAILURE|•)" >> "$RESULTS"
        ((fail++))
    fi
done

total_end=$(date +%s)
total_elapsed=$((total_end - total_start))

# Clean up
rm -rf "$PROJDIR/shadow.data"

echo "" >> "$RESULTS"
echo "========================================" >> "$RESULTS"
echo "TOTAL: $((pass + fail)) simulations, $pass passed, $fail failed" >> "$RESULTS"
echo "Total wall time: ${total_elapsed}s" >> "$RESULTS"

echo ""
echo "========================================"
echo "TOTAL: $((pass + fail)) simulations, $pass passed, $fail failed"
echo "Total wall time: ${total_elapsed}s"
echo "Results: $RESULTS"
