"""Tests for the tight SoP disruption model (sop_tight.py)."""
import numpy as np
import pytest

pytest.importorskip("scipy")

from studies.sop.countermeasures.howard import solve_tables  # noqa: E402
from studies.sop.countermeasures.sop_tight import (GIVE_UP, HOLD, PUBLISH, REVEAL, TightSoP,  # noqa: E402
                                                   exact_rate, profile)
from studies.sop.scripts import sop_mdp as M  # noqa: E402


def small():
    return TightSoP(0.45, min_depth=2, x_min=-20, x_max=20, p_max=20, q_max=20)


def test_index_round_trip_and_rows():
    m = small()
    P, r, d, legal = m.tables()
    idx = np.arange(m.n)
    assert all((np.asarray(a) == np.asarray(b)).all()
               for a, b in zip(m.decode(m.index(*m.decode(idx))), m.decode(idx)))
    for a in range(4):
        assert np.allclose(P[a].sum(axis=1).A.ravel(), 1.0)
    h, a1, x, pa, ph = m.decode(idx)
    assert legal[HOLD].all()
    assert (legal[REVEAL] == ((a1 == 1) & (h >= 1) & (x - pa > 0))).all()
    assert not legal[GIVE_UP][(h == 0) & (a1 == 0)].any()
    assert not legal[PUBLISH][h >= 1].any()


def test_restarts_follow_the_exact_game():
    m = small()
    P, _, _, _ = m.tables()
    s = (2, 3, 0, 4, 1, 0, 6)              # a, D, xa, pa, h, xh, ph (exact)
    i = m.from_exact(s)
    for act, fn in [(REVEAL, M.do_reveal), (GIVE_UP, M.do_give_up)]:
        j = P[act][i].indices[0]
        assert j == m.from_exact(fn(s)[0])


def test_howard_value_equals_profile():
    m = small()
    P, r, d, legal = m.tables()
    policy, g, _ = solve_tables(P, r, d, legal, m.start, cur=m.initial_policy())
    assert g > 0
    assert profile(P, r, d, policy, m.start)["rate"] == pytest.approx(g, rel=1e-6)


def test_exact_game_without_window_is_close_to_the_model():
    """The tight model differs from the exact game only by the window and its caps."""
    m = TightSoP(0.45, min_depth=2, x_min=-24, x_max=24, p_max=30, q_max=30)
    P, r, d, legal = m.tables()
    policy, g, _ = solve_tables(P, r, d, legal, m.start, cur=m.initial_policy())
    res = exact_rate(m, policy, 2_000_000, seed=3, window=False)
    assert res["deep"] > 1000
    assert res["rate"] == pytest.approx(g, rel=0.1)
