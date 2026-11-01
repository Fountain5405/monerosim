"""Tests for scripts/selfish_mining/flipback_scan.py (ported from
.claude/campaign7/flipback_scan.py): per-node reorgs onto the attacker's
blocks, and whether each is undone within WINDOW_S of sim time."""
import sys
from pathlib import Path

from scripts.selfish_mining.flipback_scan import attacker_ids, main

ID = lambda n: ("%064x" % n)


def line(t, thread, msg):
    return f"{t}\t[{thread}]\tINFO\tglobal\tsrc/x.cpp:1\t{msg}"


def reorg(t, thread, split, old_top, size, bid):
    """A REORGANIZE event that switches in one block `bid` at height `split`."""
    return [
        line(t, thread, f"###### REORGANIZE on height: {split} of {old_top} with cum_difficulty 1"),
        line(t, thread, f" alternative blockchain size: {size} with cum_difficulty 1"),
        line(t, thread, "+++++ BLOCK SUCCESSFULLY ADDED"),
        line(t, thread, f"id:\t<{bid}>"),
        line(t, thread, f"HEIGHT {split}, difficulty:\t741"),
    ]


def write_log(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def node_log(run: Path, node: str) -> Path:
    return run / "daemon_logs" / f"monero-{node}" / "bitmonero.log"


def test_attacker_ids_reads_found_blocks(tmp_path):
    att_bid = ID(200)
    write_log(node_log(tmp_path, "attacker-miner"),
              [line("2000-01-01 00:00:00.500", "A", f"Found block <{att_bid}> at height 5")])
    assert attacker_ids(tmp_path) == {att_bid}


def test_switch_onto_attacker_block_kept_is_not_undone(tmp_path, capsys):
    att_bid = ID(200)
    lines = reorg("2000-01-01 00:00:10.000", "M", 5, 5, 1, att_bid)
    write_log(node_log(tmp_path, "honest-001"), lines)
    write_log(node_log(tmp_path, "attacker-miner"),
              [line("2000-01-01 00:00:00.500", "A", f"Found block <{att_bid}> at height 5")])

    sys.argv = ["flipback_scan.py", str(tmp_path)]
    main()
    out = capsys.readouterr().out
    assert "onto-attacker= 1" in out
    assert "undone<1s= 0" in out


def test_switch_onto_attacker_block_undone_within_window(tmp_path, capsys):
    att_bid = ID(200)
    hon_bid = ID(1)
    lines = reorg("2000-01-01 00:00:20.000", "M", 5, 5, 1, att_bid)
    lines += reorg("2000-01-01 00:00:20.500", "M", 5, 5, 1, hon_bid)
    write_log(node_log(tmp_path, "honest-001"), lines)
    write_log(node_log(tmp_path, "attacker-miner"),
              [line("2000-01-01 00:00:00.500", "A", f"Found block <{att_bid}> at height 5")])

    sys.argv = ["flipback_scan.py", str(tmp_path)]
    main()
    out = capsys.readouterr().out
    assert "onto-attacker= 1" in out
    assert "undone<1s= 1" in out


def test_later_simulated_days_are_scanned(tmp_path, capsys):
    """The 240 h runs span 2000-01-01 .. 2000-01-11; every day must be read,
    and the window must work across midnight."""
    att_bid = ID(200)
    hon_bid = ID(1)
    lines = reorg("2000-01-04 12:00:20.000", "M", 5, 5, 1, att_bid)
    lines += reorg("2000-01-04 12:00:20.500", "M", 5, 5, 1, hon_bid)
    lines += reorg("2000-01-05 23:59:59.800", "M", 9, 9, 1, att_bid)
    lines += reorg("2000-01-06 00:00:00.200", "M", 9, 9, 1, hon_bid)
    write_log(node_log(tmp_path, "honest-001"), lines)
    write_log(node_log(tmp_path, "attacker-miner"),
              [line("2000-01-01 00:00:00.500", "A", f"Found block <{att_bid}> at height 5")])

    sys.argv = ["flipback_scan.py", str(tmp_path)]
    main()
    out = capsys.readouterr().out
    assert "reorgs=  4" in out
    assert "undone<1s= 2" in out


def test_unparsed_timestamps_are_reported_not_dropped(tmp_path, capsys):
    write_log(node_log(tmp_path, "honest-001"),
              [line("2001-07-04 00:00:20.000", "M", "###### REORGANIZE on height: 5 of 5 with cum_difficulty 1")])
    write_log(node_log(tmp_path, "attacker-miner"), [])

    sys.argv = ["flipback_scan.py", str(tmp_path)]
    main()
    assert "unparsed-lines=1" in capsys.readouterr().out
