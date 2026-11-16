"""Reorg tagging, the disruption objective and the reorg profile of a policy.

Every protocol model in this package builds its transitions with
`TaggedTransitions`, which records the public reorgs each transition causes:

- "majority": blocks removed from the chain most honest miners had as their
  tip (an override, or a match race the attacker's branch wins);
- "minority": blocks removed from the chain the gamma share of honest miners
  had followed (a match race the attacker's branch loses).

`TaggedModel.objective` picks the reward the solver maximises: "revenue"
(attacker blocks on the main chain, pto's own reward) or "disruption"
(weight per majority reorg deeper than `min_depth - 1` blocks). The
difficulty contribution stays blocks added to the main chain, so a solved
disruption value is the expected weight per main-chain block.

`reorg_profile` reports, for any policy, the revenue and the rate of reorgs of
each depth per main-chain block, from the stationary distribution of the
policy's Markov chain. `simulate_profile` estimates the same by Monte Carlo.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, Optional, Tuple

import numpy as np

from .vendor.blockchain_mdps import BlockchainModel, StateTransitions
from .vendor.blockchain_mdps.base.blockchain_mdps.sparse_blockchain_mdp import SparseBlockchainMDP

MAJORITY = "majority"
MINORITY = "minority"
OBJECTIVES = ("revenue", "disruption")
WEIGHTS = ("count", "depth")

Reorg = Tuple[str, int]


class TaggedTransitions(StateTransitions):
    """pto's StateTransitions plus the reorgs each transition causes."""

    def __init__(self) -> None:
        super().__init__()
        # next_state -> {(kind, depth): probability}
        self.reorgs: Dict[tuple, Dict[Reorg, float]] = {}

    def add(self, next_state: tuple, probability: float = 0, reward: float = 0,
            difficulty_contribution: float = 0, allow_merging: bool = False,
            reorgs: Iterable[Reorg] = ()) -> None:
        super().add(next_state, probability=probability, reward=reward,
                    difficulty_contribution=difficulty_contribution,
                    allow_merging=allow_merging)
        for kind, depth in reorgs:
            if depth <= 0:
                continue
            tags = self.reorgs.setdefault(next_state, {})
            tags[(kind, depth)] = tags.get((kind, depth), 0.0) + probability


class TaggedModel(BlockchainModel):
    """Base for protocol models: the objective switch on top of tagged transitions.

    Subclasses implement `get_tagged_transitions` (revenue rewards, reorg tags)
    and set `self.objective`, `self.min_depth` and `self.weight` before calling
    `super().__init__()` (use `init_objective`).
    """

    def init_objective(self, objective: str = "revenue", min_depth: int = 11,
                       weight: str = "count") -> None:
        if objective not in OBJECTIVES:
            raise ValueError(f"objective must be one of {OBJECTIVES}")
        if weight not in WEIGHTS:
            raise ValueError(f"weight must be one of {WEIGHTS}")
        if min_depth < 1:
            raise ValueError("min_depth must be at least 1")
        self.objective = objective
        self.min_depth = min_depth
        self.weight = weight

    def objective_key(self) -> tuple:
        return self.objective, self.min_depth, self.weight

    def reorg_weight(self, depth: int) -> float:
        if depth < self.min_depth:
            return 0.0
        return 1.0 if self.weight == "count" else float(depth)

    def get_tagged_transitions(self, state: BlockchainModel.State, action: BlockchainModel.Action,
                               check_valid: bool = True) -> TaggedTransitions:
        raise NotImplementedError

    def get_state_transitions(self, state: BlockchainModel.State, action: BlockchainModel.Action,
                              check_valid: bool = True) -> TaggedTransitions:
        transitions = self.get_tagged_transitions(state, action, check_valid)
        if self.objective == "revenue":
            return transitions
        for next_state, probability in transitions.probabilities.items():
            if transitions.rewards[next_state] < 0:
                continue  # keep the illegal-action penalty
            gain = sum(q * self.reorg_weight(depth)
                       for (kind, depth), q in transitions.reorgs.get(next_state, {}).items()
                       if kind == MAJORITY)
            transitions.rewards[next_state] = gain / probability if probability > 0 else 0.0
        return transitions

    def get_honest_revenue(self) -> float:
        # the honest policy causes no reorgs
        return self.alpha if self.objective == "revenue" else 0.0


