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
