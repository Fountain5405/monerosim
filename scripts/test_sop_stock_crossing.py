"""Tests for scripts/sop_stock_crossing.py: the stock network's selfish-mining
crossing in the same race model, for the comparison with SoP's."""
from scripts import sop_stock_crossing as SC


def test_evaluate_stock_runs_the_race_model_without_sop():
    r = SC.evaluate(d=2, alpha=0.4, days=2, seed=1)
    assert 0.0 <= r["share"] <= 1.0 and r["d"] == 2 and r["alpha"] == 0.4 and r["seed"] == 1
    assert r["reveals"] >= 0 and 0.0 <= r["att_orphan_rate"] <= 1.0


def test_stock_rule_has_no_window_or_shares():
    cfg = SC.stock_config(0.4, 2, 1, d=2)
    assert cfg.rule == "stock" and cfg.d == 2 and cfg.attacker_embeds is False
