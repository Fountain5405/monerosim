"""scripts/sop_oracle.py: the nine hand-worked cases and log/CLI plumbing.

docs/20260930_sop_conformance.md: diff = 1216 everywhere, unit = 76,
h0 = 994, hf = 1000, k = 3, w = 16 (k*w = 48), d_ms = 5000, unless a case
overrides one of these.
"""
import json

from scripts.sop_oracle import check_log, compare, decide, main, parse_log_line, pool_count

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


def test_v3_h0_at_last_common_block_is_objective():
    # h0 = 999 is the last common block when the first alt block is 1000.
    # Revised #146 needs h0 < h_f (last common block): objective from v3 on;
    # v1/v2 logs tested h0 < first alt block.
    blk = {"h": 1000, "id": "a", "diff": "1216", "seen": 0, "n_sh": 0, "shares": []}
    rec = {"mode": "whole_branch", "reinsert": False, "h0": 999, "hf": 1000,
           "top": 1000, "w": 16, "k": 3, "d_ms": 5000, "nf_rule": "either",
           "alt": [dict(blk)], "main": [dict(blk, id="m")]}
    assert decide(dict(rec, v=2))["regime"] == "subjective"
    assert decide(dict(rec, v=3, online=True))["regime"] == "objective"
    assert decide(dict(rec, v=3, online=True, h0=998))["regime"] == "subjective"


def test_v3_objective_until_online():
    # From v3 a node that has not come online yet (no first sync, no block
    # mined) judges objectively: its receive times are download times. v1/v2
    # records predate the field; a v3 record without it is malformed.
    import pytest
    blk = {"h": 1000, "id": "a", "diff": "1216", "seen": 0, "n_sh": 0, "shares": []}
    rec = {"mode": "whole_branch", "reinsert": False, "h0": 998, "hf": 1000,
           "top": 1000, "w": 16, "k": 3, "d_ms": 5000, "nf_rule": "either",
           "alt": [dict(blk)], "main": [dict(blk, id="m")]}
    assert decide(dict(rec, v=3, online=True))["regime"] == "subjective"
    assert decide(dict(rec, v=3, online=False))["regime"] == "objective"
    assert decide(dict(rec, v=2, online=False))["regime"] == "subjective"
    with pytest.raises(KeyError):
        decide(dict(rec, v=3))


D4 = 5000
DIFF4 = 1600            # unit 100


def blk4(h, n_sh=0, seen=1000, ref=1000, diff=DIFF4):
    return {"h": h, "id": f"{h:064x}", "diff": str(diff), "seen": seen, "ref": ref,
            "n_sh": n_sh, "shares": [{"id": f"s{h}_{i}", "seen": seen - 10000} for i in range(n_sh)]}


def sh4(slot, seen=500, pow_ok=True, i=0):
    return {"id": f"p{slot}_{i}", "slot": slot, "seen": seen, "pow_ok": pow_ok}


def rec_v4(alt, main, pool_alt=(), pool_main=(), h0=10, online=True, major=16, **kw):
    hf = alt[0]["h"]
    r = {"v": 4, "mode": "whole_branch", "reinsert": False, "skipped": False, "h0": h0,
         "online": online, "hf": hf, "top": main[-1]["h"] if main else hf - 1,
         "w": W, "k": K, "d_ms": D4, "alt": alt, "main": main, "major": major,
         "pool_alt": list(pool_alt), "pool_main": list(pool_main),
         "pool_diff_alt": str(DIFF4), "pool_diff_main": str(DIFF4)}
    r.update(kw)
    return r


def test_pool_count_slot_rule():
    assert pool_count([sh4(16), sh4(17), sh4(18)], 16) == 3


def test_v4_duplicate_slot_counts_once():
    assert pool_count([sh4(16, 500, i=0), sh4(16, 400, i=1), sh4(17)], 16) == 2
    assert pool_count([sh4(16, 500, i=0), sh4(16, 400, i=1), sh4(17)], 16, rule="all") == 3


def test_v4_slot_gap_stops_the_run():
    assert pool_count([sh4(16), sh4(18), sh4(19)], 16) == 1


def test_v4_bad_pow_is_not_in_the_pool():
    assert pool_count([sh4(16, pow_ok=False), sh4(17)], 16) == 0


