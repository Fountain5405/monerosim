# agents/selfish_strategy.py
"""Selfish-mining decision state machines (no RPC, no I/O).

Heights are block COUNTS (monerod get_info 'height' = top index + 1). `fork`
is the count of blocks common to both chains; the attacker's divergent block
indexes are fork..priv_height-1. `release_to` in the returned decision is a
block INDEX (the highest divergent index to submit to the bridge), or None.

`honest` is the neutral baseline and `eyal_sirer` the textbook Eyal-Sirer state
machine. The phase-2 stubborn variants (`trail_stubborn`, `equal_fork_stubborn`,
`lead_stubborn`) layer on top of eyal_sirer (§4.2 of the phase-2 design). The
`release_lead` knob (default 1 = textbook) parametrizes when eyal_sirer's
cash-out fires: `release_lead: 2` is the conservative release-at-lead-2 policy
Qubic actually ran on Monero in 2025 (Lee & Kim 2025, arXiv:2512.01437) --
release the private chain while still two clear rather than waiting for honest
to close to one. This apparatus runs at gamma~0: a released equal-height tie
block does not propagate (a reactive attacker publishing through its own
bridges is always second), so the attacker loses every tie and the
tie-exploiting variants realize at or below eyal_sirer -- they are built to pay
off at gamma>0. See docs/20260912_selfish_mining_results.md and the specs under
docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md (+ -phase2-design.md).

`window_stubborn` attacks Share-or-Perish (SoP): SoP judges a fork subjectively
(and rejects withheld/late blocks) only while the alt branch holds fewer than
`window_objects` WORK OBJECTS (a block counts as 1 + its embedded valid
shares); at or past the window honest nodes fall back to plain cumulative
difficulty, which is a WEIGHT, not a block count -- each recent block weighs
`unit * (1 + its valid embedded shares)`, `unit = max(1, difficulty // w)`
(MRL #146). The attacker withholds while its branch is still inside the
window or its weight does not exceed honest's, reveals once BOTH the window
and the weight conditions hold, and gives up once honest leads by
`give_up_depth` blocks. Past the window there is no "withhold while
comfortably ahead" arm (unlike eyal_sirer/lead_stubborn): waiting for honest
to close in only risks losing the weight lead the attacker already has, and
the spec's own analysis models revealing at the first opportunity once past
the window.
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ReleaseDecision:
    release_to: Optional[int] = None   # highest divergent block INDEX to release, or None
    adopt_public: bool = False         # attacker abandoned its private branch this step
    release_from: int = 0              # lowest divergent block INDEX to release (the fork
                                       # BEFORE this step mutated it; the caller must use this,
                                       # not the post-update .fork, or the reveal submits nothing)
    forward_to: Optional[int] = None   # cap on how far honest blocks may be forwarded into the
                                       # offline miner (index-exclusive bound), or None = uncapped


class SelfishStrategy:
    def __init__(self, name: str, start_height: int, trail_depth: int = 1,
                 release_lead: int = 1, window_objects: int = 48,
                 give_up_depth: int = 2):
        if name not in (
            "honest",
            "eyal_sirer",
            "trail_stubborn",
            "equal_fork_stubborn",
            "lead_stubborn",
            "window_stubborn",
        ):
            raise ValueError(f"unknown strategy: {name}")
        self.name = name
        self.start_height = int(start_height)
        self.fork = int(start_height)
        self.trail_depth = int(trail_depth)
        self.release_lead = int(release_lead)
        if self.release_lead < 1:
            raise ValueError(f"release_lead must be >= 1, got {release_lead}")
        self.window_objects = int(window_objects)
        if self.window_objects < 1:
            raise ValueError(f"window_objects must be >= 1, got {window_objects}")
        self.give_up_depth = int(give_up_depth)
        if self.give_up_depth < 1:
            raise ValueError(f"give_up_depth must be >= 1, got {give_up_depth}")
        self._was_tie = False   # equal_fork_stubborn: set on a tie contest (a == h >= 1)
        self.last_weights = None   # window_stubborn: last branch_weights() result seen

    def update(self, pub_height: int, priv_height: int,
               branch_weights: Optional[Callable[[int, int, int], Optional[tuple]]] = None) -> ReleaseDecision:
        # `old_fork` is the divergence point for THIS step's release range. Every
        # returned decision carries it as release_from, because the reveal/adopt
        # branches below move self.fork forward and a caller that read the
        # post-update .fork would compute an empty release range (see review C1).
        old_fork = self.fork

        # Honest, or any strategy during warm-up: publish everything immediately.
        if self.name == "honest" or pub_height < self.start_height:
            self.fork = pub_height
            return ReleaseDecision(
                release_from=old_fork,
                release_to=(priv_height - 1) if priv_height > 0 else None,
                adopt_public=False,
                forward_to=None,
            )

        a = priv_height - old_fork   # private branch length
        h = pub_height - old_fork    # honest branch length since fork

        if self.name == "eyal_sirer":
            return self._eyal_sirer_decision(old_fork, pub_height, priv_height, a, h)
        if self.name == "trail_stubborn":
            return self._trail_stubborn_decision(old_fork, pub_height, priv_height, a, h)
        if self.name == "equal_fork_stubborn":
            return self._equal_fork_stubborn_decision(old_fork, pub_height, priv_height, a, h)
        if self.name == "window_stubborn":
            return self._window_stubborn_decision(old_fork, pub_height, priv_height, a, h, branch_weights)
        return self._lead_stubborn_decision(old_fork, pub_height, priv_height, a, h)

    def _eyal_sirer_decision(self, old_fork: int, pub_height: int, priv_height: int, a: int, h: int) -> ReleaseDecision:
        """Textbook Eyal-Sirer decision body, parametrized by `self.release_lead`
        (1 = textbook). Shared by the `eyal_sirer` strategy itself and by the
        stubborn variants' `a >= h` / fallthrough arms (§4.2: each stubborn
        variant is "like eyal_sirer except ...", so they inherit the knob)."""
        # Honest overtook (or attacker has nothing on the branch): adopt public.
        if a < h or (h > 0 and a == 0):
            self.fork = pub_height
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=True, forward_to=None)

        # Honest has not moved since the fork: keep withholding.
        if h == 0:
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=False, forward_to=None)

        # a >= h >= 1 from here.
        if a == h:
            # Tie/race: submit the whole private branch. At gamma=0 the
            # equal-height tip does not propagate; the attacker only wins if it
            # later extends (handled next tick as a-h==1). Fork is NOT moved.
            return ReleaseDecision(release_from=old_fork, release_to=priv_height - 1, adopt_public=False, forward_to=None)

        if 0 < a - h <= self.release_lead:
            # Honest closed to within `release_lead`: reveal all -> strictly
            # longer -> win. eyal_sirer is release_lead=1 (wait until honest is
            # exactly one behind, maximising honest waste). release_lead=2 is
            # Qubic's observed conservative policy (Lee & Kim 2025): cash out
            # while still two clear, trading one honest block of waste per run
            # for safety from the tie races a slow reveal loses at gamma~0.
            self.fork = priv_height
            return ReleaseDecision(release_from=old_fork, release_to=priv_height - 1, adopt_public=False, forward_to=None)

        # a - h > release_lead: still comfortably ahead; withhold.
        return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=False, forward_to=None)

    def _trail_stubborn_decision(self, old_fork: int, pub_height: int, priv_height: int, a: int, h: int) -> ReleaseDecision:
        """trail_stubborn(j): like eyal_sirer, but refuses to concede while
        trailing by at most `trail_depth` (j), hoping to catch back up."""
        # Behind by more than j, or nothing to trail with at all: concede.
        if (a == 0 and h > 0) or (h - a > self.trail_depth):
            self.fork = pub_height
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=True, forward_to=None)

        # Trailing within tolerance: hold. Withhold the honest blocks past the
        # fork from the miner too, so it keeps mining the private branch.
        if 0 < h - a <= self.trail_depth:
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=False, forward_to=old_fork)

        # a >= h: eyal_sirer rules.
        return self._eyal_sirer_decision(old_fork, pub_height, priv_height, a, h)

    def _equal_fork_stubborn_decision(self, old_fork: int, pub_height: int, priv_height: int, a: int, h: int) -> ReleaseDecision:
        """like eyal_sirer, but never concedes straight out of a tie: once it has
        contested a tie, if honest only breaks the tie by one it holds one more
        round instead of adopting, hoping to re-level."""
        if a < h:
            if self._was_tie and h - a == 1:
                # Just fell out of a tie by one: hold instead of conceding.
                return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=False, forward_to=old_fork)
            self._was_tie = False
            self.fork = pub_height
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=True, forward_to=None)

        # a >= h: eyal_sirer rules; track whether this step is the tie contest
        # itself so the next step knows whether a one-block honest lead is "out
        # of a tie" (hold) or a plain overtake (adopt).
        decision = self._eyal_sirer_decision(old_fork, pub_height, priv_height, a, h)
        self._was_tie = a == h and a >= 1
        return decision

    def _lead_stubborn_decision(self, old_fork: int, pub_height: int, priv_height: int, a: int, h: int) -> ReleaseDecision:
        """like eyal_sirer, but it holds its top block back at the overtake
        threshold. When honest catches to within one (h > 0, a - h == 1) -- where
        eyal_sirer would reveal the whole branch and win by one -- lead_stubborn
        instead reveals all BUT the top private block (a tie that bets on gamma)
        and keeps the top hidden, fork unmoved. It cashes the moment it is >= 2
        ahead of an *active* honest chain (h > 0, a - h >= 2): it reveals
        everything and commits the strictly-longer overtake (fork = priv_height,
        a real win).

        The a-h>=2 cash is the winning commit path and is load-bearing: without
        it lead_stubborn only ever advances `fork` by conceding, so it can never
        place a block on the canonical chain (realized share 0.000, attacker
        orphan 1.000 -- the 2026-09-13 bug, see docs/20260912_selfish_mining_results.md).
        The cash requires h > 0: while honest has not moved (h == 0) the attacker
        must keep withholding its secret lead, not reveal it. At gamma~0 the held
        tie never propagates, so lead_stubborn realizes at or below eyal_sirer;
        the one-round hold only pays at gamma>0. (In the a-h==1 arm
        priv_height == pub_height + 1, so release_to = priv_height - 2 ==
        pub_height - 1: the same tie as before, only with the missing commit
        restored via the a-h>=2 arm.)"""
        if h > 0 and a - h == 1:
            # Hold the top: reveal all but the top private block (a tie at gamma=0).
            return ReleaseDecision(release_from=old_fork, release_to=priv_height - 2, adopt_public=False, forward_to=None)

        if h > 0 and a - h >= 2:
            # Cash the lead: reveal the whole branch -> strictly longer -> win.
            self.fork = priv_height
            return ReleaseDecision(release_from=old_fork, release_to=priv_height - 1, adopt_public=False, forward_to=None)

        # h == 0 (withhold), a == h (tie), a < h (adopt): eyal_sirer rules.
        return self._eyal_sirer_decision(old_fork, pub_height, priv_height, a, h)

    def _window_stubborn_decision(self, old_fork: int, pub_height: int, priv_height: int,
                                   a: int, h: int,
                                   branch_weights: Optional["Callable[[int, int, int], Optional[tuple]]"]
                                   ) -> ReleaseDecision:
        """Attacks Share-or-Perish (SoP): SoP judges a fork subjectively (and
        rejects withheld/late blocks) only while the alt branch holds fewer
        than `window_objects` WORK OBJECTS. At or past the window every
        lateness factor is 1, but the comparison is still MRL #146's
        share-counted WEIGHT (unit * (1 + shares) per recent block), not a
        block count or plain cumulative difficulty. Give up once honest leads by
        `give_up_depth` blocks. An attack only starts from a private lead, so
        a == 0 adopts as in eyal_sirer. Withhold entirely while honest hasn't
        moved (h == 0). Otherwise reveal only once BOTH the branch is past
        `window_objects` objects AND its weight exceeds honest's; hold
        (never withhold-while-comfortably-ahead, unlike eyal_sirer) in every
        other case -- past the window, waiting for honest to close in only
        risks losing the weight lead already held, and the spec's own
        analysis models revealing at the first opportunity."""
        if (a == 0 and h > 0) or (h - a >= self.give_up_depth):
            self.fork = pub_height
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=True, forward_to=None)

        if h == 0:
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=False, forward_to=old_fork)

        weights = branch_weights(old_fork, priv_height, pub_height) if branch_weights else (a, a, h)
        self.last_weights = weights
        if weights is None:
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=False, forward_to=old_fork)
        att_objects, att_weight, hon_weight = weights
        if att_objects < self.window_objects or att_weight <= hon_weight:
            # Inside the window, or not ahead by weight: hold.
            return ReleaseDecision(release_from=old_fork, release_to=None, adopt_public=False, forward_to=old_fork)

        # Past the window and ahead by weight: reveal the whole branch and win.
        self.fork = priv_height
        return ReleaseDecision(release_from=old_fork, release_to=priv_height - 1, adopt_public=False, forward_to=None)
