"""Share-or-Perish (MRL #146, 2026-10-20 rule) for the disruption objective.

The exact SoP MDP (`studies/sop/scripts/sop_mdp.py`) tracks every work object:
state (a, D, xa, pa, h, xh, ph). Its caps stop at 4 blocks a side, far short
of the 11+ honest blocks a reorg past the 10-block lock needs. This model
keeps only what the disruption objective reads:

  h   honest blocks since the fork, saturating at min_depth (the reward test);
  a1  whether the attacker has a block since the fork (a reveal needs one);
  x   the attacker's object lead D + pa - ph: every attacker object moves it
      +1 and every honest object -1, share or block alike;
  pa  the attacker's shares pending on its tip (they do not count for
      acceptance: the network accepts a reveal iff x - pa > 0).

Departures from the exact rule, two of them in the attacker's favour:
- the window (no reveal before 32 objects past a branch's first block) is
  ignored; at h >= 11 a race is always past it;
- after give_up and publish the honest pending shares are dropped (exact:
  the next race starts at x = -ph);
- attacker shares past p_max and attacker objects past x_max are discarded
  (they cost the attacker); honest objects below x_min are ignored (from
  x_min the attacker's chance to recover is (alpha/(1-alpha))^-x_min).
So the optimum is optimistic for the attacker; `exact_rate` runs a policy
through `sop_mdp.py`'s own event, acceptance and reset functions to get the
rate of a policy that is legal in the exact game.

Time is counted in expected block intervals: each object adds 1/w. Rewards
are 1 per accepted reveal with h >= min_depth (count weight only). Revenue
is not modelled (blocks per side are not tracked).
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .reorgs import MAJORITY, TaggedModel, TaggedTransitions
from .vendor.blockchain_mdps.base.base_space.default_value_space import DefaultValueSpace
from .vendor.blockchain_mdps.base.base_space.discrete_space import DiscreteSpace
from .vendor.blockchain_mdps.base.base_space.multi_dimensional_discrete_space import MultiDimensionalDiscreteSpace
from .vendor.blockchain_mdps.base.base_space.space import Space
from .vendor.blockchain_mdps.base.blockchain_model import BlockchainModel


class SoPWalkModel(TaggedModel):
    def __init__(self, alpha: float, w: int = 16, min_depth: int = 11, x_min: int = -80, x_max: int = 80,
                 p_max: int = 64, objective: str = "disruption"):
        if objective != "disruption":
            raise ValueError("SoPWalkModel models the disruption objective only")
        self.alpha = alpha
        self.w = w
        self.x_min, self.x_max, self.p_max = x_min, x_max, p_max
        self.init_objective(objective, min_depth, "count")
        self.Action = self.create_int_enum("Action", ["Illegal", "Hold", "Reveal", "GiveUp", "Publish"])
        super().__init__()

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}({self.alpha}, w={self.w}, min_depth={self.min_depth}, "
                f"x=[{self.x_min},{self.x_max}], p_max={self.p_max})")

    def __reduce__(self) -> Tuple[type, tuple]:
        return self.__class__, (self.alpha, self.w, self.min_depth, self.x_min, self.x_max, self.p_max,
                                self.objective)

    def get_state_space(self) -> Space:
        underlying = MultiDimensionalDiscreteSpace((0, self.min_depth), (0, 1), (self.x_min, self.x_max),
                                                   (0, self.p_max))
        return DefaultValueSpace(underlying, self.get_final_state())

    def get_action_space(self) -> Space:
        return DiscreteSpace(self.Action)

    def get_initial_state(self) -> BlockchainModel.State:
        return 0, 0, 0, 0

    def get_final_state(self) -> BlockchainModel.State:
        return -1, -1, -1, -1

    def clamp(self, x: int) -> int:
        return max(self.x_min, min(self.x_max, x))

    def reset(self, x: int, pa: int) -> tuple:
        return 0, 0, self.clamp(x), pa

    def legal(self, state: tuple, action) -> bool:
        h, a1, x, pa = state
        if action is self.Action.Hold:
            return True
        if action is self.Action.Reveal:
            return a1 == 1 and h >= 1 and x - pa > 0
        if action is self.Action.Publish:
            return a1 == 1 and h == 0
        if action is self.Action.GiveUp:
            return h >= 1 or a1 == 1
        return False

    def get_tagged_transitions(self, state: BlockchainModel.State, action: BlockchainModel.Action,
                               check_valid: bool = True) -> TaggedTransitions:
        t = TaggedTransitions()
        if state == self.final_state:
            t.add(self.final_state, probability=1)
            return t
        if not self.legal(state, action):
            penalty = self.error_penalty / 2 if action is self.Action.Illegal else self.error_penalty
            t.add(self.final_state, probability=1, reward=penalty)
            return t

        h, a1, x, pa = state
        if action is self.Action.Hold:
            al, pb, dt = self.alpha, 1.0 / self.w, 1.0 / self.w
            # attacker share: pending on its tip (discarded past p_max)
            share = (h, a1, x + 1, pa + 1) if pa < self.p_max and x < self.x_max else (h, a1, x, pa)
            t.add(share, probability=al * (1 - pb), difficulty_contribution=dt, allow_merging=True)
            # attacker block: embeds its pending shares
            t.add((h, 1, self.clamp(x + 1), 0), probability=al * pb, difficulty_contribution=dt,
                  allow_merging=True)
            # honest share / block
            t.add((h, a1, self.clamp(x - 1), pa), probability=(1 - al) * (1 - pb), difficulty_contribution=dt,
                  allow_merging=True)
            t.add((min(h + 1, self.min_depth), a1, self.clamp(x - 1), pa), probability=(1 - al) * pb,
                  difficulty_contribution=dt, allow_merging=True)
        elif action is self.Action.Reveal:
            # the attacker's pending shares stay pending on the new tip (exact)
            t.add(self.reset(pa, pa), probability=1, reorgs=[(MAJORITY, h)])
        elif action is self.Action.Publish:
            t.add(self.reset(pa, pa), probability=1)      # exact: x = pa - ph
        else:  # GiveUp
            t.add(self.reset(0, 0), probability=1)        # exact: x = -ph
        return t

    def get_honest_revenue(self) -> float:
        return 0.0


def to_walk_state(model: SoPWalkModel, s: tuple) -> tuple:
    """Map an exact sop_mdp state (a, D, xa, pa, h, xh, ph) onto the walk model's state."""
    a, D, xa, pa, h, xh, ph = s
    x = D + pa - ph
    return (min(h, model.min_depth), 1 if a >= 1 else 0, max(model.x_min, min(model.x_max, x)),
            min(pa, model.p_max))


