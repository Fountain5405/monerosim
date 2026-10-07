"""Tests for scripts/sop_reveals.py (reveal_stats/reorg_depths/reveal_shapes/
race_leads, ported from .claude/campaign7/analysis)."""
import calendar
import json
import time
from pathlib import Path

from scripts.selfish_mining.sop_reveals import (bucket, found_ids, node_depths, race_leads,
                                  reorg_events, reveal_shapes, run_stats)

ID = lambda n: ("%064x" % n)


def line(t, thread, msg):
    return f"{t}\t[{thread}]\tINFO\tglobal\tsrc/x.cpp:1\t{msg}"


def added(t, thread, height, bid):
    """The three log lines monerod prints to add one main-chain block."""
    return [line(t, thread, "+++++ BLOCK SUCCESSFULLY ADDED AS TOP BLOCK"),
            line(t, thread, f"id:\t<{bid}>"),
            line(t, thread, f"HEIGHT {height}, difficulty:\t741")]


def reorg_start(t, thread, split, old_top):
    return line(t, thread, f"###### REORGANIZE on height: {split} of {old_top} with cum_difficulty 1")


def reorg_success(t, thread, split, size):
    return line(t, thread, f"REORGANIZE SUCCESS! on height: {split}, new blockchain size: {size}")


def write_log(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def node_log(run: Path, node: str) -> Path:
    return run / "daemon_logs" / f"monero-{node}" / "bitmonero.log"


# --- reorg_events -------------------------------------------------------

def test_reorg_events_builds_old_and_new_from_matching_thread():
    b = [ID(i) for i in range(1, 6)]
    n = [ID(100), ID(101)]
    lines = []
    for h, bid in enumerate(b, start=1):
        lines += added(f"2000-01-01 00:00:{h:02d}.000", "M", h, bid)
    lines.append(reorg_start("2000-01-01 00:01:00.000", "M", 3, 5))
    lines += added("2000-01-01 00:01:01.000", "M", 3, n[0])
    lines += added("2000-01-01 00:01:02.000", "M", 4, n[1])
    lines.append(reorg_success("2000-01-01 00:01:03.000", "M", 3, 5))

    events = reorg_events(_write(lines))
    assert len(events) == 1
    e = events[0]
    assert e["split"] == 3 and e["old_top"] == 5 and e["new_top"] == 4
    assert e["old"] == [b[2], b[3], b[4]]
    assert e["new"] == n


def test_reorg_start_without_success_is_not_an_event():
    lines = added("2000-01-01 00:00:01.000", "M", 1, ID(1))
    lines.append(reorg_start("2000-01-01 00:01:00.000", "M", 1, 1))
    assert reorg_events(_write(lines)) == []


def test_heights_dropped_when_new_size_is_smaller():
    b = [ID(i) for i in range(1, 6)]
    n = [ID(100), ID(101)]
    lines = []
    for h, bid in enumerate(b, start=1):
        lines += added(f"2000-01-01 00:00:{h:02d}.000", "M", h, bid)
    lines.append(reorg_start("2000-01-01 00:01:00.000", "M", 3, 5))
    lines += added("2000-01-01 00:01:01.000", "M", 3, n[0])
    lines += added("2000-01-01 00:01:02.000", "M", 4, n[1])
    lines.append(reorg_success("2000-01-01 00:01:03.000", "M", 3, 5))
    # height 5 is now gone (new size 5 means heights 1..4 remain); a later
    # reorg reading it back sees None.
    lines.append(reorg_start("2000-01-01 00:02:00.000", "M2", 5, 5))
    lines += added("2000-01-01 00:02:01.000", "M2", 5, ID(102))
    lines.append(reorg_success("2000-01-01 00:02:02.000", "M2", 5, 6))

    events = reorg_events(_write(lines))
    assert len(events) == 2
    assert events[1]["old"] == [None]
    assert events[1]["new"] == [ID(102)]


def _write(lines, path=None):
    import tempfile
    d = Path(tempfile.mkdtemp())
    p = d / "bitmonero.log"
    write_log(p, lines)
    return p


# --- node_depths / bucket ------------------------------------------------

def test_node_depths_depth_is_old_top_minus_split_plus_1():
    b = [ID(i) for i in range(1, 6)]
    lines = []
    for h, bid in enumerate(b, start=1):
        lines += added(f"2000-01-01 00:00:{h:02d}.000", "M", h, bid)
    lines.append(reorg_start("2000-01-01 00:01:00.000", "M", 3, 5))
    lines += added("2000-01-01 00:01:01.000", "M", 3, ID(100))
    lines += added("2000-01-01 00:01:02.000", "M", 4, ID(101))
    lines.append(reorg_success("2000-01-01 00:01:03.000", "M", 3, 5))

    d = node_depths(_write(lines))
    assert len(d) == 1
    assert d[0]["split"] == 3 and d[0]["old_top"] == 5 and d[0]["depth"] == 3


def test_bucket():
    assert bucket(1) == "1"
    assert bucket(5) == "5"
    assert bucket(6) == "6-9"
    assert bucket(9) == "6-9"
    assert bucket(10) == "10+"
    assert bucket(20) == "10+"


# --- run_stats ------------------------------------------------------------

def test_run_stats_classifies_attacker_reveal_vs_other_reorg(tmp_path):
    att_bid = ID(200)
    hon_bid = ID(1)
    hon2_bid = ID(2)

    # honest-001: two reorgs. First applies an attacker-found block over one
    # honest block (a reveal); second applies only an honest block (other).
    lines = []
    lines += added("2000-01-01 00:00:01.000", "M", 1, hon_bid)
    lines.append(reorg_start("2000-01-01 00:01:00.000", "M", 1, 1))
    lines += added("2000-01-01 00:01:01.000", "M", 1, att_bid)
    lines.append(reorg_success("2000-01-01 00:01:02.000", "M", 1, 2))
    lines += added("2000-01-01 00:02:01.000", "M2", 2, hon2_bid)
    lines.append(reorg_start("2000-01-01 00:03:00.000", "M2", 2, 2))
    lines += added("2000-01-01 00:03:01.000", "M2", 2, ID(3))
    lines.append(reorg_success("2000-01-01 00:03:02.000", "M2", 2, 3))
    write_log(node_log(tmp_path, "honest-001"), lines)
    write_log(node_log(tmp_path, "honest-002"), [line("2000-01-01 00:00:01.000", "M", "nothing")])
    write_log(node_log(tmp_path, "attacker-miner"),
              [line("2000-01-01 00:00:00.500", "A", f"Found block <{att_bid}> at height 1")])

    s = run_stats(tmp_path)
    assert s["found_att"] == 1
    assert len(s["reveals"]) == 1
    assert s["reveals"][0]["honest_orphaned"] == 1
    assert s["reveals"][0]["att_applied"] == 1
    assert len(s["other_reorgs"]) == 1
    assert s["other_reorgs"][0]["att_applied"] == 0


def test_run_stats_merges_cell_markers(tmp_path):
    write_log(node_log(tmp_path, "honest-001"), [line("2000-01-01 00:00:01.000", "M", "nothing")])
    write_log(node_log(tmp_path, "honest-002"), [line("2000-01-01 00:00:01.000", "M", "nothing")])
    write_log(node_log(tmp_path, "attacker-miner"), [line("2000-01-01 00:00:01.000", "M", "nothing")])
    cells = {tmp_path.name: {"share": 0.3, "canonical_blocks": 100,
                             "attacker_orphan_rate": 0.1, "network_orphan_rate": 0.2,
                             "attacker_found": 42}}
    s = run_stats(tmp_path, cells)
    assert s["share"] == 0.3 and s["canonical_blocks"] == 100 and s["attacker_found"] == 42


# --- reveal_shapes --------------------------------------------------------

def _dec_line(t, rec):
    return f"{t}\t[P1]\tINFO\tglobal\tsrc/x.cpp:1\tSIM-SoP-DEC {json.dumps(rec)}"


def test_reveal_shapes_filters_to_switch_non_reinsert_non_skipped_with_attacker_blocks(tmp_path):
    att_bid = ID(200)
    alt_block = {"id": att_bid, "h": 1001, "n_sh": 3}
    main_blocks = [{"id": ID(1), "h": 1001, "n_sh": 2}]
    good = {"result": "SWITCH", "regime": "objective", "nf": 4, "w_alt": "10", "w_main": "5",
            "alt": [alt_block], "main": main_blocks}
    keep = dict(good, result="KEEP")
    reinsert = dict(good, reinsert=True)
    skipped = dict(good, skipped=True)
    no_att = dict(good, alt=[{"id": ID(2), "h": 1001, "n_sh": 1}])

    lines = [_dec_line("2000-01-01 00:00:01.000", good),
             _dec_line("2000-01-01 00:00:02.000", keep),
             _dec_line("2000-01-01 00:00:03.000", reinsert),
             _dec_line("2000-01-01 00:00:04.000", skipped),
             _dec_line("2000-01-01 00:00:05.000", no_att)]
    write_log(node_log(tmp_path, "honest-001"), lines)
    write_log(node_log(tmp_path, "attacker-miner"),
              [line("2000-01-01 00:00:00.500", "A", f"Found block <{att_bid}> at height 1001")])

    rows = reveal_shapes(tmp_path)
    assert len(rows) == 1
    r = rows[0]
    assert r["regime"] == "objective" and r["nf"] == 4
    assert r["alt_nsh"] == [3] and r["alt_is_att"] == [True]
    assert r["main_nsh"] == [2] and r["main_is_att"] == [False]


# --- race_leads ------------------------------------------------------------

def epoch_ms(ts: str) -> int:
    s, frac = ts.split(".")
    return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M:%S")) * 1000 + int(frac)


def test_race_leads_reports_max_honest_lead(tmp_path):
    att1, att2 = ID(201), ID(202)
    hon1, hon2, hon3 = ID(1), ID(2), ID(3)
    t_h1, t_h2, t_a1, t_a2, t_h3 = ("2000-01-01 00:00:01.000", "2000-01-01 00:00:02.000",
                                    "2000-01-01 00:00:03.000", "2000-01-01 00:00:04.000",
                                    "2000-01-01 00:00:05.000")
    rec = {
        "result": "SWITCH",
        "alt": [{"id": att1, "h": 1001, "seen": epoch_ms(t_a1), "n_sh": 0},
                {"id": att2, "h": 1002, "seen": epoch_ms(t_a2), "n_sh": 0}],
        "main": [{"id": hon1, "h": 1001, "seen": epoch_ms(t_h1), "n_sh": 0},
                 {"id": hon2, "h": 1002, "seen": epoch_ms(t_h2), "n_sh": 0},
                 {"id": hon3, "h": 1003, "seen": epoch_ms(t_h3), "n_sh": 0}],
    }
    write_log(node_log(tmp_path, "honest-001"), [_dec_line("2000-01-01 00:00:04.000", rec)])
    write_log(node_log(tmp_path, "attacker-miner"), [
        line(t_a1, "A", f"Found block <{att1}> at height 1001"),
        line(t_a2, "A", f"Found block <{att2}> at height 1002"),
    ])

    tally, rows = race_leads(tmp_path, 2)
    assert tally == {2: 1}
    assert len(rows) == 1
    assert rows[0]["a"] == 2 and rows[0]["h"] == 3 and rows[0]["lead"] == 2
