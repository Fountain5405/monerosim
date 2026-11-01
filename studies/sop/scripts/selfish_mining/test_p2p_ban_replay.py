"""Tests for scripts/p2p_ban_replay.py (ban_replay.py/drops.sh, ported from
.claude/campaign7/analysis)."""
from pathlib import Path

import yaml

from scripts.selfish_mining.p2p_ban_replay import group_drops, replay

PEER_IP = "10.0.0.5"
PEER_PORT = "18080"


def line(t, msg):
    return f"{t}\t[P2P1]\tINFO\tglobal\tsrc/net_node.inl:1\t{msg}"


def write_log(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def node_log(run: Path, node: str) -> Path:
    return run / "daemon_logs" / f"monero-{node}" / "bitmonero.log"


def write_agents(run: Path, hosts: dict):
    (run / "shadow_agents.yaml").write_text(yaml.safe_dump({"hosts": hosts}))


def conn(dir_="OUT"):
    return f"[{PEER_IP}:{PEER_PORT} {dir_}]"


def test_logged_ban_is_matched_from_claims_and_scored_drops(tmp_path):
    write_agents(tmp_path, {"peer": {"ip_addr": PEER_IP}})
    lines = [
        line("2000-01-01 00:00:01.000", f"{conn()} Claims 5, claimed 3 before"),
        line("2000-01-01 00:00:02.000", f"{conn()} dropping connection id abc (pruning seed 0), score 5, flush_all_spans 0"),
        line("2000-01-01 00:00:03.000", f"{conn()} Claims 5, claimed 3 before"),
        line("2000-01-01 00:00:04.000", f"{conn()} dropping connection id def (pruning seed 0), score 5, flush_all_spans 0"),
        line("2000-01-01 00:00:05.000", f"{conn()} Claims 5, claimed 3 before"),
        line("2000-01-01 00:00:06.000", f"{conn()} dropping connection id ghi (pruning seed 0), score 5, flush_all_spans 0"),
        line("2000-01-01 00:00:06.000", f"Host {PEER_IP} blocked."),
    ]
    write_log(node_log(tmp_path, "honest-001"), lines)
    r = replay(tmp_path)
    assert r["bans_logged"] == 1
    assert r["bans_replayed"] == 1
    assert r["matched"] == 1
    assert not r["unexplained"]


def test_ban_with_no_scored_drops_is_unexplained(tmp_path):
    write_agents(tmp_path, {"peer": {"ip_addr": PEER_IP}})
    lines = [line("2000-01-01 00:00:01.000", f"Host {PEER_IP} blocked.")]
    write_log(node_log(tmp_path, "honest-001"), lines)
    r = replay(tmp_path)
    assert r["bans_logged"] == 1
    assert r["bans_replayed"] == 0
    assert r["matched"] == 0
    assert len(r["unexplained"]) == 1


def test_claims_hit_after_shorter_branch_switch_is_counted_as_caused(tmp_path):
    write_agents(tmp_path, {"peer": {"ip_addr": PEER_IP}})
    peer_lines = [
        line("2000-01-01 00:00:00.000",
             "SIM-SoP: fork 10 OBJECTIVE alt 300/3 vs main 200/4 (h0=1 nf=50) -> SWITCH"),
    ]
    write_log(node_log(tmp_path, "peer"), peer_lines)
    hit_lines = [
        line("2000-01-01 00:10:00.000", f"{conn()} Claims 5, claimed 3 before"),
    ]
    write_log(node_log(tmp_path, "honest-001"), hit_lines)
    r = replay(tmp_path)
    assert r["claim_cause"] == {"after a shorter-branch switch by the peer": 1}
    assert r["shorter_switches_total"] == 1


def test_group_drops_counts_grouped_lines(tmp_path):
    lines = [
        line("2000-01-01 00:00:01.000", f"{conn()} dropping connection id abc (pruning seed 0), score 5, flush_all_spans 0"),
        line("2000-01-01 00:00:02.000", f"{conn()} dropping connection id def (pruning seed 0), score 5, flush_all_spans 0"),
    ]
    write_log(node_log(tmp_path, "honest-001"), lines)
    groups = group_drops(tmp_path)
    assert "honest-001" in groups
    assert sum(groups["honest-001"].values()) == 2
