"""scripts/compare_chains.py: block ids per height from two runs' daemon logs.

The chain of a node is read from <run>/daemon_logs/<node>/bitmonero.log* (the
"+++++ BLOCK SUCCESSFULLY ADDED" record, whose id: and HEIGHT lines follow it).
Two runs match for a node when every common height carries the same block id.
"""
import gzip
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "compare_chains.py"
spec = importlib.util.spec_from_file_location("compare_chains", SCRIPT)
compare_chains = importlib.util.module_from_spec(spec)
sys.modules["compare_chains"] = compare_chains  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(compare_chains)

PREFIX = "2000-01-01 00:00:39.700\t[P2P7]\tINFO\tblockchain\tsrc/cryptonote_core/blockchain.cpp:5474\t"


def added(height: int, block_id: str, t: str = "2000-01-01 00:00:39.700") -> str:
    p = PREFIX.replace("2000-01-01 00:00:39.700", t)
    return (
        f"{p}+++++ BLOCK SUCCESSFULLY ADDED\n"
        f"{p}id:\t<{block_id}>\n"
        f"{p}PoW:\t<{'0' * 64}>\n"
        f"{p}HEIGHT {height}, difficulty:\t6663\n"
        f"{p}block reward: 35.08(35.08 + 0.0), coinbase_weight: 84, cumulative weight: 84, 0(0/0)ms\n"
    )


def hid(n: int) -> str:
    return f"{n:064x}"


def write_run(root: Path, name: str, chains: dict, gz: bool = False) -> Path:
    """chains: {node: [(height, id), ...]} in log order."""
    run = root / name
    for node, blocks in chains.items():
        d = run / "daemon_logs" / node
        d.mkdir(parents=True)
        text = "".join(added(h, i) for h, i in blocks)
        if gz:
            with gzip.open(d / "bitmonero.log.gz", "wt") as fh:
                fh.write(text)
        else:
            (d / "bitmonero.log").write_text(text)
    return run


def test_chain_from_log_reads_height_and_id(tmp_path):
    run = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2))]})
    chain = compare_chains.chain_from_log(run / "daemon_logs" / "n1" / "bitmonero.log")
    assert chain == {1: hid(1), 2: hid(2)}


def test_chain_from_log_reads_gzip(tmp_path):
    run = write_run(tmp_path, "a", {"n1": [(5, hid(5))]}, gz=True)
    chain = compare_chains.chain_from_log(run / "daemon_logs" / "n1" / "bitmonero.log.gz")
    assert chain == {5: hid(5)}


def test_last_block_added_at_a_height_wins(tmp_path):
    # A reorg re-adds height 2 with another id; the chain is what the node ended on.
    run = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2)), (2, hid(22))]})
    chain = compare_chains.chain_from_log(run / "daemon_logs" / "n1" / "bitmonero.log")
    assert chain[2] == hid(22)


def test_daemon_nodes_lists_nodes_with_a_log(tmp_path):
    run = write_run(tmp_path, "a", {"n2": [(1, hid(1))], "n1": [(1, hid(1))]})
    (run / "daemon_logs" / "empty").mkdir()
    assert compare_chains.daemon_nodes(run) == ["n1", "n2"]


def test_compare_identical_runs(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2)), (3, hid(3))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1)), (2, hid(2))]})
    (res,) = compare_chains.compare_runs(a, b)
    assert res.node == "n1"
    assert res.common == 2
    assert res.first_divergence is None
    assert (res.top_a, res.top_b) == (3, 2)


def test_compare_reports_first_divergent_height(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2)), (3, hid(3))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1)), (2, hid(22)), (3, hid(33))]})
    (res,) = compare_chains.compare_runs(a, b)
    assert res.first_divergence == 2
    assert res.same_below == 1


def test_compare_only_named_nodes(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1))], "n2": [(1, hid(1))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1))], "n2": [(1, hid(9))]})
    results = compare_chains.compare_runs(a, b, nodes=["n1"])
    assert [r.node for r in results] == ["n1"]


def test_compare_node_missing_in_one_run_is_an_error(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1))], "n2": [(1, hid(1))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1))]})
    results = compare_chains.compare_runs(a, b)
    by_node = {r.node: r for r in results}
    assert by_node["n2"].error
    assert not by_node["n1"].error


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def test_cli_exit_0_when_identical(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1)), (2, hid(2))]})
    p = run_cli(a, b)
    assert p.returncode == 0, p.stderr
    assert "identical over 2 common heights" in p.stdout


def test_cli_exit_1_on_divergence_names_node_and_height(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1)), (2, hid(22))]})
    p = run_cli(a, b)
    assert p.returncode == 1
    assert "n1" in p.stdout and "height 2" in p.stdout


def test_cli_exit_2_when_too_few_common_heights(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1)), (2, hid(2))]})
    p = run_cli(a, b, "--min-common", 10)
    assert p.returncode == 2


def test_cli_exit_2_when_a_node_is_missing(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1))], "n2": [(1, hid(1))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1))]})
    p = run_cli(a, b)
    assert p.returncode == 2


def test_cli_json_output(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [(1, hid(1)), (2, hid(2))]})
    b = write_run(tmp_path, "b", {"n1": [(1, hid(1)), (2, hid(22))]})
    out = tmp_path / "out.json"
    p = run_cli(a, b, "--json", out)
    assert p.returncode == 1
    data = json.loads(out.read_text())
    assert data["verdict"] == "DIVERGED"
    assert data["nodes"][0] == {
        "node": "n1", "top_a": 2, "top_b": 2, "common": 2,
        "first_divergence": 2, "same_below": 1, "error": None,
    }
