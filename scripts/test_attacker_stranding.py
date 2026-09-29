"""scripts/attacker_stranding.py: rejected long runs and reorg depth parsing."""
from scripts.attacker_stranding import abandoned_depths, deepest_reorg, rejected_long_runs, run_row

LOG = "\n".join([
    "x\tSIM-PoP: fork 352 alt 0/10 vs main 26/26 -> KEEP",
    "x\tSIM-PoP: fork 352 alt 0/12 vs main 26/26 -> KEEP",
    "x\tSIM-SoP: fork 400 alt 9/45 vs main 41/45 -> KEEP",
    "x\tSIM-PoP: fork 410 alt 2/2 vs main 1/1 -> SWITCH",
    "x\tSIM-PoP: fork 420 alt 30/11 vs main 5/11 -> SWITCH",
    "x\tSIM-PoP: fork 430 alt 0/9 vs main 9/9 -> KEEP",
    "x\tREORGANIZE SUCCESS! on height: 300, new blockchain size: 347",
    "x\tREORGANIZE SUCCESS! on height: 350, new blockchain size: 352",
])


def test_rejected_long_runs_keeps_the_longest_kept_out_alt_per_fork():
    assert rejected_long_runs(LOG) == {352: 12, 400: 45}
    assert rejected_long_runs(LOG, min_len=9) == {352: 12, 400: 45, 430: 9}


def test_deepest_reorg():
    assert deepest_reorg(LOG) == 47
    assert deepest_reorg("nothing") == 0


ATTACKER_LOG = "\n".join([
    "x\t###### REORGANIZE on height: 391 of 439 with cum_difficulty 490276",
    "x\t###### REORGANIZE on height: 400 of 401 with cum_difficulty 5",
    "x\t###### REORGANIZE on height: 450 of 459 with cum_difficulty 7",
    "x\t###### REORGANIZE on height: 470 of 478 with cum_difficulty 9",
])


def test_abandoned_depths_count_the_attacker_blocks_each_reorg_disconnects():
    # "on height: h of top" disconnects heights h..top: top - h + 1 blocks.
    assert abandoned_depths(ATTACKER_LOG) == [49, 2, 10, 9]
    assert abandoned_depths("nothing") == []


def _run_dir(tmp_path, honest, bridge, attacker):
    for node, text in (("honest-001", honest), ("attacker-bridge", bridge), ("attacker-miner", attacker)):
        d = tmp_path / "daemon_logs" / f"monero-{node}"
        d.mkdir(parents=True)
        (d / "bitmonero.log").write_text(text)
    return tmp_path


def test_run_row_measures_stranding_at_the_attacker_even_when_honest_nodes_never_see_it(tmp_path):
    # A flagged bridge rejects the reveal and never announces it: honest-001
    # logs no long alt chain, the bridge keeps out 29 blocks, and the
    # attacker's daemon abandons them.
    bridge = "x\tSIM-PoP: fork 352 alt 0/29 vs main 26/30 -> KEEP"
    attacker = "x\t###### REORGANIZE on height: 353 of 381 with cum_difficulty 1"
    row = run_row(_run_dir(tmp_path, "", bridge, attacker), min_len=10)
    assert row["abandoned_runs"] == 1
    assert row["abandoned_blocks"] == 29
    assert row["attacker_max_abandon"] == 29
    assert row["bridge_kept_out"] == 29
    assert row["runs"] == 0 and row["blocks"] == 0   # honest-side view is blind


def test_run_row_kept_out_ignores_objective_reevaluations_of_the_displaced_branch(tmp_path):
    # After an OBJECTIVE switch the node re-weighs the branch it just left;
    # those KEEP lines are not a rejected reveal.
    bridge = "\n".join([
        "x\tSIM-SoP: fork 390 alt 366/47 vs main 27784/49 -> KEEP",
        "x\tSIM-SoP: fork 390 OBJECTIVE alt 490992/49 vs main 490276/49 (h0=336 nf=49) -> SWITCH",
        "x\tSIM-SoP: fork 390 OBJECTIVE alt 490276/49 vs main 490992/49 (h0=336 nf=496) -> KEEP",
    ])
    row = run_row(_run_dir(tmp_path, "", bridge, ""), min_len=10)
    assert row["bridge_kept_out"] == 47


AGENT_LOG = "\n".join([
    # every line is logged twice (two handlers); count each concession once
    "2000-01-01 01:03:54,374 - attacker-miner - SelfishMinerAgent[attacker-miner] - INFO - reveal rejected by the bridge (tip 1016); popped 12 private block(s) to ancestor 1004, fork -> 1016",
    "2000-01-01 01:03:54,374 - SelfishMinerAgent[attacker-miner] - INFO - reveal rejected by the bridge (tip 1016); popped 12 private block(s) to ancestor 1004, fork -> 1016",
    "2000-01-01 02:00:00,100 - attacker-miner - SelfishMinerAgent[attacker-miner] - INFO - strategy conceded; popped 1 private block(s) to ancestor 1030, fork -> 1032",
    "2000-01-01 02:00:00,100 - SelfishMinerAgent[attacker-miner] - INFO - strategy conceded; popped 1 private block(s) to ancestor 1030, fork -> 1032",
    "2000-01-01 03:00:00,200 - attacker-miner - SelfishMinerAgent[attacker-miner] - INFO - committed block 1099 dropped by the bridge; popped 4 private block(s) to ancestor 1097, fork -> 1101",
    "2000-01-01 03:00:00,200 - SelfishMinerAgent[attacker-miner] - INFO - committed block 1099 dropped by the bridge; popped 4 private block(s) to ancestor 1097, fork -> 1101",
])


def test_concessions_are_counted_once_by_reason():
    from scripts.attacker_stranding import concessions
    c = concessions(AGENT_LOG)
    assert c == {"reveal rejected": [12], "strategy conceded": [1], "committed dropped": [4]}


def test_run_row_reports_pops_for_a_reject_aware_attacker(tmp_path):
    # Pops are not reorganizations: a reject-aware attacker's abandonment
    # shows only in its own concession lines.
    d = _run_dir(tmp_path, "", "", "")
    host = tmp_path / "shadow.data" / "hosts" / "attacker-miner"
    host.mkdir(parents=True)
    (host / "bash.1020.stdout").write_text(AGENT_LOG)
    row = run_row(d, min_len=10)
    assert row["concessions"] == 3
    assert row["pop_max"] == 12
    assert row["dropped_commits"] == 1 and row["dropped_commit_blocks"] == 4
