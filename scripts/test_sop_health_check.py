"""Tests for scripts/sop_health_check.py (review 2026-09-25 F1/F2/F5 detectors)."""
from pathlib import Path

from scripts.sop_health_check import check_run, main, scan_log_text, summarize

HEALTHY = """\
2000-01-01 00:21:00.835 [RPC0] INFO global blockchain.cpp:2815 ###### REORGANIZE on height: 2 of 2 with cum_difficulty 3601
2000-01-01 00:21:00.900 [RPC0] INFO global blockchain.cpp:2900 REORGANIZE SUCCESS! on height: 2, new blockchain size: 4
2000-01-01 00:22:00.000 [P2P1] INFO blockchain blockchain.cpp:2820 ----- BLOCK ADDED AS ALTERNATIVE ON HEIGHT 3
2000-01-01 00:22:00.001 [P2P1] INFO blockchain blockchain.cpp:2000 SIM-SoP: fork 2 alt 1904/1 vs main 224/2 -> SWITCH
2000-01-01 00:22:00.002 [P2P1] INFO blockchain blockchain.cpp:2000 SIM-SoP: fork 3 OBJECTIVE alt 5401/2 vs main 3601/1 (h0=0 nf=2) -> SWITCH
2000-01-01 00:22:00.003 [P2P1] INFO blockchain blockchain.cpp:2000 SIM-SoP: fork 4 TIE 112/1 vs 112/1 -> KEEP (random tie)
"""

BROKEN = """\
2000-01-01 00:21:00.835 [RPC0] INFO global blockchain.cpp:2815 ###### REORGANIZE on height: 2 of 2 with cum_difficulty 3601
2000-01-01 00:21:00.836 [RPC0] ERROR blockchain blockchain.cpp:5416 Exception at [add_new_block], what=Error attempting to retrieve a hard fork version at height 2 from the db: MDB_NOTFOUND: No matching key/data pair found
2000-01-01 00:22:00.001 [P2P1] INFO blockchain blockchain.cpp:2000 SIM-SoP: fork 52 alt 0/1 vs main 224/2 -> KEEP
"""


def test_scan_counts_and_share_weight_detection():
    n = scan_log_text(HEALTHY, unit=112)
    assert (n["reorg_started"], n["reorg_success"], n["exceptions"], n["alt_added"]) == (1, 1, 0, 1)
    assert n["decisions"] == 3 and n["objective"] == 1 and n["ties"] == 1 and n["switches"] == 2
    assert n["sop_subjective"] == 2          # the objective line is excluded
    assert n["share_weighted"] == 1          # 1904 > 112*1 (shares counted); 224 == 112*2, 112 == 112*1
    b = scan_log_text(BROKEN, unit=112)
    assert (b["reorg_started"], b["reorg_success"], b["exceptions"]) == (1, 0, 1)
    assert b["share_weighted"] == 0          # every weight is lb*unit: the share term is inert


POP = """\
2000-01-01 00:22:00.001 [P2P1] INFO blockchain blockchain.cpp:2000 SIM-PoP: fork 2 alt 2/1 vs main 1/1 -> SWITCH
2000-01-01 00:22:00.002 [P2P1] INFO blockchain blockchain.cpp:2000 SIM-PoP: fork 3 alt 1/1 vs main 1/1 -> KEEP
2000-01-01 00:22:00.003 [P2P1] INFO blockchain blockchain.cpp:2000 SIM-PoP: fork 4 TIE 1/1 vs 1/1 -> KEEP (det tie)
"""


def test_scan_counts_pop_uncle_bonus():
    n = scan_log_text(POP)                   # PoP needs no unit: a chain heavier than its length carried an uncle
    assert n["decisions"] == 3 and n["sop_subjective"] == 0
    assert n["share_weighted"] == 1          # 2/1: the uncle bonus counted (review F4 was 0 of 1260)


def _run(tmp_path: Path, logs: dict) -> Path:
    for node, text in logs.items():
        d = tmp_path / "daemon_logs" / f"monero-{node}"
        d.mkdir(parents=True)
        (d / "bitmonero.log").write_text(text)
    return tmp_path


def test_check_run_flags_failed_reorgs_and_exceptions(tmp_path):
    rep = check_run(_run(tmp_path, {"honest-001": HEALTHY, "attacker-bridge": BROKEN}), unit=112)
    assert not rep["ok"]
    assert any("attacker-bridge: reorg 0/1" in p for p in rep["problems"])
    assert any("1 add_new_block exceptions" in p for p in rep["problems"])
    assert rep["forks_seen"] == 1            # the bridge's counts are excluded from forks_seen
    assert "REORG 1/2" in summarize(rep) and "EXC 1" in summarize(rep)


def test_check_run_healthy_and_fork_free(tmp_path):
    rep = check_run(_run(tmp_path, {"honest-001": HEALTHY, "honest-002": HEALTHY}), unit=112)
    assert rep["ok"] and summarize(rep) == "ok" and rep["share_weighted"] == 2
    quiet = _run(tmp_path / "q", {"honest-001": "nothing happened\n"})
    rep = check_run(quiet)
    assert rep["ok"] and summarize(rep) == "no-forks"
    assert main([str(quiet), "--require-forks"]) == 1
    assert main([str(quiet)]) == 0
    assert main([str(tmp_path), "--unit", "112", "--require-forks", "--require-share-weight"]) == 0


