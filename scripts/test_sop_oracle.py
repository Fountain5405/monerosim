"""scripts/sop_oracle.py: the nine hand-worked cases and log/CLI plumbing.

docs/20260930_sop_conformance.md: diff = 1216 everywhere, unit = 76,
h0 = 994, hf = 1000, k = 3, w = 16 (k*w = 48), d_ms = 5000, unless a case
overrides one of these.
"""
from scripts.sop_oracle import check_log, compare, decide, main, parse_log_line

DIFF = "1216"
UNIT = 76
H0, HF, K, W, D_MS = 994, 1000, 3, 16, 5000


def blk(h, seen=None, n_sh=0, shares=None, diff=DIFF):
    b = {"h": h, "id": "x" * 8, "diff": diff, "seen": seen, "n_sh": n_sh}
    if shares is not None:
        b["shares"] = shares
    elif n_sh:
        b["shares"] = [{"id": "s%d" % i, "seen": None} for i in range(n_sh)]
    return b


def sh(seen):
    return {"id": "s", "seen": seen}


def rec(alt, main, mode="rejudge", reinsert=False, h0=H0, hf=HF, top=None,
        w=W, k=K, d_ms=D_MS):
    return {"v": 1, "mode": mode, "reinsert": reinsert, "h0": h0, "hf": hf,
            "top": top if top is not None else main[-1]["h"], "w": w, "k": k,
            "d_ms": d_ms, "alt": alt, "main": main}


# --- Case 1: objective, shares decide -------------------------------------

def test_case1_objective_shares_decide():
    alt = [blk(1000 + i, n_sh=n) for i, n in enumerate([8, 8, 9, 8, 9, 8, 9])]
    main = [blk(1000 + i, n_sh=15) for i in range(6)]
    d = decide(rec(alt, main, top=1005))
    assert d["nf"] == 66
    assert d["regime"] == "objective"
    assert d["w_alt"] == 5016
    assert d["w_main"] == 7296
    assert d["expected"] == "KEEP"


# --- Case 2: subjective, displaced prefix (both modes) ----------------------

def _case2_alt_main():
    alt = [blk(1000, seen=0, shares=[sh(-60000) for _ in range(11)], n_sh=11)]
    main = [blk(1000 + i, seen=2_160_000 + i * 1000,
                shares=[sh(None) for _ in range(8)], n_sh=8) for i in range(7)]
    return alt, main


def test_case2_rejudge_switches():
    alt, main = _case2_alt_main()
    d = decide(rec(alt, main, mode="rejudge", top=1006))
    assert d["nf"] == 12
    assert d["regime"] == "subjective"
    assert d["w_alt"] == 912
    assert d["w_main"] == 532
    assert d["expected"] == "SWITCH"
    assert d["skip"] is False


def test_case2_whole_branch_reinsert_is_skipped():
    alt, main = _case2_alt_main()
    d = decide(rec(alt, main, mode="whole_branch", reinsert=True, top=1006))
    # Same weights (SWITCH would be judged), but the record is skipped.
    assert d["expected"] == "SWITCH"
    assert d["skip"] is True


# --- Case 3: late alt block --------------------------------------------

def test_case3_late_alt_block_weighs_zero():
    main_seen = 1_000_000
    alt = [blk(1000, seen=main_seen + 6000, n_sh=3)]
    main = [blk(1000, seen=main_seen)]
    d = decide(rec(alt, main, top=1000))
    assert d["regime"] == "subjective"
    assert d["w_alt"] == 0


# --- Case 4: share timing edge ------------------------------------------

def test_case4_share_exactly_d_excluded_d_plus_1_included():
    main_seen = 100_000
    alt = [blk(1000, seen=main_seen,
                shares=[sh(main_seen - D_MS), sh(main_seen - D_MS - 1)], n_sh=2)]
    main = [blk(1000, seen=main_seen)]
    d = decide(rec(alt, main, top=1000))
    assert d["w_alt"] == UNIT * 2  # block + the one early-enough share


# --- Case 5: alt ahead of top --------------------------------------------

def test_case5_alt_ahead_uses_its_own_seen_as_main_seen():
    block_seen = 200_000
    alt = [blk(1007, seen=block_seen,
                shares=[sh(block_seen - D_MS), sh(block_seen - D_MS - 1)], n_sh=2)]
    main = [blk(1006, seen=190_000)]
    d = decide(rec(alt, main, top=1006))
    assert d["w_alt"] == UNIT * 2  # only the share seen more than d before counts


# --- Case 6: late joiner --------------------------------------------------

def test_case6_late_joiner_is_objective_despite_small_nf():
    alt = [blk(1000, n_sh=2)]
    main = [blk(1000)]
    d = decide(rec(alt, main, h0=1005, hf=1000, top=1000))
    assert d["nf"] == 3
    assert d["regime"] == "objective"


# --- Case 7: tie -----------------------------------------------------------

def test_case7_tie():
    alt = [blk(1000)]
    main = [blk(1000)]
    d = decide(rec(alt, main, top=1000))
    assert d["w_alt"] == d["w_main"] == UNIT
    assert d["expected"] == "TIE"


# --- Case 8: non-conforming share set --------------------------------------

