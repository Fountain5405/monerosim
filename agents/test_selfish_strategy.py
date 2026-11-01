# agents/test_selfish_strategy.py
import pytest
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


def test_release_lead_two_cashes_at_lead_two():
    # Qubic's observed conservative policy (Lee & Kim 2025): reveal the whole
    # branch while still two clear of an active honest chain, instead of
    # waiting for honest to close to one behind (eyal_sirer).
    s = SelfishStrategy("eyal_sirer", start_height=0, release_lead=2)
    assert _triple(s.update(0, 3)) == (None, None, False)      # h==0: free lead, withhold
    d = s.update(1, 3)                                          # a=3,h=1, a-h==2 -> cash out
    assert d.release_to == 2 and d.release_from == 0            # reveal indexes 0..2
    assert d.adopt_public is False and s.fork == 3              # strictly longer: the win commits


def test_release_lead_two_withholds_beyond_lead_two():
    s = SelfishStrategy("eyal_sirer", start_height=0, release_lead=2)
    assert _triple(s.update(1, 4)) == (None, None, False)      # a-h==3: keep withholding
    d = s.update(2, 4)                                          # honest +1 -> a-h==2 -> cash
    assert d.release_to == 3 and d.release_from == 0 and s.fork == 4


def test_release_lead_two_tie_and_concede_arms_unchanged():
    s = SelfishStrategy("eyal_sirer", start_height=0, release_lead=2)
    s.update(0, 1)                                              # lead 1, h==0: withhold
    d = s.update(1, 1)                                          # tie: contest, fork unmoved
    assert _triple(d) == (0, None, False) and s.fork == 0
    d = s.update(2, 1)                                          # a<h: concede
    assert d.adopt_public is True and s.fork == 2


def test_release_lead_one_is_eyal_sirer():
    k1 = SelfishStrategy("eyal_sirer", start_height=0, release_lead=1)
    es = SelfishStrategy("eyal_sirer", start_height=0)          # default
    # monotone game: free lead, tie, cash, free lead, catch to one
    for pub, priv in [(0, 1), (1, 1), (1, 2), (2, 3), (2, 4), (3, 4)]:
        assert _triple(k1.update(pub, priv)) == _triple(es.update(pub, priv)), (pub, priv)


def test_release_lead_rejects_nonpositive():
    try:
        SelfishStrategy("eyal_sirer", start_height=0, release_lead=0)
    except ValueError:
        return
    raise AssertionError("release_lead=0 must raise")
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


# --- window_stubborn (Share-or-Perish attack) -------------------------------

def test_window_stubborn_rejects_bad_give_up_depth():
    try:
        SelfishStrategy("window_stubborn", start_height=0, give_up_depth=0)
    except ValueError:
        pass
    else:
        raise AssertionError("give_up_depth=0 must raise")


