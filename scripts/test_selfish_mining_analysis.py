import pytest
from scripts.selfish_mining_analysis import (
    es_revenue_share,
    mod_revenue_share,
    found_by_hash,
    attacker_share_from_chain,
    orphan_stats,
    parse_found_blocks,
)


def test_es_revenue_share_small_alpha_near_zero():
    assert abs(es_revenue_share(1e-6, 0.0)) < 1e-4


def test_mod_revenue_share_matches_lee_kim_2025_numbers():
    # Paper values (Eq. 2): mod(0.2802, 0) = 0.1782 ("17.82%"), the modified
    # model's revenue at Qubic's attack-period alpha; and mod(0.4, 0) = 0.364.
    assert abs(mod_revenue_share(0.2802, 0.0) - 0.1782) < 0.001
    assert abs(mod_revenue_share(0.4, 0.0) - 0.364) < 0.001


def test_mod_revenue_share_below_eyal_sirer_and_honest_at_gamma_zero():
    # The conservative lead-2 policy wastes less honest work than waiting for
    # the catch-to-one, so at gamma=0 it sits under the ES curve; and both
    # curves sit under honest at the sub-threshold alpha Qubic actually had.
    for alpha in (0.25, 0.3, 0.4, 0.45):
        assert mod_revenue_share(alpha, 0.0) < es_revenue_share(alpha, 0.0)


def test_release_lead_detected_from_config(tmp_path):
    from scripts.selfish_mining_analysis import _release_lead_from_config
    import yaml
    p = tmp_path / "input_config.yaml"
    p.write_text(
        "agents:\n"
        "  honest-001: {script: agents.autonomous_miner, hashrate: 6}\n"
        "  attacker-miner:\n"
        "    script: agents.selfish_miner\n"
        "    hashrate: 4\n"
        "    attributes: {release_lead: '2'}\n"
    )
    with open(p) as f:
        cfg = yaml.safe_load(f)
    assert _release_lead_from_config(cfg) == 2
    cfg["agents"]["attacker-miner"]["attributes"].pop("release_lead")
    assert _release_lead_from_config(cfg) == 1


def test_make_verdicts_conservative_uses_band_not_eyal_sirer_point():
    from scripts.selfish_mining_analysis import make_verdicts
    alpha, share = 0.4, 0.42
    verdicts = make_verdicts(alpha, share, {}, theory_at_gamma=None, release_lead=2)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert "band" in v and v["pass"] is True           # 0.42 within 0.364-0.10 .. 0.484+0.10
    # default release_lead keeps the point verdicts (and beats-honest at alpha>0.34)
    defaults = make_verdicts(alpha, share, {}, theory_at_gamma=0.484, release_lead=1)
    assert len(defaults) == 3


def test_es_revenue_share_crosses_alpha_near_one_third_at_gamma_zero():
    assert es_revenue_share(0.30, 0.0) < 0.30
    assert es_revenue_share(0.40, 0.0) > 0.40


def test_es_revenue_share_monotonic_in_gamma():
    assert es_revenue_share(0.35, 1.0) > es_revenue_share(0.35, 0.0)


def test_found_by_hash_maps_hash_to_finder():
    found = [
        {"hash": "a1", "height": 1, "miner": "attacker-miner"},
        {"hash": "h2", "height": 2, "miner": "honest-001"},
    ]
    assert found_by_hash(found) == {"a1": "attacker-miner", "h2": "honest-001"}


def test_attacker_share_from_canonical_chain():
    chain = [
        {"height": 1, "hash": "h1"},
        {"height": 2, "hash": "a2"},
        {"height": 3, "hash": "a3"},
        {"height": 4, "hash": "h4"},
    ]
    h2m = {"h1": "honest-001", "a2": "attacker-miner", "a3": "attacker-miner", "h4": "honest-002"}
    assert attacker_share_from_chain(chain, h2m, {"attacker-miner"}) == 0.5


