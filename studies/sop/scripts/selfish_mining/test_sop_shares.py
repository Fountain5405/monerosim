"""Tests for scripts/sop_shares.py (share_budget/embed_vs_judged, ported
from .claude/campaign7/analysis)."""
import json
from pathlib import Path

from scripts.selfish_mining.sop_shares import judged, miner, miner_blocks

ID = lambda n: ("%064x" % n)


def line(t, thread, msg):
    return f"{t}\t[{thread}]\tINFO\tglobal\tsrc/x.cpp:1\t{msg}"


def write_log(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def test_miner_shares_found_per_height_and_embedded_at_find():
    bid = ID(1)
    lines = [
        line("2000-01-01 00:00:01.000", "A", "SIM-SoP: share <%s> nonce 1 height 100 slot 0" % ID(10)),
        line("2000-01-01 00:00:02.000", "A", "SIM-SoP: share <%s> nonce 2 height 100 slot 1" % ID(11)),
        line("2000-01-01 00:00:03.000", "A", "SIM-SoP: pooled remote share <%s> at height 100" % ID(12)),
        line("2000-01-01 00:00:04.000", "A", "SIM-SoP: embedding 2 workshares (1 own, 1 remote) at height 100"),
        line("2000-01-01 00:00:05.000", "A", f"Found block <{bid}> at height 100"),
    ]
    log = _write(lines)
    shares, pooled, finds = miner(log)
    assert shares[100] == 2
    assert pooled[100] == 1
    assert len(finds) == 1
    f = finds[0]
    assert f["h"] == 100 and f["n"] == 2 and f["own"] == 1 and f["remote"] == 1
    assert f["embed_h"] == 100 and f["pooled_at_h"] == 1


def test_miner_zero_embedded_when_no_embedding_line():
    bid = ID(2)
    lines = [line("2000-01-01 00:00:01.000", "A", f"Found block <{bid}> at height 50")]
    shares, pooled, finds = miner(_write(lines))
    assert finds[0]["n"] is None and finds[0]["embed_h"] is None


def test_miner_blocks_pairs_found_blocks_with_last_embedding():
    bid = ID(3)
    lines = [
        line("2000-01-01 00:00:01.000", "A", "SIM-SoP: embedding 5 workshares (3 own, 2 remote) at height 200"),
        line("2000-01-01 00:00:02.000", "A", f"Found block <{bid}> at height 200"),
        line("2000-01-01 00:00:03.000", "A", "SIM-SoP: share <%s> nonce 1 height 201 slot 0" % ID(20)),
    ]
    blocks, shares = miner_blocks(_write(lines))
    assert blocks[bid] == (200, 5)
    assert shares[201] == 1


def _dec_line(t, rec):
    return f"{t}\t[P1]\tINFO\tglobal\tsrc/x.cpp:1\tSIM-SoP-DEC {json.dumps(rec)}"


def test_judged_reads_n_sh_from_dec_records():
    bid1, bid2 = ID(1), ID(2)
    rec = {"result": "SWITCH", "alt": [{"id": bid1, "h": 100, "n_sh": 7}],
           "main": [{"id": bid2, "h": 99, "n_sh": 0}]}
    lines = [_dec_line("2000-01-01 00:00:01.000", rec)]
    d = judged(_write(lines))
    assert d[bid1] == 7 and d[bid2] == 0


def _write(lines):
    import tempfile
    d = Path(tempfile.mkdtemp())
    p = d / "bitmonero.log"
    write_log(p, lines)
    return p
