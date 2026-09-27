"""scripts/uncle_attribution.py: COUNTED-uncle parsing and miner attribution."""
from scripts.uncle_attribution import scan_log

LOG = (
    "2000-01-01 00:05:00.1\t[P2P1]\tINFO\tblockchain\tx.cpp:1\tSIM-PoP: embedding uncle header (76 B) at height 12\n"
    "2000-01-01 00:05:01.1\t[P2P1]\tINFO\tglobal\tx.cpp:2\tSIM-PoP: sibling alternative block at the tip height 11 -- refreshing the block template for the uncle header\n"
    "2000-01-01 00:05:02.1\t[P2P1]\tINFO\tblockchain\tx.cpp:3\tSIM-PoP: uncle <aa11> at height 12 COUNTED\n"
    "2000-01-01 00:05:03.1\t[P2P1]\tINFO\tblockchain\tx.cpp:3\tSIM-PoP: uncle <aa11> at height 12 COUNTED\n"
    "2000-01-01 00:05:04.1\t[P2P1]\tINFO\tblockchain\tx.cpp:3\tSIM-PoP: uncle <bb22> at height 20 COUNTED (never received: trustless)\n"
    "2000-01-01 00:05:05.1\t[P2P1]\tINFO\tblockchain\tx.cpp:4\tSIM-PoP: uncle <cc33> at height 21 REJECTED (received late)\n"
)


def test_scan_log_dedupes_counted_and_ignores_rejected():
    r = scan_log(LOG)
    assert r["counted"] == {"aa11": 12, "bb22": 20}
    assert r["embedded"] == 1 and r["refreshes"] == 1
