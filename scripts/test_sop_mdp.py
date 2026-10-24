"""Tests for scripts/sop_mdp.py: transition pieces against the race model's
rules, vectorised code against the scalar spec, and the stubborn-policy chain
against a Monte Carlo run of sop_race_model.simulate with the same rules."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import sop_mdp as M                                   # noqa: E402
import sop_race_model as R                            # noqa: E402

CAPS = M.Caps(a_max=6, h_max=6, d_max=120, p_max=40, deficit=40)
TINY = M.Caps(2, 2, 24, 6, 8)


def test_share_events_accumulate_pending():
    s = M.event(M.START, True, False, CAPS)
    assert s == (0, 0, 0, 1, 0, 0, 0)
    s = M.event(s, False, False, CAPS)
    assert s == (0, 0, 0, 1, 0, 0, 1)


def test_block_embeds_pending_and_window_progress_skips_first_block():
    s = (0, 0, 0, 3, 0, 0, 2)
    s = M.event(s, True, True, CAPS)        # attacker block embeds 3 shares: weight +4
    assert s == (1, 4, 0, 0, 0, 0, 2)       # x stays 0: the first block's objects do not count
    s = M.event(s, True, False, CAPS)
    s = M.event(s, True, True, CAPS)        # second block + 1 share: x advances by 2, D by 2
    assert s == (2, 6, 2, 0, 0, 0, 2)
    s = M.event(s, False, True, CAPS)       # honest block embeds its 2: D -= 3
    assert s == (2, 3, 2, 0, 1, 0, 0)


def test_window_cap_collapse_and_acceptance():
    s = (2, 30, 31, 0, 1, 5, 0)
    assert not M.past_window(s)
    s = M.event(s, True, False, CAPS); s = M.event(s, True, True, CAPS)
    assert s[2] == s[5] == M.WINDOW and M.past_window(s)     # both collapse to 32
    assert M.accepted(s, own_pending=False)
    t = (3, 0, 32, 4, 2, 32, 0)             # equal weights: own pending decides
    assert not M.accepted(t, own_pending=False)
    assert M.accepted(t, own_pending=True)
    assert not M.accepted((3, 5, 32, 0, 2, 32, 5), False)   # honest pending counts for honest


def test_resets_match_race_model():
    s = (2, 10, 32, 5, 1, 32, 3)
    assert M.do_reveal(s) == ((0, 0, 0, 5, 0, 0, 0), 2, 0)     # att pending carries, honest pending lost
    assert M.do_give_up(s) == ((0, 0, 0, 0, 0, 0, 3), 0, 1)    # honest pending carries
    assert M.do_publish((2, 30, 32, 5, 0, 0, 3)) == ((0, 0, 0, 5, 0, 0, 3), 2, 0)
    assert M.deficit((1, -7, 0, 2, 1, 0, 4)) == 9


def test_actions_offer_reveal_only_when_accepted_and_publish_only_without_honest():
    names = {a for a, *_ in M.actions((1, 5, 0, 0, 0, 0, 0), CAPS, False)}
    assert names == {M.HOLD, M.PUBLISH, M.GIVE_UP}
    names = {a for a, *_ in M.actions((3, 40, 32, 0, 1, 32, 0), CAPS, False)}
    assert names == {M.HOLD, M.REVEAL, M.GIVE_UP}
    names = {a for a, *_ in M.actions((1, -19, 0, 0, 1, 0, 0), CAPS, False)}
    assert names == {M.HOLD, M.GIVE_UP}
    # at a cap the resolution is forced
    assert [a for a, *_ in M.actions((6, 40, 32, 0, 1, 32, 0), CAPS, False)] == [M.REVEAL]
    assert [a for a, *_ in M.actions((1, -60, 0, 0, 3, 32, 0), CAPS, False)] == [M.GIVE_UP]


def _perm(order, keys):
    pos = {int(k): i for i, k in enumerate(keys.tolist())}
    return {i: pos[M.key_of(s)] for i, s in enumerate(order)}


@pytest.mark.parametrize("own", [False, True])
def test_vectorised_enumeration_and_tables_match_scalar(own):
    index, order = M.enumerate_states(TINY, own)
    keys = M.enumerate_keys(TINY, own)
    assert sorted(M.key_of(s) for s in order) == keys.tolist()
    nxt_s, ra_s, rh_s = M.build_tables(order, index, TINY, own)
    nxt_v, ra_v, rh_v = M.build_tables_v(keys, TINY, own)
    perm = _perm(order, keys)
    for i in range(len(order)):
        j = perm[i]
        for e in range(4):
            for act in range(4):
                if nxt_s[i, e, act] < 0:
                    assert nxt_v[j, e, act] < 0
                else:
                    assert nxt_v[j, e, act] == perm[int(nxt_s[i, e, act])]
                    assert (ra_v[j, e, act], rh_v[j, e, act]) == (ra_s[i, e, act], rh_s[i, e, act])


@pytest.mark.parametrize("own", [False, True])
def test_vectorised_stubborn_matches_scalar(own):
    pol = M.make_stubborn(TINY, 5, own, own)
    index, order = M.enumerate_states(TINY, own, policy=pol)
    keys = M.enumerate_keys(TINY, own, stubborn=(5, own, own))
    assert sorted(M.key_of(s) for s in order) == keys.tolist()
    nxt_s, _, _ = M.build_tables(order, index, TINY, own, policy=pol)
    nxt_v, _, _ = M.build_tables_v(keys, TINY, own, stubborn=(5, own, own))
    perm = _perm(order, keys)
    for i in range(len(order)):
        for e in range(4):
            assert sorted(perm[int(x)] for x in nxt_s[i, e] if x >= 0) == sorted(int(x) for x in nxt_v[perm[i], e] if x >= 0)


def test_enumeration_grows_with_caps():
    n_small = len(M.enumerate_keys(M.Caps(3, 3, 40, 12, 12), False))
    n_big = len(M.enumerate_keys(M.Caps(3, 3, 60, 16, 16), False))
    assert 10 < n_small < n_big


def _mc_share(alpha, own, days=400, seed=3):
    cfg = R.SimConfig(alpha=alpha, d=5, rule="sop", attacker_embeds=True, days=days, seed=seed,
                      give_up_objects=5, **R.RULE_PRESETS["20261020" if own else "20261020_noown"])
    return R.simulate(cfg).attacker_revenue_share


@pytest.mark.parametrize("own", [True, False])
def test_stubborn_chain_matches_race_model_monte_carlo(own):
    """The chain with the race model's own policy and the race model's own
    acceptance (network counts own pending iff the test does) reproduces the
    Monte Carlo share within its noise."""
    alpha = 0.45
    caps = M.Caps(a_max=10, h_max=10, d_max=200, p_max=48, deficit=60)
    keys = M.enumerate_keys(caps, own, stubborn=(5, own, own))
    nxt, ra, rh = M.build_tables_v(keys, caps, own, stubborn=(5, own, own))
    rho, _ = M.share_for(nxt, ra, rh, M.event_probs(alpha), optimise=False)
    mc = sum(_mc_share(alpha, own, seed=s) for s in range(1, 4)) / 3
    assert abs(rho - mc) < 0.03, (rho, mc)
