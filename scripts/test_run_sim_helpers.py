"""Tests for scripts/run_sim_helpers.py.

Scope: the load-bearing pure functions and command handlers that run_sim.sh
depends on via `$(...)` command substitution - block-interval histogram math
with reorg dedupe, the two summary renderers (write-summary-report /
print-summary-kv), and the small numeric helpers. Handlers are driven directly
through the argparse layer (build_parser) so the exact stdout the shell parses
is exercised. No Shadow, no daemon, no live log tailing beyond a crafted file.
"""
import json

import pytest

from scripts.run_sim_helpers import (
    build_parser,
    _histogram_bucket,
    _count_char,
    _histogram_axis_label,
    HIST_WIDTH,
    SUBCOLS_PER_MIN,
)


def _run(capsys, argv):
    """Dispatch a subcommand through the real parser; return captured stdout."""
    args = build_parser().parse_args(argv)
    rc = args.func(args)
    out = capsys.readouterr().out
    return rc, out


# ---------------------------------------------------------------------------
# Pure histogram helpers.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("count, char", [
    (0, "0"), (-3, "0"), (1, "1"), (9, "9"),
    (10, "a"), (16, "g"), (17, "^"), (999, "^"),
])
def test_count_char(count, char):
    assert _count_char(count) == char


def test_histogram_bucket_15s_cells():
    # cells are 60/SUBCOLS_PER_MIN = 15s wide.
    assert _histogram_bucket(0) == 0
    assert _histogram_bucket(14) == 0
    assert _histogram_bucket(15) == 1
    assert _histogram_bucket(120) == 8      # 120s / 15 = column 8
    assert _histogram_bucket(-5) == 0       # negative clamps to 0


def test_histogram_bucket_overflow_clamps_to_last_column():
    assert _histogram_bucket(10_000_000) == HIST_WIDTH - 1


def test_histogram_axis_label_shape():
    axis = _histogram_axis_label()
    assert len(axis) == HIST_WIDTH
    assert axis[0] == "0"
    assert axis[SUBCOLS_PER_MIN] == "1"     # minute labels every Nth column
    assert set(axis) <= set("0123456789abcdefg-")


# ---------------------------------------------------------------------------
# hms-to-seconds
# ---------------------------------------------------------------------------
def test_hms_to_seconds(capsys):
    rc, out = _run(capsys, ["hms-to-seconds", "01:02:03"])
    assert rc == 0
    assert out.strip() == "3723"


# ---------------------------------------------------------------------------
# estimate-ramdisk-mb: max(2048, total * (100 + 10*hours))
# ---------------------------------------------------------------------------
def test_estimate_ramdisk_mb_floor(capsys):
    _, out = _run(capsys, ["estimate-ramdisk-mb", "--total-monerods", "10", "--sim-hours", "6.0"])
    # 10 * (100 + 60) = 1600 -> below 2048 floor.
    assert out.strip() == "2048"


def test_estimate_ramdisk_mb_scales_above_floor(capsys):
    _, out = _run(capsys, ["estimate-ramdisk-mb", "--total-monerods", "100", "--sim-hours", "6.0"])
    # 100 * (100 + 60) = 16000.
    assert out.strip() == "16000"


# ---------------------------------------------------------------------------
# chain-growth-stats: "max X mean Y median Z min W" with unit formatting.
# ---------------------------------------------------------------------------
def test_chain_growth_stats(capsys):
    _, out = _run(capsys, ["chain-growth-stats", "--deltas", "1048576,2097152,512,0"])
    # sorted [0,512,1048576,2097152]; mean=786560, median=(512+1048576)/2=524544.
    assert out.strip() == "max 2.0M  mean 768K  median 512K  min 0B"


def test_chain_growth_stats_empty_prints_nothing(capsys):
    rc, out = _run(capsys, ["chain-growth-stats", "--deltas", ""])
    assert rc == 0
    assert out == ""


