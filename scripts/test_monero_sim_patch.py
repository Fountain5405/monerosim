"""Pins on patches/monero-sim-pop.patch. setup.sh builds the patch outside
pytest and no C++ test covers it, so these guard fixes that a regenerated
patch could silently drop."""
from pathlib import Path

PATCH = Path(__file__).resolve().parent.parent / "patches" / "monero-sim-pop.patch"


def test_miner_invalidates_the_cached_block_id_on_every_nonce():
    """The stale-id miner bug (2026-10-03). The share log's get_block_hash(b)
    cached the share's id in the mining block object `b`, and nothing cleared
    it when the nonce changed. So a block found before the next template
    refresh (rate-limited after a local share) was stored under the SHARE's
    id while peers hashed the true one: one block, two ids. A 240 h run split
    for good. In the worker loop, `b.invalidate_hashes();` must be the first
    code line the patch adds after `b.nonce = nonce;`."""
    lines = PATCH.read_text().splitlines()
    context = "       b.nonce = nonce;"   # unified-diff context line: one space + the source line
    assert context in lines, "the patch has no hunk at the worker loop's `b.nonce = nonce;`"
    i = lines.index(context)
    added = []
    for line in lines[i + 1:]:
        if not line.startswith("+"):
            break
        added.append(line[1:].strip())
    code = [line for line in added if line and not line.startswith("//")]
    assert code[:1] == ["b.invalidate_hashes();"], added


def test_sop_does_not_score_a_peers_height_drop():
    """The P2P ban cascade (2026-10-07). Stock monero calls hit_score only when
    a peer's height went DOWN ("Claims N, claimed M before"). The second hit
    on a connection drops it with ban score 5, and the host fail score, which
    never decays, bans the peer for 24 h once it passes 10. Under SoP a node
    may switch to a branch with fewer blocks but more share weight, so honest
    peers' heights drop legitimately: the stubborn_h10_banlog runs replayed
    all 67 bans from such hits. Under SoP, hit_score must return before it
    scores: the code the patch adds right before `context.m_score -= score;`
    is that guard, and Blockchain gains the public flag getter it reads."""
    lines = PATCH.read_text().splitlines()
    context = "     context.m_score -= score;"   # one space + the source line
    assert context in lines, "the patch has no hunk at hit_score's `context.m_score -= score;`"
    i = lines.index(context)
    added = []
    for line in reversed(lines[:i]):
        if not line.startswith("+"):
            break
        added.insert(0, line[1:].strip())
    code = [line for line in added if line and not line.startswith("//")]
    assert code[:1] == ["if (m_core.get_blockchain_storage().sim_sop_enabled())"], added
    assert "return;" in code, added
    assert "+    bool sim_sop_enabled() const { return m_sim_sop_enabled; }" in lines


def test_sop_log_v4_and_window_rule():
    """MRL #146 2026-10-16/2026-10-20 (docs/20260930_sop_conformance.md, log v4)."""
    t = PATCH.read_text()
    assert '{\\"v\\":4' in t
    assert "(m_sim_sop_k - 1) * m_sim_sop_w" in t          # window = (k-1)*w
    assert "sim_sop_tip_shares(" in t                      # pool shares on a tip
    assert '\\"pool_main_counted\\":' in t


def test_shares_relay_only_on_the_main_tip():
    """Spec 2.3: pool shares on the tip relay; alternate shares do not."""
    t = PATCH.read_text()
    i = t.index("::handle_notify_new_workshare(int command")
    body = t[i:i + 1500]
    assert "if (extends_tip)" in body and "relay_workshare(arg, context)" in body
