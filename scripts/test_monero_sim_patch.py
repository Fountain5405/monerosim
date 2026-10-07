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