def exact_rate(model: SoPWalkModel, policy, objects: int, seed: int = 1, own_pending: bool = False) -> dict:
    """Deep-reorg rate of `policy` in the exact SoP game, by simulation.

    Uses sop_mdp.py's event, acceptance and reset functions with caps out of
    reach, so the window, honest pending carry-over and pending shares are
    exact. Where the walk policy asks for an action the exact game forbids
    (a reveal before the window, or one the network would reject), the
    attacker holds instead. Exact states outside the walk's range map onto
    its boundary.
    Returns reveals with h >= min_depth per block interval (objects / w).
    """
    from studies.sop.scripts import sop_mdp as M

    if model.w != M.W_SHARES:
        raise ValueError(f"exact_rate needs w = {M.W_SHARES}, the exact model's")
    caps = M.Caps(a_max=10 ** 9, h_max=10 ** 9, d_max=10 ** 9, p_max=10 ** 9, deficit=10 ** 9)
    rng = np.random.default_rng(seed)
    probs = np.array(M.event_probs(model.alpha))
    events = rng.choice(4, size=objects, p=probs)
    A = model.Action
    s = M.START
    deep = reveals = give_ups = 0
    depths = []
    for e in events:
        is_att, is_blk = M.EVENTS[e]
        s = M.event(s, is_att, is_blk, caps)
        a, D, xa, pa, h, xh, ph = s
        if a == 0 and h == 0:
            continue
        accepted = M.accepted(s, own_pending)
        ws = to_walk_state(model, s)
        act = model.action_space.index_to_element(int(policy[model.state_space.element_to_index(ws)]))
        if act is A.Reveal and not accepted:
            act = A.Hold
        if act is A.Publish and not (a >= 1 and h == 0):
            act = A.Hold
        if act is A.Reveal:
            reveals += 1
            if h >= model.min_depth:
                deep += 1
                depths.append(h)
            s = M.do_reveal(s)[0]
        elif act is A.Publish:
            s = M.do_publish(s)[0]
        elif act is A.GiveUp:
            give_ups += 1
            s = M.do_give_up(s)[0]
    block_times = objects / model.w
    return {"objects": objects, "block_times": block_times, "deep_reveals": deep,
            "deep_per_block_time": deep / block_times, "reveals": reveals, "give_ups": give_ups,
            "mean_deep_depth": float(np.mean(depths)) if depths else 0.0}