def test_orphan_stats_counts_lost_ties_as_orphans():
    # attacker found a1 (canonical) and a2x (orphaned tie loss); honest h2 canonical
    found = [
        {"hash": "a1", "height": 1, "miner": "attacker-miner"},
        {"hash": "a2x", "height": 2, "miner": "attacker-miner"},
        {"hash": "h2", "height": 2, "miner": "honest-001"},
    ]
    canonical_hashes = {"a1", "h2"}
    stats = orphan_stats(found, canonical_hashes, {"attacker-miner"})
    assert stats["attacker_found"] == 2
    assert stats["attacker_canonical"] == 1
    assert abs(stats["attacker_orphan_rate"] - 0.5) < 1e-9


def test_parse_found_blocks_reads_a_log(tmp_path):
    host = tmp_path / "shadow.data" / "hosts" / "attacker-miner"
    host.mkdir(parents=True)
    (host / "monerod.stdout").write_text(
        "2000-01-01 00:00:15.0\tI Found block <deadbeef> at height 1 for difficulty: 2\n"
    )
    found = parse_found_blocks(tmp_path, ["attacker-miner"])
    assert found == [{"hash": "deadbeef", "height": 1, "miner": "attacker-miner",
                      "time": "2000-01-01 00:00:15.0"}]


def test_config_loader_sees_agents(tmp_path):
    # Review C2: the analysis must read the RAW config (which has `agents`), so
    # attacker/honest sets and alpha are non-trivial.
    from scripts.selfish_mining_analysis import load_raw_config, _attacker_ids, _alpha_from_config
    cfg_path = tmp_path / "input_config.yaml"
    cfg_path.write_text(
        "agents:\n"
        "  honest-001: {script: agents.autonomous_miner, hashrate: 6}\n"
        "  attacker-miner: {script: agents.selfish_miner, hashrate: 4}\n"
    )
    cfg = load_raw_config(cfg_path)
    assert _attacker_ids(cfg) == {"attacker-miner"}
    assert abs(_alpha_from_config(cfg) - 0.4) < 1e-9


def test_realized_gamma_counts_tie_wins():
    from scripts.selfish_mining_analysis import realized_gamma
    found = [{"hash":"a2","height":2,"miner":"attacker-miner"},{"hash":"h2","height":2,"miner":"honest-001"},
             {"hash":"a3","height":3,"miner":"attacker-miner"},{"hash":"h3","height":3,"miner":"honest-002"},
             {"hash":"h4","height":4,"miner":"honest-001"}]
    chain = [{"height":2,"hash":"a2"},{"height":3,"hash":"h3"},{"height":4,"hash":"h4"}]
    g, ties = realized_gamma(found, chain, {"attacker-miner"})
    assert ties == 2 and abs(g - 0.5) < 1e-9

def test_realized_gamma_zero_when_no_ties():
    from scripts.selfish_mining_analysis import realized_gamma
    g, ties = realized_gamma([{"hash":"a1","height":1,"miner":"attacker-miner"}],
                             [{"height":1,"hash":"a1"}], {"attacker-miner"})
    assert ties == 0 and g == 0.0


def test_realized_gamma_excludes_reorg_wins():
    # Review C1: a fork the attacker's OWN chain extended (attacker-found
    # canonical F+1) is a reorg win, NOT a gamma tie-break — must be excluded.
    from scripts.selfish_mining_analysis import realized_gamma
    found = [{"hash": "a2", "height": 2, "miner": "attacker-miner"},
             {"hash": "h2", "height": 2, "miner": "honest-001"},
             {"hash": "a3", "height": 3, "miner": "attacker-miner"}]
    chain = [{"height": 2, "hash": "a2"}, {"height": 3, "hash": "a3"}]
    g, events = realized_gamma(found, chain, {"attacker-miner"})
    assert events == 0 and g == 0.0