def test_summarize_without_logs_or_report():
    assert summarize(None) == "-"
    assert summarize({"nodes": {}, "totals": {}}) == "no-logs"


REAL_DAA = """\
2000-01-01 00:00:00.100 [main] INFO blockchain blockchain.cpp:2576 SIM-SoP: weight table armed (w=16 delay_ms=5000 k=3)
2000-01-01 00:02:00.000 [miner 0] INFO blockchain blockchain.cpp:5271 HEIGHT 337, difficulty:\t1083
2000-01-01 00:05:00.000 [P2P1] INFO blockchain blockchain.cpp:5271 HEIGHT 338, difficulty:\t1058
2000-01-01 00:08:00.000 [P2P1] INFO blockchain blockchain.cpp:5271 HEIGHT 339, difficulty:\t1060
2000-01-01 00:09:55.807 [P2P8] INFO blockchain blockchain.cpp:2551 SIM-SoP: fork 338 alt 66/1 vs main 330/1 -> KEEP
2000-01-01 00:09:55.808 [P2P8] INFO blockchain blockchain.cpp:2551 SIM-SoP: fork 338 alt 132/2 vs main 330/1 -> KEEP
2000-01-01 00:11:00.000 [P2P1] INFO blockchain blockchain.cpp:5271 HEIGHT 340, difficulty:\t1050
2000-01-01 00:12:00.000 [P2P2] INFO blockchain blockchain.cpp:2551 SIM-SoP: fork 339 alt 65/1 vs main 65/1 -> KEEP
"""


def test_share_weight_detection_derives_unit_from_the_logged_difficulty():
    """On a real-DAA base (chain snapshot, no fixed-difficulty) there is no
    constant unit for --diff/--w, so the matrix health column could never
    see share weight (review 2026-09-26). The unit at each suffix height is
    that height's logged difficulty // w; a chain heavier than its length in
    units by a further full unit carried a counted share (the margin absorbs
    an alt chain's slightly different difficulty)."""
    n = scan_log_text(REAL_DAA)
    assert n["w"] == 16
    assert n["sop_subjective"] == 3
    # 330 vs one block at height 339 (1060 // 16 = 66): 330 >= 66 + 66 -> shares counted.
    # 66/1 and 132/2 (66 + 65 for heights 339, 340) are exactly length x unit; 65/1 at 340 too.
    assert n["share_weighted"] == 2          # both decisions at fork 338 carried it via `main`
    assert n["share_weighted_unit_source"] == "logged-difficulty"


def test_explicit_unit_still_wins():
    n = scan_log_text(REAL_DAA, unit=66)
    assert n["share_weighted"] == 2 and n["share_weighted_unit_source"] == "explicit"


def test_no_unit_without_armed_line_or_explicit_unit():
    text = REAL_DAA.replace("SIM-SoP: weight table armed (w=16 delay_ms=5000 k=3)", "")
    n = scan_log_text(text)
    assert n["w"] is None and n["share_weighted"] == 0 and n["share_weighted_unit_source"] is None


def test_summarize_flags_inert_share_term(tmp_path):
    """SoP decisions happened but not one carried a counted share: the F2
    failure class, now a token in the health column instead of a manual grep."""
    inert = REAL_DAA.replace("main 330/1", "main 66/1")          # every weight is exactly length x unit
    run = _run(tmp_path, {"honest-001": inert, "attacker-bridge": ""})
    rep = check_run(run)
    assert rep["totals"]["sop_subjective"] == 3 and rep["totals"]["share_weighted"] == 0
    assert "share-term-inert" in summarize(rep)
    healthy = _run(tmp_path / "h", {"honest-001": REAL_DAA})
    assert "share-term-inert" not in summarize(check_run(healthy))


def test_check_run_flags_agent_tracebacks(tmp_path):
    """An agent can raise on every tick while every daemon stays healthy: the
    stubborn smoke's stock attacker (2026-09-30) printed 2750 traceback lines,
    never published, and its cell still read "ok" / no-forks. The agents'
    output (shadow.data/hosts/<host>/bash.*.stdout|stderr) is scanned too.
    Lines are counted, since an agent logging through two handlers prints each
    exception twice. Daemon and wallet output is not scanned."""
    run = _run(tmp_path, {"honest-001": HEALTHY})
    host = run / "shadow.data" / "hosts" / "attacker-miner"
    host.mkdir(parents=True)
    tb = 'Traceback (most recent call last):\n  File "x.py", line 1\nValueError: bad\n'
    (host / "bash.1020.stdout").write_text("fine\n" + tb + tb)
    (host / "bash.1020.stderr").write_text(tb)
    (host / "monerod-sim.1000.stdout").write_text(tb)
    rep = check_run(run, unit=112)
    assert not rep["ok"]
    assert rep["agent_tracebacks"] == {"attacker-miner": 3}
    assert rep["totals"]["agent_tracebacks"] == 3
    assert any("attacker-miner: 3 agent traceback lines" in p for p in rep["problems"])
    assert summarize(rep) == "AGENT-TB 3"
    clean = check_run(_run(tmp_path / "c", {"honest-001": HEALTHY}), unit=112)
    assert clean["ok"] and clean["agent_tracebacks"] == {} and clean["totals"]["agent_tracebacks"] == 0
