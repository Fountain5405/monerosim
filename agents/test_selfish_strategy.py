# agents/test_selfish_strategy.py
from agents.selfish_strategy import SelfishStrategy, ReleaseDecision


def test_honest_always_releases_everything():
    s = SelfishStrategy("honest", start_height=0)
    d = s.update(pub_height=5, priv_height=5)
    assert d.release_to == 4 and d.adopt_public is False
    d = s.update(pub_height=5, priv_height=7)
    assert d.release_to == 6


def test_withholds_while_strictly_ahead():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    # fork starts at 0; honest hasn't moved (h==0), attacker mined 2 -> withhold
    d = s.update(pub_height=0, priv_height=2)
    assert d.release_to is None and d.adopt_public is False
    assert s.fork == 0


def test_lead_two_then_honest_catches_one_reveals_and_wins():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=2)          # lead 2, withhold
    d = s.update(pub_height=1, priv_height=2)        # a=2,h=1 -> a-h==1 -> reveal all
    assert d.release_to == 1                          # release indexes 0..1
    assert s.fork == 2                                # attacker chain is now public
    assert d.adopt_public is False


def test_tie_then_attacker_extends_wins():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=1)            # lead 1, withhold (h==0)
    d = s.update(pub_height=1, priv_height=1)         # a==h==1 -> tie, release match
    assert d.release_to == 0
    assert s.fork == 0                                # fork not moved on a tie
    d = s.update(pub_height=1, priv_height=2)         # a=2,h=1 -> reveal-and-win
    assert d.release_to == 1 and s.fork == 2


def test_tie_then_honest_extends_adopts():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=1)
    s.update(pub_height=1, priv_height=1)            # tie
    d = s.update(pub_height=2, priv_height=1)         # a=1,h=2 -> a<h -> adopt
    assert d.adopt_public is True and d.release_to is None
    assert s.fork == 2


def test_honest_overtakes_from_lead_adopts():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=1)            # lead 1, withhold
    d = s.update(pub_height=2, priv_height=1)         # honest jumped 2 -> a<h -> adopt
    assert d.adopt_public is True and s.fork == 2


def test_warmup_before_start_height_behaves_honestly():
    s = SelfishStrategy("eyal_sirer", start_height=10)
    d = s.update(pub_height=4, priv_height=6)         # below start_height -> honest
    assert d.release_to == 5 and d.adopt_public is False


def test_reveal_win_release_from_is_old_fork():
    # Review C1: the reveal must release from the OLD fork (covering the withheld
    # blocks), and fork only advances afterward.
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=2)        # lead 2, withhold, fork stays 0
    d = s.update(pub_height=1, priv_height=2)     # a=2,h=1 -> reveal-and-win
    assert d.release_to == 1
    assert d.release_from == 0                     # covers indexes 0..1, not empty
    assert s.fork == 2                             # fork advances only after the decision


def test_eyal_sirer_forward_to_is_none():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    for pub, priv in [(0, 2), (1, 2), (2, 2), (3, 2)]:
        assert s.update(pub, priv).forward_to is None


def test_honest_forward_to_is_none():
    s = SelfishStrategy("honest", start_height=0)
    assert s.update(5, 5).forward_to is None


def _triple(d):
    return (d.release_to, d.forward_to, d.adopt_public)


def test_trail_stubborn_holds_within_depth_then_concedes():
    s = SelfishStrategy("trail_stubborn", start_height=0); s.trail_depth = 2
    s.update(0, 1)                         # lead 1, withhold
    assert _triple(s.update(2, 1)) == (None, 0, False)   # behind 1 (<=2): hold, forward_to=fork(0)
    assert _triple(s.update(3, 1)) == (None, 0, False)   # behind 2 (<=2): still hold
    d = s.update(4, 1)                     # behind 3 (>2): concede
    assert d.adopt_public is True and d.forward_to is None and s.fork == 4


def test_trail_stubborn_depth_zero_is_eyal_sirer():
    s0 = SelfishStrategy("trail_stubborn", start_height=0); s0.trail_depth = 0
    e = SelfishStrategy("eyal_sirer", start_height=0)
    for pub, priv in [(0, 2), (1, 2), (2, 1), (2, 3)]:
        assert _triple(s0.update(pub, priv)) == _triple(e.update(pub, priv))


def test_equal_fork_stubborn_holds_one_round_out_of_tie():
    s = SelfishStrategy("equal_fork_stubborn", start_height=0)
    s.update(0, 1)                         # lead 1
    assert _triple(s.update(1, 1)) == (0, None, False)   # tie: contest (release match), _was_tie set
    assert _triple(s.update(2, 1)) == (None, 0, False)   # honest +1 out of tie: hold one round
    d = s.update(3, 1)                     # honest 2 ahead: concede
    assert d.adopt_public is True and s.fork == 3


def test_lead_stubborn_override_reveals_only_to_tip():
    s = SelfishStrategy("lead_stubborn", start_height=0)
    s.update(0, 2)                         # lead 2, withhold
    d = s.update(1, 2)                     # a-h==1 override: reveal only to honest tip
    assert d.release_to == 0 and d.forward_to is None and s.fork == 0   # top (idx1) kept hidden


def test_lead_stubborn_cashes_lead_when_two_ahead():
    # Regression (2026-09-13 bug): lead_stubborn had no winning commit path and
    # realized 0.000 share (attacker orphan 1.000). Once it is >=2 ahead of an
    # active honest chain it must cash -- reveal the whole branch and advance fork
    # (a strictly-longer overtake win).
    s = SelfishStrategy("lead_stubborn", start_height=0)
    s.update(0, 2)                         # lead 2, honest idle -> withhold
    s.update(1, 2)                         # a-h==1 -> hold top (tie), fork stays 0
    d = s.update(1, 3)                     # attacker extends: a=3,h=1 -> a-h>=2 -> CASH
    assert d.release_to == 2               # reveal whole branch, indexes 0..2
    assert d.release_from == 0
    assert d.adopt_public is False
    assert s.fork == 3                     # fork advances -> the attacker wins


def test_lead_stubborn_withholds_while_honest_idle():
    # The cash arm must require h>0: while honest has not moved (h==0), a >=2 lead
    # stays secret (withhold), never revealed.
    s = SelfishStrategy("lead_stubborn", start_height=0)
    d = s.update(0, 3)                     # a=3,h=0 -> h==0 -> withhold, NOT cash
    assert d.release_to is None and d.adopt_public is False and s.fork == 0


def test_every_withholding_strategy_has_a_winning_commit_path():
    # Regression for the 2026-09-13 lead_stubborn bug: a strategy that can only
    # advance `fork` by conceding (adopt_public) never places a block on the
    # canonical chain (realized 0.000 share, orphan 1.000). Over a favorable game
    # -- attacker builds a 3-lead, then honest catches up -- every withholding
    # strategy must commit at least one win (fork advances on a non-adopt step).
    favorable = ["a", "a", "a", "h", "h"]
    for name in ("eyal_sirer", "trail_stubborn", "equal_fork_stubborn", "lead_stubborn"):
        s = SelfishStrategy(name, start_height=0)
        pub = priv = 0
        won = False
        for ev in favorable:
            if ev == "a":
                priv += 1
            else:
                pub += 1
            before = s.fork
            d = s.update(pub, priv)
            if s.fork > before and not d.adopt_public:
                won = True
                break
        assert won, f"{name} has no winning commit path (only advances fork by conceding)"
