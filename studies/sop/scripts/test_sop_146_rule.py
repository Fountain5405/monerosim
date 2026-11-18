"""MRL #146's counting rule in the race model and the attacker search (2026-11-18).

A reveal under #146's text counts the attacker's own pending tip shares, but
it publishes only the k it needs; those are public on the new tip, so only
pa - k carry into the next race (pow-countermeasure-mdp 08fb4b4 fixed the
same double counting in the MDP). Preset 20261020 keeps the old carry so
earlier results reproduce; 20261020_146 has the fix.
"""
from studies.sop.scripts.sop_attacker_search import DEFAULT_RULE, counting_stubborn, evaluate, run_key
from studies.sop.scripts.sop_race_model import HOLD, REVEAL, RULE_PRESETS, SimConfig, SopEnv
from studies.sop.scripts.sop_rl import race_env


def env_with(preset, att_blocks, hon_blocks, att_pending, hon_pending):
    cfg = SimConfig(alpha=0.45, d=1, rule="sop", attacker_embeds=True, days=1, seed=1, **RULE_PRESETS[preset])
    env = SopEnv(cfg)
    env.att_blocks, env.hon_blocks = list(att_blocks), list(hon_blocks)
    env.att_w = sum(1 + n for n in att_blocks)
    env.hon_w = sum(1 + m for m in hon_blocks)
    env.att_x = sum(1 + n for n in att_blocks[1:])
    env.hon_x = sum(1 + m for m in hon_blocks[1:])
    env.att_pending, env.hon_pending = att_pending, hon_pending
    env._acc = None
    return env


def test_reveal_publishes_only_the_shares_it_needs():
    # objects 48 each, past the window (32 past the first block); pending 10 against 5:
    # 48 + 10 > 48 + 5 needs k = 6 of the 10, so 4 carry
    env = env_with("20261020_146", [15, 15, 15], [15, 15, 15], 10, 5)
    assert env.accepted()
    env._reveal()
    assert env.att_pending == 4


def test_old_preset_keeps_the_old_carry():
    env = env_with("20261020", [15, 15, 15], [15, 15, 15], 10, 5)
    assert env.accepted()
    env._reveal()
    assert env.att_pending == 10


def test_a_lead_in_blocks_needs_fewer_or_no_shares():
    env = env_with("20261020_146", [20, 15, 15], [15, 15, 15], 7, 5)    # 53 against 53: k = 1
    env._reveal()
    assert env.att_pending == 6
    env = env_with("20261020_146", [25, 15, 15], [15, 15, 15], 7, 5)    # 58 against 53: k = 0
    env._reveal()
    assert env.att_pending == 7


def test_counting_stubborn_reveals_on_its_own_pending_shares():
    obs = (3, 0, 32, 10, 3, 32, 5)          # a, D, xa, pa, h, xh, ph: D - ph < 1 <= D + pa - ph
    assert counting_stubborn(obs, W=32) == HOLD
    assert counting_stubborn(obs, W=32, O=1) == REVEAL
    assert counting_stubborn((3, 0, 20, 10, 3, 20, 5), W=32, O=1) == HOLD     # before the window


def test_race_env_takes_the_rule():
    assert not race_env(0.45, 1, 1).cfg.count_attacker_pending
    cfg = race_env(0.45, 1, 1, rule="20261020_146").cfg
    assert cfg.count_attacker_pending and cfg.reveal_publishes_needed


def test_run_keys_before_the_rule_option_are_unchanged():
    assert "rule" not in run_key({"G": 5}, 0.45, 1)
    assert '"rule": "20261020_146"' in run_key({"G": 5}, 0.45, 1, rule="20261020_146")
    assert DEFAULT_RULE == "20261020_noown"


def test_a_short_146_rollout():
    r = evaluate({"G": 5, "L": 1, "Z": 1, "O": 1}, 0.45, 2.0, 1, perish=True, rule="20261020_146")
    assert r["rule"] == "20261020_146"
    assert 0.0 < r["share"] < 1.0 and r["reveals"] > 0
