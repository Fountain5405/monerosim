#!/usr/bin/env python3
"""Tests for tri-state success criteria (PASS / FAIL / N/A).

Guards the landmine that motivated the tri-state change: "n/a" is a truthy
string, so a bare all(criteria.values()) counts a skipped criterion as a pass
and can flip a failing run to passing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_sim_helpers import (  # noqa: E402
    applicable_criteria,
    criteria_verdict,
    criterion_mark,
)


def test_criterion_mark_tristate():
    assert criterion_mark(True) == "PASS"
    assert criterion_mark(False) == "FAIL"
    for na in ("n/a", "N/A", "na", "not_applicable"):
        assert criterion_mark(na) == "N/A", na


def test_na_is_truthy_so_naive_all_gives_a_false_pass():
    """The real hazard of tri-state values.

    A genuinely failing criterion still fails a naive all(), because False is
    falsy. The false pass appears when EVERY criterion is skipped: naive all()
    over only "n/a" strings returns True, reporting a run as fully passing when
    nothing was checked at all.
    """
    sc = {"transactions_created_broadcast": "n/a", "transactions_in_blocks": "n/a"}
    assert all(sc.values()) is True, "precondition: naive all() is fooled by n/a"
    assert criteria_verdict(sc) == "NO APPLICABLE CHECKS"

    mixed = {"blocks_created": False, "transactions_in_blocks": "n/a"}
    assert criteria_verdict(mixed) == "SOME CHECKS FAILED"


def test_applicable_criteria_drops_na():
    sc = {"a": True, "b": "n/a", "c": False}
    assert applicable_criteria(sc) == {"a": True, "c": False}


def test_verdict_all_applicable_passed():
    sc = {"blocks_created": True, "transactions_in_blocks": "n/a"}
    assert criteria_verdict(sc) == "ALL APPLICABLE CHECKS PASSED"


def test_verdict_all_passed_when_nothing_skipped():
    sc = {"blocks_created": True, "nodes_funded": True}
    assert criteria_verdict(sc) == "ALL CHECKS PASSED"


def test_verdict_no_applicable_checks():
    assert criteria_verdict({"a": "n/a", "b": "n/a"}) == "NO APPLICABLE CHECKS"


def test_no_tx_workload_run_is_not_reported_failed():
    """The 36-of-111 cohort: mining-only runs must not read as failures."""
    sc = {
        "blocks_created": True,
        "nodes_funded": True,
        "actual_blocks_propagated": True,
        "transactions_created_broadcast": "n/a",
        "transactions_in_blocks": "n/a",
    }
    assert criteria_verdict(sc) == "ALL APPLICABLE CHECKS PASSED"


def test_real_tx_failure_still_fails():
    """A run that SHOULD transact and did not must still fail."""
    sc = {
        "blocks_created": True,
        "nodes_funded": True,
        "actual_blocks_propagated": True,
        "transactions_created_broadcast": False,
        "transactions_in_blocks": False,
    }
    assert criteria_verdict(sc) == "SOME CHECKS FAILED"


def test_legacy_key_is_not_reused():
    """blocks_propagated must not reappear as the new propagation check."""
    from scripts.run_sim_helpers import CRITERIA_LABELS

    # blocks_propagated survives ONLY as a legacy rendering label, never as the
    # new propagation metric -- the two must stay distinct keys.
    assert CRITERIA_LABELS["blocks_propagated"] == "Blocks propagated"
    assert CRITERIA_LABELS["actual_blocks_propagated"] == "Blocks propagated (actual)"
    assert "nodes_funded" in CRITERIA_LABELS


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
