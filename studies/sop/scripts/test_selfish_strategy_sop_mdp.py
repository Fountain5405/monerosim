"""SelfishStrategy.observation() (core, agents/selfish_strategy.py) must agree
with the SoP exact MDP's state after the same events (sop_mdp.py here).

Moved out of agents/test_selfish_strategy.py by the 2026-11-01 reorganization,
so that core tests import no study code.
"""
from agents.selfish_strategy import SelfishStrategy
from studies.sop.scripts import sop_mdp as M


def test_learned_observation_matches_sop_mdp():
    # fork at 100; attacker 2 blocks (3 and 1 embedded shares), 2 pending; honest 1 block (0 shares), 5 pending
    w = (6, 6, 1, 2, 0, 8, 6, 1)
    assert SelfishStrategy.observation(2, 1, w) == (2, 5, 2, 2, 1, 0, 5)
    s = M.event(M.event(M.event(M.START, True, True, M.Caps()), True, False, M.Caps()), True, False, M.Caps())
    # one attacker block then two attacker shares: a=1, D=1, pa=2
    assert SelfishStrategy.observation(1, 0, (1, 1, 0, 0, 0, 3, 0, 0)) == s