# ---------------------------------------------------------------------------
# config-summary: "<total> <miners> <users> <relays> <fb_seeds>"
# ---------------------------------------------------------------------------
def test_config_summary_counts(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "general:\n"
        "  fallback_seeds: auto\n"
        "agents:\n"
        "  miner-001: {}\n"
        "  miner-002: {}\n"
        "  user-001: {}\n"
        "  relay-001: {}\n"
        "  miner-distributor: {}\n"
    )
    _, out = _run(capsys, ["config-summary", str(cfg)])
    # total=5, miners=2 (miner-0*), users=1, relays=1, fb_seeds=6 (auto).
    assert out.strip() == "5 2 1 1 6"


def test_config_summary_fallback_seeds_off(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    # NOTE: fallback_seeds must be the *quoted* string "off" - unquoted `off` is
    # parsed by YAML as boolean False, which config-summary's `(value or 'auto')`
    # coerces back to the 'auto' branch (6 seeds). This is exactly why
    # yaml_emit quotes bool-like string values on the way out.
    cfg.write_text(
        'general:\n  fallback_seeds: "off"\nagents:\n  miner-001: {}\n  user-001: {}\n'
    )
    _, out = _run(capsys, ["config-summary", str(cfg)])
    total, miners, users, relays, fb = out.strip().split()
    assert (total, miners, users, relays, fb) == ("2", "1", "1", "0", "0")


def test_extract_stop_time(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("general:\n  stop_time: 16h\nagents: {}\n")
    _, out = _run(capsys, ["extract-stop-time", str(cfg)])
    assert out.strip() == "16h"


# ---------------------------------------------------------------------------
# block-rate: histogram accumulation + reorg dedupe.
# ---------------------------------------------------------------------------
# A log where height 101 appears twice: first at +2m (real add) and again at
# +9m (reorg replay). Dedupe must keep the EARLIEST timestamp per height, so
# the 300s "interval" from the replay must NOT enter the histogram.
BLOCK_LOG = """\
2024-01-01 00:00:00.000\tstart
2024-01-01 00:00:10.000\tBLOCK SUCCESSFULLY ADDED
2024-01-01 00:00:10.000\tfoo HEIGHT 100, difficulty: 1000
2024-01-01 00:02:10.000\tBLOCK SUCCESSFULLY ADDED
2024-01-01 00:02:10.000\tfoo HEIGHT 101, difficulty: 1001
2024-01-01 00:04:10.000\tBLOCK SUCCESSFULLY ADDED
2024-01-01 00:04:10.000\tfoo HEIGHT 102, difficulty: 1002
2024-01-01 00:09:10.000\tBLOCK SUCCESSFULLY ADDED
2024-01-01 00:09:10.000\treorg-replay HEIGHT 101, difficulty: 1001
2024-01-01 00:10:00.000\ttail now line
"""


def _kv(out):
    """Parse KEY=VALUE / KEY="VALUE" lines into a dict."""
    d = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v.strip('"')
    return d


def test_block_rate_live_stats_no_state(tmp_path, capsys):
    log = tmp_path / "bitmonero.log"
    log.write_text(BLOCK_LOG)
    rc, out = _run(capsys, ["block-rate", "--log", str(log)])
    assert rc == 0
    kv = _kv(out)
    # LAST_HEIGHT is the last block event in log order (the replay of 101).
    assert kv["LAST_HEIGHT"] == "101"
    assert "RECENT_RATE_PER_MIN" in kv
    # No histogram emitted without a --state-file.
    assert "HISTOGRAM" not in kv


def test_block_rate_reorg_dedupe_histogram(tmp_path, capsys):
    log = tmp_path / "bitmonero.log"
    log.write_text(BLOCK_LOG)
    state = tmp_path / "state.json"
    rc, out = _run(capsys, ["block-rate", "--log", str(log), "--state-file", str(state)])
    assert rc == 0
    kv = _kv(out)
    # Only two real intervals (100->101, 101->102), both 120s. The replayed
    # 101 is deduped out, so total is 2 (not 3) and no 300s interval appears.
    assert kv["HISTOGRAM_TOTAL"] == "2"
    saved = json.loads(state.read_text())
    assert saved["last_seen_height"] == 102
    assert saved["recent_intervals"] == [120.0, 120.0]
    assert sum(saved["bucket_counts"]) == 2
    # both intervals land in the 120s bucket (column 8).
    assert saved["bucket_counts"][8] == 2


def test_block_rate_missing_log_is_silent_exit_0(tmp_path, capsys):
    rc, out = _run(capsys, ["block-rate", "--log", str(tmp_path / "nope.log")])
    assert rc == 0
    assert out == ""


# ---------------------------------------------------------------------------
# Summary renderers driven from a crafted final_report.json.
# ---------------------------------------------------------------------------
FINAL_REPORT = {
    "summary": {
        "success_criteria": {
            "blocks_created": True,
            "blocks_propagated": True,
            "transactions_created_broadcast": True,
            "transactions_in_blocks": False,
        },
        "total_nodes": 12,
        "avg_sync_percentage": 99.4,
        "max_height": 272,
        "total_blocks_mined": 271,
        "alert_count": 3,
        "total_transactions_created": 100,
        "total_transactions_in_blocks": 90,
    },
    "transaction_stats": {"tx_created_by_node": {"user-001": 5, "miner-001": 10}},
    "historical_data": [
        {"node_data": {
            "user-001": {"daemon": {"height": 272, "connections": 24},
                         "wallet": {"balance": 54_640_000_000_000, "pool_size": 2}},
            "miner-001": {"daemon": {"height": 265, "connections": 27},
                          "wallet": {"balance": 0, "pool_size": 0}},
        }}
    ],
}


@pytest.fixture
def report_file(tmp_path):
    p = tmp_path / "final_report.json"
    p.write_text(json.dumps(FINAL_REPORT))
    return p


def test_print_summary_kv(report_file, capsys):
    _, out = _run(capsys, ["print-summary-kv", "--report", str(report_file)])
    kv = _kv(out)
    assert kv["NODES"] == "12"
    assert kv["SYNC"] == "99"          # rounded to 0 dp
    assert kv["HEIGHT"] == "272"
    assert kv["BLOCKS"] == "271"
    assert kv["TX_CREATED"] == "100"
    assert kv["TX_IN_BLOCKS"] == "90"
    assert kv["ALERTS"] == "3"
    assert kv["ALL_PASS"] == "no"      # one FAIL sub-criterion
    assert kv["WALLETS_FUNDED"] == "1"  # only user-001 has balance > 0


def test_print_summary_kv_emits_one_criteria_line_each(report_file, capsys):
    _, out = _run(capsys, ["print-summary-kv", "--report", str(report_file)])
    criteria = [ln for ln in out.splitlines() if ln.startswith("CRITERIA=")]
    assert len(criteria) == 4
    assert "CRITERIA=Transactions in blocks: FAIL" in out


def test_write_summary_report_roundtrips_through_parse_summary(report_file, tmp_path, capsys):
    # The renderer's output is exactly what smoke_assertions.parse_summary reads,
    # so render -> parse must recover the key fields.
    from scripts.smoke_assertions import parse_summary

    out = tmp_path / "summary.txt"
    rc, _ = _run(capsys, [
        "write-summary-report",
        "--report", str(report_file),
        "--out", str(out),
        "--run-name", "testrun",
        "--wall-time", "1h 2m",
        "--exit-code", "0",
    ])
    assert rc == 0
    parsed = parse_summary(out)
    assert parsed["wall_time_seconds"] == 3720
    assert parsed["exit_code"] == 0
    assert parsed["nodes_online"] == 12
    assert parsed["block_height"] == 272
    assert parsed["all_success_criteria_pass"] is False
    assert parsed["per_agent_tx"] == {"miner-001": 10, "user-001": 5}
    assert parsed["per_node_height"] == {"miner-001": 265, "user-001": 272}
