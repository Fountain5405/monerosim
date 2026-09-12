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
