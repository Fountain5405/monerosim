# scripts/test_msb_study.py
import json
from pathlib import Path

from scripts.msb_study import study_run, render


def _mk_run(tmp_path, name, winners, strategy="eyal_sirer", victims=()):
    """winners: list of (miner_id,) per canonical height, in order."""
    rd = tmp_path / name
    (rd / "shadow.data" / "hosts").mkdir(parents=True)
    cfg = ["agents:", "  honest-001: {script: agents.autonomous_miner, hashrate: 4}"]
    if victims:
        cfg.append("  attacker-miner: {script: agents.selfish_miner, hashrate: 4,"
                   " attributes: {strategy: %s, islands: attacker-island}}" % strategy)
        cfg.append("  attacker-bridge: {script: agents.selfish_bridge}")
        cfg.append("  attacker-island: {script: agents.selfish_bridge,"
                   " attributes: {eclipsed: 'true'}}")
        for v in victims:
            cfg.append("  %s: {script: agents.autonomous_miner, hashrate: 3,"
                       " attributes: {eclipsed: 'true'}}" % v)
    else:
        cfg.append("  attacker-miner: {script: agents.selfish_miner, hashrate: 4,"
                   " attributes: {strategy: %s}}" % strategy)
        cfg.append("  attacker-bridge: {script: agents.selfish_bridge}")
    (rd / "input_config.yaml").write_text("\n".join(cfg) + "\n")
    chain, t = [], 0
    for i, w in enumerate(winners, start=1):
        h = f"{w[:1]}{i}"
        chain.append({"height": i, "hash": h})
        host = rd / "shadow.data" / "hosts" / w
        host.mkdir(parents=True, exist_ok=True)
        with open(host / f"monerod-sim.{t}.stdout", "a") as f:
            f.write(f"2000-01-01 00:{t:02d}:00.000\tI Found block <{h}> at height {i} for difficulty: 2\n")
        t += 1
    tx = rd / "transaction_registry"
    tx.mkdir()
    (tx / "canonical_chain_attacker-bridge.json").write_text(
        json.dumps({"observer": "attacker-bridge", "chain": chain}))
    if victims:
        (tx / "canonical_chain_attacker-island.json").write_text(
            json.dumps({"observer": "attacker-island",
                        "chain": [{"height": 1, "hash": "deadbeef"}]}))
    return rd


def test_study_run_roles_and_island_exclusion(tmp_path):
    winners = ["attacker-miner"] * 4 + ["honest-001"] * 2 + \
              ["attacker-miner"] * 4 + ["victim-001"] * 2
    rd = _mk_run(tmp_path, "r1", winners, victims=("victim-001",))
    r = study_run(rd)
    assert r["strategy"] == "eyal_sirer" and r["attack"] is True
    assert abs(r["alpha_eff"] - 7 / 11) < 0.01
    roles = {row["miner"]: row["role"] for row in r["rows"]}
    assert roles["attacker-miner"] == "attacker"
    assert roles["victim-001"] == "victim"
    assert roles["honest-001"] == "honest"
    assert r["chain_len"] == 12                    # island chain excluded, not 1
    assert abs(r["attacker_share"] - 8 / 12) < 1e-9
    assert abs(r["controlled_share"] - 10 / 12) < 1e-9


def test_render_counts_flags_by_role(tmp_path):
    winners = ["attacker-miner"] * 6 + ["honest-001"] * 6
    rd = _mk_run(tmp_path, "r2", winners)
    out = render([study_run(rd)])
    assert "Flag rates by role" in out
    assert "attacker:" in out and "honest:" in out
