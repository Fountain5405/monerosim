"""scripts/attacker_stranding.py: rejected long runs and reorg depth parsing."""
from scripts.attacker_stranding import deepest_reorg, rejected_long_runs

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
