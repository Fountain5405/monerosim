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
