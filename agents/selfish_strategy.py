# agents/selfish_strategy.py
"""Pure Eyal-Sirer selfish-mining state machine (no RPC, no I/O).

Heights are block COUNTS (monerod get_info 'height' = top index + 1). `fork`
is the count of blocks common to both chains; the attacker's divergent block
indexes are fork..priv_height-1. `release_to` in the returned decision is a
block INDEX (the highest divergent index to submit to the bridge), or None.

This is the gamma=0 regime: a single bridge cannot propagate an equal-height
tie block, so the attacker loses every tie unless it extends its own branch.
That is outcome-equivalent to textbook Eyal-Sirer at gamma=0; the
lead-preserving partial reveal (which only matters at gamma>0) is deferred to
phase 2. See docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ReleaseDecision:
    release_to: Optional[int] = None   # highest divergent block INDEX to release, or None
    adopt_public: bool = False         # attacker abandoned its private branch this step


class SelfishStrategy:
    def __init__(self, name: str, start_height: int):
        if name not in ("honest", "eyal_sirer"):
            raise ValueError(f"unknown strategy: {name}")
        self.name = name
        self.start_height = int(start_height)
        self.fork = int(start_height)

    def update(self, pub_height: int, priv_height: int) -> ReleaseDecision:
        # Honest, or eyal_sirer during warm-up: publish everything immediately.
        if self.name == "honest" or pub_height < self.start_height:
            self.fork = pub_height
            return ReleaseDecision(
                release_to=(priv_height - 1) if priv_height > 0 else None,
                adopt_public=False,
            )

        a = priv_height - self.fork   # private branch length
        h = pub_height - self.fork    # honest branch length since fork

        # Honest overtook (or attacker has nothing on the branch): adopt public.
        if a < h or (h > 0 and a == 0):
            self.fork = pub_height
            return ReleaseDecision(release_to=None, adopt_public=True)

        # Honest has not moved since the fork: keep withholding.
        if h == 0:
            return ReleaseDecision(release_to=None, adopt_public=False)

        # a >= h >= 1 from here.
        if a == h:
            # Tie/race: submit the whole private branch. At gamma=0 the
            # equal-height tip does not propagate; the attacker only wins if it
            # later extends (handled next tick as a-h==1). Fork is NOT moved.
            return ReleaseDecision(release_to=priv_height - 1, adopt_public=False)

        if a - h == 1:
            # Honest caught to within one: reveal all -> strictly longer -> win.
            self.fork = priv_height
            return ReleaseDecision(release_to=priv_height - 1, adopt_public=False)

        # a - h >= 2: still comfortably ahead; withhold.
        return ReleaseDecision(release_to=None, adopt_public=False)