def test_window_stubborn_rejects_bad_window_objects():
    try:
        SelfishStrategy("window_stubborn", start_height=0, window_objects=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("window_objects=-1 must raise")


def test_window_stubborn_window_zero_reveals_on_weight_alone():
    """window_objects=0 is the stock cells' "no window": stock has no SoP
    window, so the attacker reveals as soon as it is heavier. Before
    2026-09-30 the strategy rejected 0 on every tick and the stock smoke
    attacker never published."""
    s = SelfishStrategy("window_stubborn", start_height=0, window_objects=0)
    s.update(0, 1)
    d = s.update(1, 2, branch_weights=lambda fork, priv, pub: (1, 11, 10))
    assert d.release_to == 1 and d.release_from == 0 and d.adopt_public is False
    assert s.fork == 2
    s = SelfishStrategy("window_stubborn", start_height=0, window_objects=0)
    s.update(0, 1)
    d = s.update(1, 2, branch_weights=lambda fork, priv, pub: (1, 10, 10))  # weight tied
    assert d.release_to is None and d.adopt_public is False and d.forward_to == 0


def test_window_stubborn_a_zero_h_positive_adopts():
    s = SelfishStrategy("window_stubborn", start_height=0)
    d = s.update(pub_height=1, priv_height=0)
    assert d.adopt_public is True and d.release_to is None and d.forward_to is None
    assert s.fork == 1


def test_window_stubborn_h_zero_withholds():
    s = SelfishStrategy("window_stubborn", start_height=0)
    d = s.update(pub_height=0, priv_height=2)
    assert d.release_to is None and d.adopt_public is False and d.forward_to == 0
    assert s.fork == 0


def test_window_stubborn_tie_holds():
    s = SelfishStrategy("window_stubborn", start_height=0)
    s.update(0, 1)
    d = s.update(1, 1)
    assert d.release_to is None and d.adopt_public is False and d.forward_to == 0
    assert s.fork == 0


def test_window_stubborn_give_up_at_depth_one():
    s = SelfishStrategy("window_stubborn", start_height=0, give_up_depth=1)
    s.update(0, 1)                                   # a=1,h=0 withhold
    d = s.update(1, 1)                                # a=1,h=1: h-a==0==d-1 -> hold
    assert d.adopt_public is False and d.forward_to == 0
    d = s.update(2, 1)                                # a=1,h=2: h-a==1==d -> give up
    assert d.adopt_public is True and d.release_to is None and d.forward_to is None
    assert s.fork == 2


def test_window_stubborn_give_up_at_depth_two():
    s = SelfishStrategy("window_stubborn", start_height=0, give_up_depth=2)
    s.update(0, 1)
    d = s.update(1, 1)                                # a=1,h=1: h-a==0
    assert d.adopt_public is False and d.forward_to == 0
    d = s.update(2, 1)                                # a=1,h=2: h-a==1==d-1 -> still hold
    assert d.adopt_public is False and d.forward_to == 0
    d = s.update(3, 1)                                # a=1,h=3: h-a==2==d -> give up
    assert d.adopt_public is True and s.fork == 3


def test_window_stubborn_give_up_at_depth_three():
    s = SelfishStrategy("window_stubborn", start_height=0, give_up_depth=3)
    s.update(0, 1)
    d = s.update(1, 1)                                # h-a==0
    assert d.adopt_public is False
    d = s.update(2, 1)                                # h-a==1
    assert d.adopt_public is False
    d = s.update(3, 1)                                # h-a==2==d-1 -> still hold
    assert d.adopt_public is False and d.forward_to == 0
    d = s.update(4, 1)                                # h-a==3==d -> give up
    assert d.adopt_public is True and s.fork == 4


def test_window_stubborn_does_not_call_branch_weights_on_give_up_path():
    s = SelfishStrategy("window_stubborn", start_height=0, give_up_depth=1)
    s.update(0, 1)                                    # a=1,h=0 withhold

    def _boom(fork, priv, pub):
        raise AssertionError("branch_weights must not be called on the give-up path")

    d = s.update(2, 1, branch_weights=_boom)           # a=1,h=2: h-a==1==give_up_depth -> give up
    assert d.adopt_public is True and s.fork == 2


def test_window_stubborn_does_not_call_branch_weights_on_h_zero_path():
    s = SelfishStrategy("window_stubborn", start_height=0)

    def _boom(fork, priv, pub):
        raise AssertionError("branch_weights must not be called while honest is idle")

    d = s.update(0, 2, branch_weights=_boom)           # h==0: withhold
    assert d.adopt_public is False and d.release_to is None and d.forward_to == 0


def test_window_stubborn_below_window_holds_even_if_ahead_by_weight():
    s = SelfishStrategy("window_stubborn", start_height=0, window_objects=5)
    s.update(0, 1)
    d = s.update(1, 2, branch_weights=lambda fork, priv, pub: (4, 100, 1))   # objects 4 < window 5
    assert d.adopt_public is False and d.release_to is None and d.forward_to == 0
    assert s.last_weights == (4, 100, 1)
    assert s.fork == 0


def test_window_stubborn_past_window_but_not_ahead_by_weight_holds():
    s = SelfishStrategy("window_stubborn", start_height=0, window_objects=5)
    s.update(0, 1)
    d = s.update(1, 2, branch_weights=lambda fork, priv, pub: (5, 10, 10))  # weight tied
    assert d.adopt_public is False and d.release_to is None and d.forward_to == 0
    assert s.fork == 0


def test_window_stubborn_past_window_and_ahead_by_weight_reveals():
    s = SelfishStrategy("window_stubborn", start_height=0, window_objects=5)
    s.update(0, 1)
    d = s.update(1, 2, branch_weights=lambda fork, priv, pub: (5, 11, 10))  # weight ahead
    assert d.release_to == 1 and d.release_from == 0
    assert d.adopt_public is False and d.forward_to is None
    assert s.fork == 2
    assert s.last_weights == (5, 11, 10)


def test_window_stubborn_none_weights_holds():
    s = SelfishStrategy("window_stubborn", start_height=0)
    s.update(0, 1)
    d = s.update(1, 2, branch_weights=lambda fork, priv, pub: None)
    assert d.adopt_public is False and d.release_to is None and d.forward_to == 0
    assert s.last_weights is None
    assert s.fork == 0


def test_window_stubborn_default_branch_weights_uses_block_count_fallback():
    # No branch_weights callable: falls back to (a, a, h). With the default
    # window (48) the block-only arm needs a >= 48 and a > h to reveal.
    s = SelfishStrategy("window_stubborn", start_height=0)
    s.update(0, 1)
    priv = 1
    while priv < 48:
        priv += 1
        s.update(0, priv)
    d = s.update(47, priv)                             # a=48,h=47: fallback (48,48,47) -> reveal
    assert priv == 48
    assert d.release_to == priv - 1 and s.fork == priv
    assert d.adopt_public is False
    assert s.last_weights == (48, 48, 47, 47, 46, 48, 47)


# --- deep_hunt (2026-10-19): an attacker after a deep reorg, not revenue ---
# It withholds until the honest branch holds release_depth blocks past the
# fork, then reveals if it outweighs honest (the window still applies), and
# gives up once honest leads by give_up_depth blocks.

def test_deep_hunt_is_known_and_validates_release_depth():
    import pytest
    assert SelfishStrategy("deep_hunt", start_height=0).release_depth == 10
    with pytest.raises(ValueError):
        SelfishStrategy("deep_hunt", start_height=0, release_depth=0)


def test_deep_hunt_holds_while_honest_branch_is_shorter_than_release_depth():
    # Past the window and ahead by weight at every step, but the honest
    # branch is shorter than release_depth: keep withholding.
    s = SelfishStrategy("deep_hunt", start_height=0, release_depth=3, window_objects=0)
    s.update(0, 1)                                                   # a=1,h=0 withhold
    for pub, priv in ((1, 3), (2, 4)):                               # h=1, then h=2
        d = s.update(pub, priv, branch_weights=lambda f, p, q: (p - f, 10 * (p - f), 5 * (q - f)))
        assert d.release_to is None and d.adopt_public is False and d.forward_to == 0
        assert s.fork == 0


def test_deep_hunt_reveals_once_honest_reaches_release_depth_and_is_outweighed():
    s = SelfishStrategy("deep_hunt", start_height=0, release_depth=3, window_objects=0)
    s.update(0, 1)
    s.update(2, 4, branch_weights=lambda f, p, q: (4, 40, 20))       # h=2 < 3: hold
    d = s.update(3, 5, branch_weights=lambda f, p, q: (5, 50, 30))   # h=3: reveal
    assert d.release_from == 0 and d.release_to == 4
    assert d.adopt_public is False and d.forward_to is None
    assert s.fork == 5
    assert s.last_weights == (5, 50, 30)


def test_deep_hunt_at_release_depth_but_not_heavier_holds():
    s = SelfishStrategy("deep_hunt", start_height=0, release_depth=2, give_up_depth=3, window_objects=0)
    s.update(0, 1)
    d = s.update(2, 2, branch_weights=lambda f, p, q: (2, 20, 20))   # equal weight: hold
    assert d.release_to is None and d.adopt_public is False and d.forward_to == 0
    assert s.fork == 0


def test_deep_hunt_respects_the_window():
    # SoP: inside the window the branch can't win, whatever its weight.
    s = SelfishStrategy("deep_hunt", start_height=0, release_depth=1, window_objects=48)
    s.update(0, 1)
    d = s.update(1, 3, branch_weights=lambda f, p, q: (47, 470, 16))
    assert d.release_to is None and d.forward_to == 0
    d = s.update(1, 4, branch_weights=lambda f, p, q: (48, 480, 16))
    assert d.release_to == 3 and s.fork == 4


def test_deep_hunt_gives_up_once_honest_leads_by_give_up_depth():
    s = SelfishStrategy("deep_hunt", start_height=0, release_depth=10, give_up_depth=2, window_objects=0)
    s.update(0, 1)
    d = s.update(2, 1)                                  # a=1,h=2: h-a=1 < 2: hold
    assert d.adopt_public is False and d.forward_to == 0
    d = s.update(3, 1)                                  # h-a=2: give up
    assert d.adopt_public is True and d.release_to is None and d.forward_to is None
    assert s.fork == 3


def test_deep_hunt_does_not_attack_without_a_private_lead():
    s = SelfishStrategy("deep_hunt", start_height=0)
    d = s.update(1, 0)                                  # a=0,h=1
    assert d.adopt_public is True and s.fork == 1


def test_deep_hunt_release_depth_comes_from_the_agent_attributes():
    from agents.selfish_miner import SelfishMinerAgent
    kw = SelfishMinerAgent.strategy_kwargs({"strategy": "deep_hunt", "release_depth": "12"})
    assert kw["release_depth"] == 12
    assert SelfishMinerAgent.strategy_kwargs({})["release_depth"] == 10
    assert SelfishStrategy("deep_hunt", 0, **kw).release_depth == 12


def _ws(rule, objects=32):
    s = SelfishStrategy("window_stubborn", start_height=0, window_objects=objects,
                        give_up_depth=5, window_rule=rule)
    s.fork = 100
    return s


def test_window_rule_default_is_v3():
    assert SelfishStrategy("window_stubborn", 0).window_rule == "v3"


def test_window_rule_rejects_unknown():
    with pytest.raises(ValueError):
        SelfishStrategy("window_stubborn", 0, window_rule="nope")


def test_window_rule_20261020_excludes_first_block():
    s = _ws("20261020")
    # attacker 3 blocks, 60 objects of which 40 in its first block: 20 above it
    d = s.update(pub_height=101, priv_height=103, branch_weights=lambda f, p, q: (60, 6000, 1600, 20, 0))
    assert d.release_to is None
    d = s.update(pub_height=101, priv_height=103, branch_weights=lambda f, p, q: (72, 7200, 1600, 32, 0))
    assert d.release_to == 102


def test_window_rule_20261020_either_branch():
    s = _ws("20261020")
    # honest branch is past 32 above its first block; attacker heavier -> reveal
    d = s.update(pub_height=103, priv_height=104, branch_weights=lambda f, p, q: (40, 5000, 4900, 24, 33))
    assert d.release_to == 103


def test_window_rule_20261020_with_difficulty_weights_falls_back_to_v3():
    """A stock attacker (weigh difficulty) gets a 3-tuple from _branch_weights.
    Before 2026-10-25 the 20261020 branch then never set `past`, so the
    attacker held forever (sop_v4_o5_stock_72h: 0 reveals in 6 x 72 h)."""
    s = _ws("20261020", objects=0)
    # ahead by difficulty: reveal
    d = s.update(pub_height=101, priv_height=103, branch_weights=lambda f, p, q: (3, 3000, 1000))
    assert d.release_to == 102
    s = _ws("20261020", objects=0)
    # not ahead: hold
    d = s.update(pub_height=103, priv_height=104, branch_weights=lambda f, p, q: (4, 4000, 4000))
    assert d.release_to is None


def test_window_rule_v3_unchanged():
    s = _ws("v3", objects=48)
    d = s.update(pub_height=101, priv_height=103, branch_weights=lambda f, p, q: (60, 6000, 1600, 20, 0))
    assert d.release_to == 102          # v3: 60 >= 48 counts the first block


# --- give_up_objects: the race model's objects give-up (2026-10-23) ---

def _wo(o, d=5):
    s = SelfishStrategy("window_stubborn", start_height=0, window_objects=32,
                        give_up_depth=d, window_rule="20261020", give_up_objects=o)
    s.fork = 100
    return s


def _w7(att, hon, att_tot, hon_tot, att_w=1000, hon_w=2000):
    return lambda f, p, q: (att, att_w, hon_w, max(att - 1, 0), max(hon - 1, 0), att_tot, hon_tot)


def test_give_up_objects_default_is_off():
    assert SelfishStrategy("window_stubborn", 0).give_up_objects == -1


def test_give_up_objects_gives_up_once_honest_exceeds_by_more_than_o():
    s = _wo(5)
    d = s.update(pub_height=102, priv_height=102, branch_weights=_w7(30, 35, 30, 35))   # ahead by 5: hold
    assert d.adopt_public is False and d.release_to is None and s.fork == 100
    d = s.update(pub_height=102, priv_height=102, branch_weights=_w7(30, 35, 30, 36))   # by 6: give up
    assert d.adopt_public is True and d.release_to is None and d.forward_to is None and s.fork == 102


def test_give_up_objects_counts_pending_pool_shares():
    s = _wo(5)
    # branch objects equal; the honest tip pool holds 6 more pending shares -> give up
    d = s.update(pub_height=102, priv_height=102, branch_weights=_w7(30, 30, 30, 36))
    assert d.adopt_public is True and s.fork == 102


def test_give_up_objects_replaces_the_block_depth_rule():
    s = _wo(5, d=1)
    # honest leads by 2 blocks (the block rule at d=1 would give up) but not by objects: hold
    d = s.update(pub_height=103, priv_height=101, branch_weights=_w7(40, 36, 40, 36))
    assert d.adopt_public is False and s.fork == 100


def test_give_up_objects_still_adopts_when_no_private_block():
    s = _wo(5)

    def _boom(f, p, q):
        raise AssertionError("branch_weights must not be called when a == 0")

    d = s.update(pub_height=101, priv_height=100, branch_weights=_boom)   # a=0, h=1
    assert d.adopt_public is True and s.fork == 101


def test_give_up_objects_holds_on_short_or_missing_weights():
    s = _wo(5)
    d = s.update(pub_height=102, priv_height=102, branch_weights=lambda f, p, q: (30, 3000, 1000))
    assert d.adopt_public is False and d.release_to is None
    d = s.update(pub_height=102, priv_height=102, branch_weights=lambda f, p, q: None)
    assert d.adopt_public is False and d.release_to is None


def test_give_up_objects_then_reveals_when_past_window_and_heavier():
    s = _wo(5)
    d = s.update(pub_height=102, priv_height=103,
                 branch_weights=lambda f, p, q: (50, 5000, 3000, 34, 30, 50, 40))
    assert d.release_to == 102 and d.release_from == 100 and s.fork == 103


# ---- learned strategy (docs/superpowers/plans/2026-10-25-sop-rl-attacker.md, Task 5) ----

def _policy_file(tmp_path, entries, alpha=0.45, key_clip=None):
    import gzip
    import json
    p = tmp_path / "p.json.gz"
    with gzip.open(p, "wt") as f:
        json.dump({"meta": {"alpha": alpha, "env": "race"},
                   "key_clip": key_clip or {"d": 128, "p": 48, "d_bin": 1},
                   "fallback": "sim_stubborn", "policy": entries}, f)
    return str(p)


def test_learned_keys_through_the_policy_files_pending_bins(tmp_path):
    # key_clip p_bin 2: the observation (1, 2, 32, 5, 1, 32, 1) keys as (1, 2, 32, 2, 1, 32, 0),
    # where the file says hold; sim_stubborn (and an unbinned lookup) would reveal
    pf = _policy_file(tmp_path, {"1,2,32,2,1,32,0": "hold"},
                      key_clip={"d": 128, "p": 48, "d_bin": 1, "p_bin": 2})
    s = SelfishStrategy("learned", start_height=0, window_objects=32, window_rule="20261020",
                        give_up_objects=5, policy_file=pf)
    s.fork = 100
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (3, 3, 1, 32, 0, 8, 2, 1))
    assert d.release_to is None and s.learned_decisions == 1 and s.fallback_decisions == 0
    assert s.last_learned[0] == (1, 2, 32, 5, 1, 32, 1) and s.last_learned[1] == (1, 2, 32, 2, 1, 32, 0)


