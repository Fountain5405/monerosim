"""Run-directory path resolution for analyze_success_criteria.py."""
from pathlib import Path

from scripts.analyze_success_criteria import resolve_run_paths


def _run(tmp_path):
    run = tmp_path / "20260904_120000_a"
    (run / "shadow.data" / "hosts").mkdir(parents=True)
    return run


def test_archived_daemon_logs_preferred(tmp_path):
    run = _run(tmp_path)
    (run / "daemon_logs").mkdir()
    log_dir, shadow, out = resolve_run_paths(run)
    assert (log_dir, shadow, out) == (run / "daemon_logs", run / "shadow.data", run / "analysis_output")


def test_live_namespace_from_run_env(tmp_path):
    run = _run(tmp_path)
    live = tmp_path / "ns"
    (live / "monero-miner-001").mkdir(parents=True)
    (live / "monero-miner-001" / "bitmonero.log").write_text("x")
    (run / "shadow_output").mkdir()
    (run / "shadow_output" / "run_env.sh").write_text(f'MONEROSIM_DAEMON_DATA_DIR="{live}"\n')
    assert resolve_run_paths(run)[0] == live


def test_falls_back_to_hosts_dir(tmp_path):
    run = _run(tmp_path)
    assert resolve_run_paths(run)[0] == run / "shadow.data" / "hosts"