def stationary_distribution(model: BlockchainModel, policy, method: str = "direct"
                            ) -> Tuple[SparseBlockchainMDP, np.ndarray]:
    """Stationary distribution of the policy's Markov chain.

    "direct" (default): restrict the chain to the states reachable from the
    initial state and solve pi (P - I) = 0, sum(pi) = 1 with a sparse LU
    factorisation; exact to round-off, so rates far below 1e-13 survive.
    "eigs": pto's way (ARPACK on the whole chain); its round-off of about
    1e-13 of the largest probability swamps rare states (2026-11-16: a SoP
    rate of 3e-13 came out as 1.3e-8).
    """
    from scipy.sparse import csr_matrix, identity
    from scipy.sparse.csgraph import breadth_first_order
    from scipy.sparse.linalg import spsolve

    mdp = SparseBlockchainMDP(model)
    mdp.build_mdp()
    chain = csr_matrix(mdp.get_policy_induced_chain(policy))
    if method == "eigs":
        chain = chain.tolil()
        chain[mdp.final_state_index, mdp.final_state_index] = 0
        pi = np.real(np.asarray(mdp.calc_steady_distribution(chain.tocsr()))).flatten()
        pi[pi < 1e-13 * pi.max()] = 0.0
        return mdp, pi / pi.sum()
    if method != "direct":
        raise ValueError("method must be direct or eigs")
    reach = breadth_first_order(chain, mdp.initial_state_index, directed=True, return_predecessors=False)
    if mdp.final_state_index in set(reach.tolist()):
        raise ValueError("the policy reaches the final state (an illegal action)")
    reach = np.sort(reach)
    sub = chain[reach][:, reach]
    n = len(reach)
    a = (sub.T - identity(n, format="csr")).tolil()
    a[n - 1, :] = np.ones(n)          # replace one balance row by the normalisation
    b = np.zeros(n)
    b[n - 1] = 1.0
    sol = spsolve(a.tocsc(), b)
    pi = np.zeros(chain.shape[0])
    pi[reach] = np.clip(sol, 0.0, None)
    return mdp, pi / pi.sum()


def reorg_profile(model: TaggedModel, policy, max_report_depth: Optional[int] = None,
                  method: str = "direct") -> dict:
    """Revenue and reorg rates per main-chain block under `policy`.

    The revenue is the attacker's share of main-chain blocks, whatever the
    model's objective. Depth histograms are keyed by kind, then depth.
    """
    _, pi = stationary_distribution(model, policy, method)
    revenue_model_objective = model.objective
    model.objective = "revenue"  # tags and revenue rewards, whatever was solved
    try:
        blocks = 0.0
        attacker = 0.0
        rates: Dict[str, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for index in np.nonzero(pi)[0]:
            weight = pi[index]
            state = model.state_space.index_to_element(int(index))
            action = model.action_space.index_to_element(int(policy[index]))
            transitions = model.get_state_transitions(state, action, check_valid=False)
            for next_state, probability in transitions.probabilities.items():
                blocks += weight * probability * transitions.difficulty_contributions[next_state]
                attacker += weight * probability * transitions.rewards[next_state]
                for (kind, depth), q in transitions.reorgs.get(next_state, {}).items():
                    rates[kind][depth] += weight * q
    finally:
        model.objective = revenue_model_objective
    if blocks <= 0:
        raise ValueError("the policy adds no blocks to the main chain")
    return _summarise(attacker / blocks, {k: {d: v / blocks for d, v in hist.items()}
                                          for k, hist in rates.items()},
                      model.min_depth, max_report_depth)


def simulate_profile(model: TaggedModel, policy, steps: int, seed: int = 1,
                     max_report_depth: Optional[int] = None) -> dict:
    """Monte Carlo estimate of `reorg_profile` over one long run of `steps` transitions."""
    rng = np.random.default_rng(seed)
    revenue_model_objective = model.objective
    model.objective = "revenue"
    cache: Dict[int, tuple] = {}
    try:
        state = model.initial_state
        blocks = 0.0
        attacker = 0.0
        counts: Dict[str, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for _ in range(steps):
            index = model.state_space.element_to_index(state)
            if index not in cache:
                action = model.action_space.index_to_element(int(policy[index]))
                transitions = model.get_state_transitions(state, action, check_valid=False)
                next_states = list(transitions.probabilities)
                probabilities = np.array([transitions.probabilities[s] for s in next_states])
                cache[index] = (next_states, probabilities / probabilities.sum(), transitions)
            next_states, probabilities, transitions = cache[index]
            next_state = next_states[rng.choice(len(next_states), p=probabilities)]
            if next_state == model.final_state:
                raise ValueError(f"the policy takes an illegal action in state {state}")
            blocks += transitions.difficulty_contributions[next_state]
            attacker += transitions.rewards[next_state]
            p = transitions.probabilities[next_state]
            for (kind, depth), q in transitions.reorgs.get(next_state, {}).items():
                # a tag covers part of the transition's probability (gamma splits)
                if rng.random() < q / p:
                    counts[kind][depth] += 1
            state = next_state
    finally:
        model.objective = revenue_model_objective
    return _summarise(attacker / blocks, {k: {d: v / blocks for d, v in hist.items()}
                                          for k, hist in counts.items()},
                      model.min_depth, max_report_depth, blocks=blocks)


def _summarise(revenue: float, rates: Dict[str, Dict[int, float]], min_depth: int,
               max_report_depth: Optional[int], blocks: Optional[float] = None) -> dict:
    out = {"revenue": revenue}
    for kind in (MAJORITY, MINORITY):
        hist = rates.get(kind, {})
        out[f"{kind}_reorgs_per_block"] = sum(hist.values())
        out[f"{kind}_deep_reorgs_per_block"] = sum(v for d, v in hist.items() if d >= min_depth)
        total = sum(hist.values())
        out[f"{kind}_mean_depth"] = sum(d * v for d, v in hist.items()) / total if total > 0 else 0.0
        top = max(hist) if hist else 0
        if max_report_depth is not None:
            top = min(top, max_report_depth)
        out[f"{kind}_depth_rates"] = {d: hist[d] for d in sorted(hist) if d <= top}
    out["min_depth"] = min_depth
    if blocks is not None:
        out["blocks"] = blocks
    return out