# ---- param_stubborn strategy (docs/20261026_sop_attacker_search.md, the searched family in the sim) ----

def test_param_stubborn_strategy_follows_the_knobs():
    # hold_shares 1: a pending-shares-only branch (a = 0) against an honest block is held, not given up
    s = SelfishStrategy("param_stubborn", start_height=0, window_objects=32, window_rule="20261020",
                        give_up_objects=8, hold_shares=1)
    s.fork = 100
    # a=0, h=1: D = 0 - 2 = -2, pa = 4, ph = 3 - 2 = 1 -> objects deficit 2 + 1 - 4 = -1 <= 8 -> hold
    d = s.update(pub_height=101, priv_height=100, branch_weights=lambda f, p, q: (0, 0, 2, 0, 0, 4, 3, 2))
    assert d.adopt_public is False and d.release_to is None and s.learned_decisions == 1
    s0 = SelfishStrategy("param_stubborn", start_height=0, window_objects=32, window_rule="20261020",
                         give_up_objects=8)
    s0.fork = 100
    d = s0.update(pub_height=101, priv_height=100, branch_weights=lambda f, p, q: (0, 0, 2, 0, 0, 4, 3, 2))
    assert d.adopt_public is True                      # hold_shares 0: the sim's rule gives up


def test_param_stubborn_publish_lead_and_reveal_margin():
    s = SelfishStrategy("param_stubborn", start_height=0, window_objects=32, window_rule="20261020",
                        give_up_objects=8, publish_lead=2, reveal_margin=4)
    s.fork = 100
    d = s.update(pub_height=100, priv_height=102, branch_weights=lambda f, p, q: (4, 4, 0, 2, 0, 4, 0, 0))   # a=2, h=0
    assert d.release_to == 101 and d.release_from == 100 and s.fork == 102
    s.fork = 100
    # a=2, h=1, past the window, D - ph = 3 - 1 = 2 < margin 4 although the network accepts (6 > 3 + 1): hold
    d = s.update(pub_height=101, priv_height=102, branch_weights=lambda f, p, q: (6, 6, 3, 32, 0, 6, 4, 3))
    assert d.release_to is None and s.suppressed_reveals == 0
    s.reveal_margin = 2
    d = s.update(pub_height=101, priv_height=102, branch_weights=lambda f, p, q: (6, 6, 3, 32, 0, 6, 4, 3))
    assert d.release_to == 101