def test_realized_gamma_lost_tie_is_zero():
    # Honest built F+1 on honest's F -> attacker lost the tie -> gamma 0.
    from scripts.selfish_mining_analysis import realized_gamma
    found = [{"hash": "a2", "height": 2, "miner": "attacker-miner"},
             {"hash": "h2", "height": 2, "miner": "honest-001"},
             {"hash": "h3", "height": 3, "miner": "honest-002"}]
    chain = [{"height": 2, "hash": "h2"}, {"height": 3, "hash": "h3"}]
    g, events = realized_gamma(found, chain, {"attacker-miner"})
    assert events == 1 and g == 0.0


def test_realized_gamma_won_tie_counts():
    # Honest built F+1 on the ATTACKER's F -> gamma win.
    from scripts.selfish_mining_analysis import realized_gamma
    found = [{"hash": "a2", "height": 2, "miner": "attacker-miner"},
             {"hash": "h2", "height": 2, "miner": "honest-001"},
             {"hash": "h3", "height": 3, "miner": "honest-002"}]
    chain = [{"height": 2, "hash": "a2"}, {"height": 3, "hash": "h3"}]
    g, events = realized_gamma(found, chain, {"attacker-miner"})
    assert events == 1 and g == 1.0


def test_eclipse_config_helpers():
    from scripts.selfish_mining_analysis import (
        _island_ids_from_config, _eclipsed_miner_ids, _alpha_eff_from_config,
    )
    cfg = {
        "agents": {
            "honest-001": {"script": "agents.autonomous_miner", "hashrate": 6},
            "victim-001": {"script": "agents.autonomous_miner", "hashrate": 3,
                           "attributes": {"eclipsed": "true"}},
            "attacker-miner": {"script": "agents.selfish_miner", "hashrate": 4,
                               "attributes": {"islands": "attacker-island, "}},
            "attacker-bridge": {"script": "agents.selfish_bridge"},
            "attacker-island": {"script": "agents.selfish_bridge",
                                "attributes": {"eclipsed": "true"}},
        }
    }
    assert _island_ids_from_config(cfg) == {"attacker-island"}
    assert _eclipsed_miner_ids(cfg) == {"victim-001"}
    assert abs(_alpha_eff_from_config(cfg) - 7 / 13) < 1e-9    # (4+3)/(4+3+6)


def test_eclipse_verdict_uses_controlled_share_vs_alpha_eff():
    from scripts.selfish_mining_analysis import make_verdicts, es_revenue_share
    # Sub-majority composition: alpha=4/15, alpha_eff=(4+3)/15=0.467,
    # ES(0.467, gamma=0) ~ 0.73 — controlled 0.75 sits on the curve.
    alpha, controlled, alpha_eff = 4 / 15, 0.75, 7 / 15
    verdicts = make_verdicts(alpha, 0.30, {}, theory_at_gamma=None,
                             eclipse=(controlled, alpha_eff))
    assert len(verdicts) == 1
    v = verdicts[0]
    assert abs(v["theory"] - es_revenue_share(alpha_eff, 0.0)) < 1e-12
    assert v["pass"] is True
    # Majority composition degrades to a control check, not the (undefined)
    # ES curve: alpha_eff=7/13 must not evaluate es_revenue_share.
    maj = make_verdicts(alpha, 0.30, {}, theory_at_gamma=None,
                        eclipse=(0.6, 7 / 13))
    assert len(maj) == 1 and maj[0]["pass"] is True and maj[0]["theory"] == 0.5


def test_chain_file_search_skips_island_observers(tmp_path):
    from scripts.selfish_mining_analysis import _find_chain_file
    (tmp_path / "canonical_chain_attacker-island.json").write_text(
        '{"observer": "attacker-island", "chain": [{"height": 1, "hash": "priv"}]}')
    (tmp_path / "canonical_chain_attacker-bridge.json").write_text(
        '{"observer": "attacker-bridge", "chain": [{"height": 1, "hash": "hon"}]}')
    picked = _find_chain_file(tmp_path, None, islands={"attacker-island"})
    assert picked.name == "canonical_chain_attacker-bridge.json"
    # without islands the deterministic sorted-first pick is unchanged
    first = _find_chain_file(tmp_path, None)
    assert first.name == "canonical_chain_attacker-bridge.json"
