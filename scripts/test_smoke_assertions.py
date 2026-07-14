"""Tests for scripts/smoke_assertions.py (Tier-2 archived-run assertions).

Scope: parse_summary (extract fields from a summary.txt) and the wall-time
branch of assert_metrics, pinned with small crafted fixtures plus one real
archived summary.txt if present. No Shadow, no daemon, no run execution.

The recently-fixed behavior being pinned: a "Wall time: unknown" line parses to
wall_time_seconds=None (not 0), and a wall_time_seconds_max assertion against a
None wall time FAILS rather than passing as an instant 0s run.
"""
from pathlib import Path

import pytest

from scripts.smoke_assertions import parse_summary, assert_metrics, Assertions


# A compact summary.txt covering every field parse_summary extracts. Format
# mirrors run_sim_helpers.cmd_write_summary_report output.
SUMMARY_TEXT = """\
============================================================
MONEROSIM SIMULATION SUMMARY
============================================================

Run:            testrun
Wall time:      1h 2m 3s
Exit code:      0

SUCCESS CRITERIA
----------------------------------------
  Blocks created                 PASS
  Blocks propagated              PASS
  Transactions broadcast         PASS
  Transactions in blocks         FAIL

  Result: SOME CHECKS FAILED

NETWORK
----------------------------------------
  Nodes online:     12
  Sync:             99%
  Block height:     272
  Blocks mined:     271
  Alerts:           3

TRANSACTIONS
----------------------------------------
  Created:          100
  In blocks:        90

  Created by:
    miner-001              10 txs
    user-001                5 txs
    user-002                7 txs

NODE STATUS (final)
----------------------------------------
  Node                  Height      Balance  Conns  Pool TXs
  miner-001                265            -     27         0
  user-001                 272    54.64 XMR     24         2
  user-002                 270    48.85 XMR     27         1

============================================================
"""


@pytest.fixture
def summary_file(tmp_path):
    p = tmp_path / "summary.txt"
    p.write_text(SUMMARY_TEXT)
    return p


# ---------------------------------------------------------------------------
# parse_summary field extraction
# ---------------------------------------------------------------------------
def test_parse_summary_scalar_fields(summary_file):
    d = parse_summary(summary_file)
    assert d["wall_time_seconds"] == 3723
    assert d["wall_time_str"] == "1h 2m 3s"
    assert d["exit_code"] == 0
    assert d["nodes_online"] == 12
    assert d["block_height"] == 272
    assert d["blocks_mined"] == 271
    assert d["alerts"] == 3
    assert d["tx_created"] == 100
    assert d["tx_in_blocks"] == 90


def test_parse_summary_success_criteria(summary_file):
    d = parse_summary(summary_file)
    assert d["success_criteria"] == {
        "blocks_created": True,
        "blocks_propagated": True,
        "transactions_created_broadcast": True,
        "transactions_in_blocks": False,
    }
    assert d["all_success_criteria_pass"] is False


def test_parse_summary_per_agent_tx(summary_file):
    d = parse_summary(summary_file)
    assert d["per_agent_tx"] == {"miner-001": 10, "user-001": 5, "user-002": 7}


def test_parse_summary_per_node_height(summary_file):
    d = parse_summary(summary_file)
    assert d["per_node_height"] == {"miner-001": 265, "user-001": 272, "user-002": 270}


def test_parse_summary_wall_time_unknown_is_none(tmp_path):
    # Recently-fixed: an unparseable wall-time line -> None, key present.
    text = SUMMARY_TEXT.replace("Wall time:      1h 2m 3s", "Wall time:      unknown")
    p = tmp_path / "summary.txt"
    p.write_text(text)
    d = parse_summary(p)
    assert d["wall_time_str"] == "unknown"
    assert d["wall_time_seconds"] is None


# ---------------------------------------------------------------------------
# assert_metrics: the wall-time None -> FAIL branch (recently fixed).
# ---------------------------------------------------------------------------
def test_wall_time_none_fails_max_assertion(tmp_path):
    text = SUMMARY_TEXT.replace("Wall time:      1h 2m 3s", "Wall time:      unknown")
    p = tmp_path / "summary.txt"
    p.write_text(text)
    parsed = parse_summary(p)
    a = Assertions()
    assert_metrics(parsed, {"wall_time_seconds_max": 100000}, a)
    # Even though the limit is huge, an unparseable wall time must FAIL, not
    # sneak through as a 0s "instant" run.
    assert a.failures == 1
    assert a.passes == 0


def test_wall_time_parseable_passes_when_under_limit(summary_file):
    parsed = parse_summary(summary_file)
    a = Assertions()
    assert_metrics(parsed, {"wall_time_seconds_max": 7200}, a)  # 3723 <= 7200
    assert a.failures == 0
    assert a.passes == 1


def test_assert_metrics_all_success_criteria_fail_reported(summary_file):
    parsed = parse_summary(summary_file)
    a = Assertions()
    assert_metrics(parsed, {"all_success_criteria_pass": True}, a)
    # fixture has one FAIL sub-criterion, so the assertion fails.
    assert a.failures == 1


def test_assert_metrics_wallets_funded_exact(summary_file):
    parsed = parse_summary(summary_file)
    a = Assertions()
    # 3 senders appear in the "Created by:" section.
    assert_metrics(parsed, {"wallets_funded_exact": 3}, a)
    assert a.failures == 0


def test_assert_metrics_height_range_uses_per_node_heights(summary_file):
    parsed = parse_summary(summary_file)
    a = Assertions()
    # heights 265/272/270 -> spread 7. Limit 10 passes, limit 5 fails.
    assert_metrics(parsed, {"all_nodes_within_height_range": 10}, a)
    assert a.failures == 0
    a2 = Assertions()
    assert_metrics(parsed, {"all_nodes_within_height_range": 5}, a2)
    assert a2.failures == 1


# ---------------------------------------------------------------------------
# Real archived summary.txt (if one is present) - format-drift guard.
# ---------------------------------------------------------------------------
REAL_SUMMARY = (
    Path(__file__).resolve().parent.parent
    / "archived_runs" / "20260609_153322_captest_cap4" / "summary.txt"
)


@pytest.mark.skipif(not REAL_SUMMARY.is_file(), reason="archived captest_cap4 run not present")
def test_parse_real_archived_summary():
    d = parse_summary(REAL_SUMMARY)
    assert d["wall_time_seconds"] == 38520          # "10h 42m"
    assert d["exit_code"] == 0
    assert d["all_success_criteria_pass"] is True
    assert d["nodes_online"] == 1011
    assert d["tx_created"] == 13688
    assert d["per_agent_tx"]["miner-001"] == 137
    # 5 miners + 200 users listed as senders.
    assert len(d["per_agent_tx"]) == 205
    # 1011 nodes in the final status table.
    assert len(d["per_node_height"]) == 1011
