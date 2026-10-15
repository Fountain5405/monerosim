"""Tests for scripts/sop_lateness_probe.py and sop_oracle.decide's nf_rule."""
import pytest

from scripts.sop_lateness_probe import both_ways, example_race, reverse
from scripts.sop_oracle import decide

UNIT = 1216 // 16


@pytest.mark.parametrize("rule", ["alt", "either"])
def test_example_race_switches_both_ways(rule):
    fwd, rev = both_ways(example_race(), rule)
    assert fwd["regime"] == rev["regime"] == "subjective"
    # On X: Y's two early shares count, X's three late ones don't.
    assert (fwd["w_alt"], fwd["w_main"], fwd["expected"]) == (3 * UNIT, 1 * UNIT, "SWITCH")
    # On Y: both sets of shares count against Y's later block.
    assert (rev["w_alt"], rev["w_main"], rev["expected"]) == (4 * UNIT, 3 * UNIT, "SWITCH")


@pytest.mark.parametrize("rule", ["alt", "either"])
def test_fixed_reference_does_not_cycle(rule):
    # Revised #146: both blocks are timed against X's seen time, on either
    # branch. Y is 4 s late (< d, so on time); its 2 shares are early, X's 3
    # are not (2-4 s before X <= d), so Y outweighs X from both sides.
    fwd, rev = both_ways(example_race(fixed_ref=True), rule)
    assert (fwd["w_alt"], fwd["w_main"], fwd["expected"]) == (3 * UNIT, 1 * UNIT, "SWITCH")
    assert (rev["w_alt"], rev["w_main"], rev["expected"]) == (1 * UNIT, 3 * UNIT, "KEEP")


def test_fixed_reference_late_block_weighs_zero_on_main_too():
    # A block that joined the main chain by a switch is still timed against
    # the original main block's seen time: 6 s after it is late (> d = 5 s).
    rec = example_race(fixed_ref=True)
    rec["alt"][0]["seen"] = 6000
    rev = decide(reverse(rec), "either")
    assert rev["w_main"] == 0


def test_null_ref_means_block_seen():
    rec = example_race(fixed_ref=True)
    for b in rec["alt"] + rec["main"]:
        b["ref"] = None
    d = decide(rec, "either")
    # Each block is its own reference, so neither is late. X's shares are
    # 2-4 s before X (late); Y's are 13-14 s before Y (on time): Y = 1 + 2,
    # X = 1 + 0.
    assert (d["w_alt"], d["w_main"]) == (3 * UNIT, 1 * UNIT)


def test_example_race_without_delay_gap_does_not_cycle():
    # With d = 0 every share seen before its reference counts on both sides,
    # so X (3 shares) beats Y (2 shares) from both sides.
    fwd, rev = both_ways(example_race(d_ms=0), "either")
    assert fwd["expected"] == "KEEP"
    assert rev["expected"] == "SWITCH"


def test_reverse_swaps_branches_and_moves_top():
    rec = example_race()
    rec["alt"][0]["h"] = 1001  # alt branch one block longer
    r = reverse(rec)
    assert r["main"] == rec["alt"] and r["alt"] == rec["main"]
    assert r["top"] == 1001 and r["reinsert"] is False


def _branch(n_blocks, n_sh, seen0, h0=1000):
    return [{"h": h0 + i, "id": f"b{i}", "diff": "1216", "seen": seen0 + i,
             "n_sh": n_sh, "shares": []} for i in range(n_blocks)]


def test_nf_rule_either_closes_window_when_main_reaches_kw():
    # alt holds 10 objects, main 6 blocks x (1 + 8) = 54 >= 48.
    rec = {"mode": "whole_branch", "reinsert": False, "h0": 994, "hf": 1000,
           "top": 1005, "w": 16, "k": 3, "d_ms": 5000,
           "alt": _branch(10, 0, 0), "main": _branch(6, 8, 0)}
    assert decide(rec, "alt")["regime"] == "subjective"
    assert decide(rec, "either")["regime"] == "objective"
    assert decide(rec)["regime"] == "subjective"  # no logged rule: formal "alt"
    rec["nf_rule"] = "either"                     # the daemon logged "either"
    assert decide(rec)["regime"] == "objective"
    assert decide(rec, "alt")["regime"] == "subjective"  # explicit rule wins


def test_nf_rule_rejects_unknown():
    with pytest.raises(ValueError):
        decide(example_race(), "both")
