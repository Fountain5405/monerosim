"""Nakamoto consensus (longest chain, first-seen ties) with reorg tags.

The transitions are pto-selfish-mining's BitcoinModel (vendor/, MIT,
Zur, Eyal & Tamar 2020) unchanged; this class adds the reorg each transition
causes and the objective switch from `reorgs.TaggedModel`.

State (a, h, fork): a = attacker's private blocks since the fork, h = honest
public blocks since the fork, fork in {Irrelevant, Relevant, Active}.
Reorgs:
- Override with h > 0: the honest chain loses h blocks (majority, depth h).
- Active fork, an honest miner on the attacker's branch (prob. gamma(1-alpha)):
  the attacker's branch wins and the honest chain loses h blocks (majority).
- Active fork, an honest miner on the honest branch (prob. (1-gamma)(1-alpha)):
  the gamma share that followed the attacker's h published blocks drops them
  (minority, depth h; none when gamma is 0).

normalization "main_chain" (pto's): the difficulty contribution is the
blocks a transition adds to the main chain, so rates are per main-chain block.
normalization "time": every mined block contributes 1, so rates are per block
interval (comparable with the SoP walk model, which counts objects / w).
"""
from __future__ import annotations

from typing import Tuple

from .reorgs import MAJORITY, MINORITY, TaggedModel, TaggedTransitions
from .vendor.blockchain_mdps import BitcoinModel
from .vendor.blockchain_mdps.base.blockchain_model import BlockchainModel


class NakamotoModel(TaggedModel, BitcoinModel):
    def __init__(self, alpha: float, gamma: float, max_fork: int, objective: str = "revenue",
                 min_depth: int = 11, weight: str = "count", normalization: str = "main_chain"):
        if normalization not in ("main_chain", "time"):
            raise ValueError("normalization must be main_chain or time")
        self.normalization = normalization
        self.init_objective(objective, min_depth, weight)
        BitcoinModel.__init__(self, alpha, gamma, max_fork)

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}({self.alpha}, {self.gamma}, {self.max_fork}, "
                f"{self.objective}, {self.min_depth}, {self.weight}, {self.normalization})")

    def __reduce__(self) -> Tuple[type, tuple]:
        return self.__class__, (self.alpha, self.gamma, self.max_fork, self.objective,
                                self.min_depth, self.weight, self.normalization)

    # The body follows BitcoinModel.get_state_transitions line for line.
    def get_tagged_transitions(self, state: BlockchainModel.State, action: BlockchainModel.Action,
                               check_valid: bool = True) -> TaggedTransitions:
        transitions = TaggedTransitions()

        if state == self.final_state:
            transitions.add(self.final_state, probability=1)
            return transitions

        a, h, fork = state

        if action is self.Action.Illegal:
            transitions.add(self.final_state, probability=1, reward=self.error_penalty / 2)

        if action is self.Action.Adopt:
            if h > 0:
                transitions.add((0, 0, self.Fork.Irrelevant), probability=1, difficulty_contribution=h)
            else:
                transitions.add(self.final_state, probability=1, reward=self.error_penalty)

        if action is self.Action.Override:
            if a > h:
                transitions.add((a - h - 1, 0, self.Fork.Irrelevant), probability=1, reward=h + 1,
                                difficulty_contribution=h + 1, reorgs=[(MAJORITY, h)])
            else:
                transitions.add(self.final_state, probability=1, reward=self.error_penalty)

        if action is self.Action.Match:
            if 0 < h <= a < self.max_fork and fork is self.Fork.Relevant:
                transitions.add((a, h, self.Fork.Active), probability=1)
            else:
                transitions.add(self.final_state, probability=1, reward=self.error_penalty)

        if action is self.Action.Wait:
            if fork is not self.Fork.Active and a < self.max_fork and h < self.max_fork:
                transitions.add((a + 1, h, self.Fork.Irrelevant), probability=self.alpha)
                transitions.add((a, h + 1, self.Fork.Relevant), probability=1 - self.alpha)
            elif fork is self.Fork.Active and 0 < h <= a < self.max_fork:
                transitions.add((a + 1, h, self.Fork.Active), probability=self.alpha)
                transitions.add((a - h, 1, self.Fork.Relevant), probability=self.gamma * (1 - self.alpha),
                                reward=h, difficulty_contribution=h, reorgs=[(MAJORITY, h)])
                # with gamma 0 nobody followed the attacker's branch
                transitions.add((a, h + 1, self.Fork.Relevant),
                                probability=(1 - self.gamma) * (1 - self.alpha),
                                reorgs=[(MINORITY, h)] if self.gamma > 0 else [])
            else:
                transitions.add(self.final_state, probability=1, reward=self.error_penalty)

        if self.normalization == "time":
            mined = action is self.Action.Wait
            for next_state in transitions.difficulty_contributions:
                transitions.difficulty_contributions[next_state] = (
                    1.0 if mined and next_state != self.final_state else 0.0)
        return transitions
