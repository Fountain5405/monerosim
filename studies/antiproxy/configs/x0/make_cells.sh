#!/usr/bin/env bash
# Expand x0_2024.scenario.yaml into the X0 cells (docs/20261018_spy_node_defenses.md
# §5.3): peer selection {legacy, 24} x ban list {none, half} x seeds. Writes
# cells/x0_<dedup>_<list>_s<seed>.yaml and, per seed, cells/banlist_s<seed>.txt
# (the spies' /24s, scripts/spy_ban_list.py). cells/ is machine-specific
# (absolute ban-list paths) and not committed.
#
# Usage: test_configs/x0/make_cells.sh [seed ...]     (default: 12345 23456 34567)
# Run one: ./run_sim.sh --config test_configs/x0/cells/x0_legacy_none_s12345.yaml --bootfast --ksm
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="$REPO/venv/bin/python"
SRC="$HERE/x0_2024.scenario.yaml"
OUT="$HERE/cells"
mkdir -p "$OUT"
seeds=("$@")
[[ ${#seeds[@]} -gt 0 ]] || seeds=(12345 23456 34567)

expand() {  # <dedup> <list: none|half> <seed> <banlist path> <out yaml>
    local tmp
    tmp="$(mktemp -p "$OUT" --suffix=.scenario.yaml)"
    sed -e "s|^\(  simulation_seed:\).*|\1 $3|" \
        -e "s|^\(    sim-subnet-dedup:\).*|\1 \"$1\"|" "$SRC" > "$tmp"
    if [[ $2 == none ]]; then
        sed -i -e '/^    daemon_options: {ban-list: "@BANLIST@"}$/d' \
               -e 's|, ban-list: "@BANLIST@"||' "$tmp"
    else
        sed -i -e "s|@BANLIST@|$4|" "$tmp"
    fi
    if grep -v '^\s*#' "$tmp" | grep -q "@BANLIST@"; then
        echo "unreplaced @BANLIST@ in $tmp" >&2; exit 1
    fi
    # --no-safe-tx-interval: without it the generator raises users' 300 s to
    # this box's calibrated "safe" interval (3412 s on the 32-thread box), and
    # users send ~2 txs each instead of ~30 (pilot 20261020_165536).
    "$PY" "$REPO/scripts/generate_config.py" --from "$tmp" -o "$5" --no-safe-tx-interval > /dev/null
    rm -f "$tmp"
}

for seed in "${seeds[@]}"; do
    ban="$OUT/banlist_s$seed.txt"
    expand legacy none "$seed" "" "$OUT/x0_legacy_none_s$seed.yaml"
    "$PY" "$REPO/scripts/spy_ban_list.py" "$OUT/x0_legacy_none_s$seed.yaml" -o "$ban"
    expand 24 none "$seed" "" "$OUT/x0_24_none_s$seed.yaml"
    expand legacy half "$seed" "$ban" "$OUT/x0_legacy_half_s$seed.yaml"
    expand 24 half "$seed" "$ban" "$OUT/x0_24_half_s$seed.yaml"
done
ls -1 "$OUT"
