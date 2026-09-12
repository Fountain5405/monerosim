import pytest
from scripts.selfish_mining_analysis import (
    es_revenue_share,
    found_by_hash,
    attacker_share_from_chain,
    orphan_stats,
    parse_found_blocks,
)


def test_es_revenue_share_small_alpha_near_zero():
    assert abs(es_revenue_share(1e-6, 0.0)) < 1e-4


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
    assert found == [{"hash": "deadbeef", "height": 1, "miner": "attacker-miner"}]


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
