"""Tests for scripts/sop_mdp.py: transition pieces against the race model's
rules, vectorised code against the scalar spec, and the stubborn-policy chain
against a Monte Carlo run of sop_race_model.simulate with the same rules."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import random                                          # noqa: E402
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


@pytest.mark.parametrize("own", [False, True])
def test_compact_solver_matches_dense_on_small_caps(own):
    caps = M.Caps(3, 3, 40, 10, 12)
    keys = M.enumerate_keys(caps, own)
    nxt, ra, rh = M.build_tables_v(keys, caps, own)
    probs = M.event_probs(0.45)
    rho_dense, _ = M.share_for(nxt, ra, rh, probs, optimise=True)
    C = M.Compact(keys, caps, own)
    rho_c, _ = C.share(0.45, optimise=True)
    assert abs(rho_dense - rho_c) < 2e-4, (rho_dense, rho_c)
    stub = (5, own, own)
    keys = M.enumerate_keys(caps, own, stubborn=stub)
    nxt, ra, rh = M.build_tables_v(keys, caps, own, stubborn=stub)
    rho_dense, _ = M.share_for(nxt, ra, rh, probs, optimise=False)
    rho_c, _ = M.Compact(keys, caps, own, stubborn=stub).share(0.45, optimise=False)
    assert abs(rho_dense - rho_c) < 2e-4, (rho_dense, rho_c)


def test_enumeration_grows_with_caps():
    n_small = len(M.enumerate_keys(M.Caps(3, 3, 40, 12, 12), False))
    n_big = len(M.enumerate_keys(M.Caps(3, 3, 60, 16, 16), False))
    assert 10 < n_small < n_big


def _mc_chain(alpha, caps, own_test, own_net, days, seed, idle_drop=False):
    """Monte Carlo of the scalar chain (event + stubborn_action), G = 5."""
    rng = random.Random(seed)
    s = M.START
    att = hon = 0
    for _ in range(int(days * 720 * M.W_SHARES)):
        s = M.event(s, rng.random() < alpha, rng.random() < 1.0 / M.W_SHARES, caps)
        _, s, fa, fh = M.stubborn_action(s, caps, 5, own_test, own_net)
        att += fa
        hon += fh
        if idle_drop and s[0] == 0 and s[4] == 0 and M.deficit(s) > 5:
            s = (0, 0, 0, 0, 0, 0, s[6])    # the race model's objects give-up fires while idle
    return att / (att + hon)


@pytest.mark.parametrize("own", [True, False])
def test_stubborn_chain_matches_capped_race_model_monte_carlo(own):
    """The chain with 3-block caps and no share caps against sop_race_model
    Model B with cap_blocks=3 (same forced publish/reveal/give-up at the cap).
    The race model's objects give-up also fires while the attacker holds no
    block and then drops its pending shares; the chain keeps them (idle_drop
    mirrors the race model; without it the chain is ~5 % higher: 0.107 vs
    0.1025 own, 0.1007 vs 0.096 noown at 2000 d, 2026-10-25)."""
    alpha = 0.45
    caps = M.Caps(3, 3, 100000, 100000, 100000)
    cfg = R.SimConfig(alpha=alpha, d=1, rule="sop", attacker_embeds=True, days=500, seed=2,
                      give_up_objects=5, cap_blocks=3,
                      **R.RULE_PRESETS["20261020" if own else "20261020_noown"])
    race = R.simulate(cfg).attacker_revenue_share
    chain = _mc_chain(alpha, caps, own, own, 500, 2, idle_drop=True)
    assert abs(chain - race) < 0.004, (chain, race)


def test_value_iteration_matches_chain_monte_carlo():
    """Compact relative VI on the stubborn chain (3/3/40/12/12, count/count)
    against a Monte Carlo of the same chain: 0.1334 vs 0.1343 on 2026-10-25.
    (Those caps cannot reach the window, so all the revenue is forced
    publishes at a == 3, which is exactly the cap rule being checked.)"""
    caps = M.Caps(3, 3, 40, 12, 12)
    stub = (5, True, True)
    keys = M.enumerate_keys(caps, True, stubborn=stub)
    rho, _ = M.Compact(keys, caps, True, stubborn=stub).share(0.45, optimise=False)
    mc = _mc_chain(0.45, caps, True, True, 500, 1)
    assert abs(rho - mc) < 0.006, (rho, mc)


def test_window_reach_matches_race_model_counting():
    """x advances only on a branch's own blocks after its first, by 1 + embedded
    shares (race model either_window: sum(1 + n for n in blocks[1:])). Caps that
    cannot reach the window make every withheld block a loss (2026-10-25: the
    3/3/40/12/12 timing run scored the stubborn chain 0.0000 for that reason)."""
    assert M.window_reach(M.Caps(3, 3, 40, 12, 12)) == (26, 26)
    assert max(M.window_reach(M.Caps(3, 3, 40, 12, 12))) < M.WINDOW
    assert M.window_reach(M.Caps(4, 4, 64, 24, 24)) == (75, 75)
    assert M.window_reach(M.Caps(3, 3, 48, 20, 20)) == (42, 42)