def test_param_stubborn_rejects_bad_knobs():
    with pytest.raises(ValueError):
        SelfishStrategy("param_stubborn", start_height=0, give_up_objects=-1)     # needs the objects give-up
    with pytest.raises(ValueError):
        SelfishStrategy("param_stubborn", start_height=0, give_up_objects=5, reveal_margin=0)


def test_learned_requires_a_loadable_policy_file(tmp_path):
    with pytest.raises(ValueError):
        SelfishStrategy("learned", start_height=0)
    with pytest.raises(ValueError):
        SelfishStrategy("learned", start_height=0, policy_file=str(tmp_path / "missing.json.gz"))
    with pytest.raises(ValueError):
        SelfishStrategy("learned", start_height=0, policy_file=_policy_file(tmp_path, {}, alpha=0.40), alpha=0.45)


def test_learned_observation_matches_sop_mdp():
    from scripts import sop_mdp as M
    # fork at 100; attacker 2 blocks (3 and 1 embedded shares), 2 pending; honest 1 block (0 shares), 5 pending
    w = (6, 6, 1, 2, 0, 8, 6, 1)
    assert SelfishStrategy.observation(2, 1, w) == (2, 5, 2, 2, 1, 0, 5)
    s = M.event(M.event(M.event(M.START, True, True, M.Caps()), True, False, M.Caps()), True, False, M.Caps())
    # one attacker block then two attacker shares: a=1, D=1, pa=2
    assert SelfishStrategy.observation(1, 0, (1, 1, 0, 0, 0, 3, 0, 0)) == s