def test_v4_first_block_excluded_from_window():
    # alt: first block 40 objects, then two blocks of 16 = 32 above h_f+1 -> objective
    alt = [blk4(100, 39), blk4(101, 15), blk4(102, 15)]
    main = [blk4(100, 15), blk4(101, 15)]
    d = decide(rec_v4(alt, main))
    assert d["n_alt"] == 32 and d["n_main"] == 16
    assert d["regime"] == "objective"
    # one object fewer above the first block: subjective
    alt2 = [blk4(100, 39), blk4(101, 15), blk4(102, 14)]
    assert decide(rec_v4(alt2, main))["regime"] == "subjective"


def test_v4_pool_shares_turn_switch_into_keep():
    alt = [blk4(100, 15), blk4(101, 15), blk4(102, 15)]            # 48 objects
    main = [blk4(100, 15), blk4(101, 15)]                           # 32 objects, 16 above h_f+1
    assert decide(rec_v4(alt, main))["expected"] == "SWITCH"      # 4800 vs 3200
    pool = [sh4(16 + i) for i in range(17)]                        # 17 counted -> 3200 + 1700
    d = decide(rec_v4(alt, main, pool_main=pool))
    assert d["regime"] == "objective" and d["pool_main_counted"] == 17
    assert d["w_main"] == 4900 and d["expected"] == "KEEP"


def test_v4_pool_shares_ignored_when_subjective():
    alt = [blk4(100, 2, seen=9000)]                                # late, inside the window
    main = [blk4(100, 2)]
    d = decide(rec_v4(alt, main, pool_main=[sh4(19)], pool_alt=[sh4(19)]))
    assert d["regime"] == "subjective"
    assert d["pool_main_counted"] == 0 and d["pool_alt_counted"] == 0


def test_v4_nakamoto_past_10w():
    alt = [blk4(100 + i) for i in range(161)]
    main = [blk4(100 + i, 15) for i in range(160)]
    d = decide(rec_v4(alt, main, pool_main=[sh4(16)]))
    assert d["regime"] == "nakamoto"
    assert d["w_alt"] == 161 * DIFF4 and d["w_main"] == 160 * DIFF4
    assert d["expected"] == "SWITCH"


def test_v4_compare_flags_wrong_pool_count():
    alt = [blk4(100, 15), blk4(101, 15), blk4(102, 15)]
    main = [blk4(100, 15), blk4(101, 15)]
    r = rec_v4(alt, main, pool_main=[sh4(16)], n_alt=32, n_main=16, nakamoto=False,
               regime="objective", w_alt="4800", w_main="3300", tie=False, tie_draw=None,
               pool_alt_counted=0, pool_main_counted=0, result="SWITCH", nf=48, nf_main=32)
    msgs = compare(r)
    assert any("pool_main_counted" in m for m in msgs)


def test_v3_records_unchanged():
    alt = [blk4(100, 15), blk4(101, 15), blk4(102, 15)]
    main = [blk4(100, 15), blk4(101, 15)]
    r = rec_v4(alt, main, v=3, nf_rule="either")
    d = decide(r)
    assert "n_alt" not in d and d["regime"] == "objective"   # 48 objects, old rule

def test_pool_rule_all_changes_count_in_cli(tmp_path, capsys):
    alt = [blk4(100, 15), blk4(101, 15), blk4(102, 15)]
    main_ = [blk4(100, 15), blk4(101, 15)]
    pool = [sh4(16, 500, i=0), sh4(16, 400, i=1)] + [sh4(17 + i) for i in range(15)]
    r = rec_v4(alt, main_, pool_main=pool, w_alt="0", w_main="0")
    _write_node_log(tmp_path, "a0", ["SIM-SoP-DEC " + json.dumps(r)])
    main(["check", str(tmp_path), "--pool-rule", "all"])
    assert "pool-rule all changes 1 outcomes" in capsys.readouterr().out


def test_v4_compare_flags_duplicate_slot_in_pool():
    alt = [blk4(100, 15), blk4(101, 15), blk4(102, 15)]
    main = [blk4(100, 15), blk4(101, 15)]
    r = rec_v4(alt, main, pool_main=[sh4(16, i=0), sh4(16, i=1)], n_alt=32, n_main=16, nakamoto=False,
               regime="objective", w_alt="4800", w_main="3300", tie=False, tie_draw=None,
               pool_alt_counted=0, pool_main_counted=1, result="SWITCH", nf=48, nf_main=32)
    assert any("duplicate slot 16 in pool_main" in m for m in compare(r))
