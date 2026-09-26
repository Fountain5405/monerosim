# scripts/test_honest_chain_from_log.py
"""The honest reference chain reconstructed from a daemon log (review
2026-09-26): last-added block id per height, capped at the final tip."""
from scripts.honest_chain_from_log import parse_main_chain

T = "2000-01-01 00:{m:02d}:00.000\t{tag}\tINFO\tblockchain\tsrc/cryptonote_core/blockchain.cpp:5271\t{msg}\n"


def _add(m, tag, height, hid):
    return (T.format(m=m, tag=tag, msg="+++++ BLOCK SUCCESSFULLY ADDED")
            + T.format(m=m, tag=tag, msg=f"id:\t<{hid}>")
            + T.format(m=m, tag=tag, msg=f"PoW:\t<{'0' * 64}>")
            + T.format(m=m, tag=tag, msg=f"HEIGHT {height}, difficulty:\t1200"))


def test_last_added_per_height_wins_and_genesis_is_skipped():
    log = _add(0, "main", 0, "g") + _add(1, "[miner 0]", 1, "a1") + _add(2, "[P2P1]", 2, "a2")
    chain = parse_main_chain(log)
    assert chain == [{"height": 1, "hash": "a1"}, {"height": 2, "hash": "a2"}]


def test_reorg_replaces_heights_and_extends():
    log = (_add(1, "m", 1, "a1") + _add(2, "m", 2, "a2") + _add(3, "m", 3, "a3")
           + T.format(m=4, tag="[P2P4]", msg="REORGANIZE SUCCESS! on height: 2, new blockchain size: 5")
           + _add(4, "[P2P4]", 2, "b2") + _add(4, "[P2P4]", 3, "b3") + _add(4, "[P2P4]", 4, "b4"))
    assert [b["hash"] for b in parse_main_chain(log)] == ["a1", "b2", "b3", "b4"]


def test_switch_to_shorter_heavier_chain_drops_heights_above_tip():
    log = (_add(1, "m", 1, "a1") + _add(2, "m", 2, "a2") + _add(3, "m", 3, "a3") + _add(4, "m", 4, "a4")
           + _add(5, "[P2P2]", 2, "c2") + _add(5, "[P2P2]", 3, "c3"))      # tip is now 3
    assert [b["hash"] for b in parse_main_chain(log)] == ["a1", "c2", "c3"]


def test_interleaved_threads_do_not_mix_ids_and_heights():
    a = _add(1, "[P2P1]", 1, "a1").splitlines(keepends=True)
    b = _add(1, "[P2P2]", 2, "b2").splitlines(keepends=True)
    log = a[0] + b[0] + a[1] + b[1] + a[2] + b[2] + a[3] + b[3]   # fully interleaved
    assert parse_main_chain(log) == [{"height": 1, "hash": "a1"}, {"height": 2, "hash": "b2"}]


def test_grafted_prefix_absent_when_log_starts_above_it():
    log = _add(1, "m", 337, "a337") + _add(2, "m", 338, "a338")
    assert parse_main_chain(log) == [{"height": 337, "hash": "a337"}, {"height": 338, "hash": "a338"}]