def test_learned_uses_table_then_falls_back_to_sim_stubborn(tmp_path):
    s = SelfishStrategy("learned", start_height=0, window_objects=32, window_rule="20261020",
                        give_up_objects=5, policy_file=_policy_file(tmp_path, {"1,2,32,0,1,32,1": "hold"}))
    s.fork = 100
    # stored state says hold where sim_stubborn would reveal (both x collapse to 32)
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (3, 3, 1, 32, 0, 3, 2, 1))
    assert d.release_to is None and s.learned_decisions == 1 and s.fallback_decisions == 0
    # unseen state: sim_stubborn reveals (past window, D 3 > ph 1)
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (4, 4, 1, 32, 0, 4, 2, 1))
    assert d.release_to == 100 and s.fallback_decisions == 1


def test_learned_reveal_is_suppressed_when_own_test_fails_and_publish_skips_it(tmp_path):
    pf = _policy_file(tmp_path, {"1,2,32,0,1,32,3": "reveal", "1,2,0,0,0,0,10": "publish"})
    s = SelfishStrategy("learned", start_height=0, window_objects=32, window_rule="20261020",
                        give_up_objects=5, policy_file=pf)
    s.fork = 100
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (3, 3, 4, 32, 0, 3, 4, 1))   # weight 3 <= 4
    assert d.release_to is None and s.suppressed_reveals == 1
    s.fork = 100
    d = s.update(pub_height=100, priv_height=101, branch_weights=lambda f, p, q: (3, 3, 10, 0, 0, 3, 11, 1))  # h == 0, honest pending heavy
    assert d.release_to == 100 and d.release_from == 100


def test_learned_clips_out_of_range_observations(tmp_path):
    pf = _policy_file(tmp_path, {"1,128,0,0,1,0,48": "give_up"})
    s = SelfishStrategy("learned", start_height=0, window_objects=32, window_rule="20261020",
                        give_up_objects=5, policy_file=pf)
    s.fork = 100
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (300, 300, 1, 0, 0, 300, 100, 1))
    assert d.adopt_public is True and s.clipped_decisions == 1