def test_case8_non_conforming_set_counts_as_header_alone():
    alt = [blk(1000, n_sh=0)]
    main = [blk(1000)]
    d = decide(rec(alt, main, top=1000))
    assert d["nf"] == 1
    assert d["w_alt"] == UNIT


# --- Case 9: old block ------------------------------------------------------

def test_case9_old_block_weighs_plain_difficulty():
    alt = [blk(1840, n_sh=5)]
    main = [blk(1840, n_sh=5)]
    d = decide(rec(alt, main, top=2000))
    assert d["w_alt"] == int(DIFF)
    assert d["w_main"] == int(DIFF)


# --- parse_log_line ---------------------------------------------------------

def test_parse_log_line_round_trip():
    payload = {"v": 1, "mode": "rejudge", "reinsert": False, "h0": 994, "hf": 1000,
               "top": 1000, "w": 16, "k": 3, "d_ms": 5000,
               "alt": [blk(1000)], "main": [blk(1000)],
               "nf": 1, "regime": "subjective", "w_alt": "76", "w_main": "76",
               "tie": True, "tie_draw": "random", "result": "KEEP"}
    import json
    line = ("2000-01-01 00:36:32.117\t[RPC1]\tINFO\tblockchain\t"
             f"src/cryptonote_core/blockchain.cpp:2619\tSIM-SoP-DEC {json.dumps(payload)}   \n")
    assert parse_log_line(line) == payload
    assert parse_log_line("no marker here\n") is None


# --- compare(): each kind of mismatch ---------------------------------------

def _agreeing_case1_record():
    alt = [blk(1000 + i, n_sh=n) for i, n in enumerate([8, 8, 9, 8, 9, 8, 9])]
    main = [blk(1000 + i, n_sh=15) for i in range(6)]
    r = rec(alt, main, top=1005)
    r.update(nf=66, regime="objective", w_alt="5016", w_main="7296",
             tie=False, tie_draw=None, result="KEEP")
    return r


def test_compare_agrees_on_a_correct_record():
    assert compare(_agreeing_case1_record()) == []


def test_compare_flags_wrong_w_alt():
    r = _agreeing_case1_record()
    r["w_alt"] = "9999"
    msgs = compare(r)
    assert any("w_alt" in m for m in msgs)


def test_compare_flags_wrong_regime():
    r = _agreeing_case1_record()
    r["regime"] = "subjective"
    msgs = compare(r)
    assert any("regime" in m for m in msgs)


def test_compare_flags_tie_claimed_when_weights_differ():
    r = _agreeing_case1_record()
    r["tie"] = True
    r["tie_draw"] = "random"
    msgs = compare(r)
    assert any("tie" in m for m in msgs)


def test_compare_flags_result_contradicting_weights():
    r = _agreeing_case1_record()
    r["result"] = "SWITCH"  # weights say KEEP
    msgs = compare(r)
    assert any("result" in m for m in msgs)


def test_compare_flags_skipped_outside_whole_branch_reinsert():
    r = _agreeing_case1_record()
    r["skipped"] = True  # mode is "rejudge" by default
    msgs = compare(r)
    assert any("skipped" in m for m in msgs)


def test_compare_accepts_a_legitimate_whole_branch_skip():
    alt, main = _case2_alt_main()
    r = rec(alt, main, mode="whole_branch", reinsert=True, top=1006)
    r.update(skipped=True, result="KEEP")
    assert compare(r) == []


# --- check_log ---------------------------------------------------------

def test_check_log_counts_agreeing_and_disagreeing_records(tmp_path):
    import json
    good = _agreeing_case1_record()
    bad = _agreeing_case1_record()
    bad["w_alt"] = "1"
    log = tmp_path / "bitmonero.log"
    log.write_text("\n".join([
        f"x\tSIM-SoP-DEC {json.dumps(good)}",
        f"x\tSIM-SoP-DEC {json.dumps(bad)}",
        "x\tunrelated line",
    ]))
    report = check_log(log)
    assert report["decisions"] == 2
    assert report["mismatches"] == 1
    assert len(report["details"]) == 1
    assert report["details"][0]["line"] == 2


# --- CLI exit codes ---------------------------------------------------------

def _write_node_log(run_dir, node, lines):
    d = run_dir / "daemon_logs" / node
    d.mkdir(parents=True)
    (d / "bitmonero.log").write_text("\n".join(lines))


def test_cli_exit_0_when_no_mismatches(tmp_path):
    import json
    good = _agreeing_case1_record()
    _write_node_log(tmp_path, "node1", [f"x\tSIM-SoP-DEC {json.dumps(good)}"])
    assert main(["check", str(tmp_path)]) == 0


def test_cli_exit_1_on_mismatch(tmp_path):
    import json
    bad = _agreeing_case1_record()
    bad["w_alt"] = "1"
    _write_node_log(tmp_path, "node1", [f"x\tSIM-SoP-DEC {json.dumps(bad)}"])
    assert main(["check", str(tmp_path)]) == 1


def test_cli_exit_2_when_no_decisions_found(tmp_path):
    _write_node_log(tmp_path, "node1", ["x\tnothing here"])
    assert main(["check", str(tmp_path)]) == 2
