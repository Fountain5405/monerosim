"""Tests for scripts/selfish_mining/sop_pending.py: honest workshares that
honest-001 had received but that sat in no honest block when an attacker
branch was revealed (results doc 4.1 hypothesis)."""
import json

from scripts.selfish_mining.sop_pending import reveal_pending

EPOCH_MS = 946684800000


def ts(day, hh, mm, ss, ms):
    return f"2000-01-{day:02d} {hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"


def dec(t, regime, result, w_alt, w_main, main_seen, diff=1600, w=16):
    rec = {'regime': regime, 'result': result, 'w': w, 'w_alt': str(w_alt), 'w_main': str(w_main),
           'alt': [{'h': 5, 'id': 'a' * 64, 'diff': str(diff), 'seen': 1, 'n_sh': 3, 'shares': []}],
           'main': [{'h': 5, 'id': 'b' * 64, 'diff': str(diff), 'seen': main_seen, 'n_sh': 3, 'shares': []}]}
    return f"{t}\t[P2P1]\tINFO\tblockchain\tsrc/x.cpp:1\tSIM-SoP-DEC {json.dumps(rec)}"


def share(t):
    return f"{t}\t[P2P1]\tINFO\tblockchain\tsrc/x.cpp:1\tSIM-SoP: workshare received (76 B, height 5)"


def test_pending_counts_shares_received_after_last_honest_block(tmp_path):
    main_seen = EPOCH_MS + 1000                      # 00:00:01.000 on day 1
    log = tmp_path / 'bitmonero.log'
    log.write_text("\n".join([
        share(ts(1, 0, 0, 0, 500)),                  # before the honest block: not pending
        share(ts(1, 0, 0, 2, 0)),                    # pending
        share(ts(1, 0, 0, 2, 300)),                  # the same share from a second peer
        share(ts(1, 0, 0, 5, 0)),                    # pending
        dec(ts(1, 0, 0, 7, 0), 'objective', 'SWITCH', w_alt=100 * 100, w_main=60 * 100, main_seen=main_seen),
        dec(ts(1, 0, 0, 5, 0), 'subjective', 'SWITCH', w_alt=1, w_main=1, main_seen=main_seen),   # not objective
        dec(ts(1, 0, 0, 6, 0), 'objective', 'KEEP', w_alt=1, w_main=2, main_seen=main_seen),      # not a switch
    ]) + "\n")
    rows = reveal_pending(log)
    assert len(rows) == 1
    r = rows[0]
    assert r['pending'] == 2
    assert r['att_obj'] == 100 and r['hon_obj'] == 60       # weight / (diff / w)
    assert r['flips_if_counted'] is False                   # 60 + 2 < 100
    assert r['gap'] == 40


def test_reveal_that_pending_shares_would_have_blocked(tmp_path):
    main_seen = EPOCH_MS + 1000
    log = tmp_path / 'bitmonero.log'
    lines = [share(ts(1, 0, 0, 2 + 3 * i, 0)) for i in range(5)]
    lines.append(dec(ts(1, 0, 0, 20, 0), 'objective', 'SWITCH', w_alt=62 * 100, w_main=60 * 100, main_seen=main_seen))
    log.write_text("\n".join(lines) + "\n")
    r = reveal_pending(log)[0]
    assert r['pending'] == 5 and r['flips_if_counted'] is True   # 60 + 5 >= 62
