"""check_sim.sh resolves a run directory and reads that run's data only."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fixture_run(tmp_path, *, live=True):
    run = tmp_path / "archived_runs" / "20260904_120000_fx"
    host = run / "shadow.data" / "hosts" / "miner-001"
    host.mkdir(parents=True)
    (host / "bash.1000.stdout").write_text(
        "2000-01-01 00:10:00 AutonomousMiner starting\n2000-01-01 01:00:00 New height: 5\n"
    )
    (run / "input_config.yaml").write_text("general:\n  stop_time: 6h\nagents:\n  miner-001: {}\n")
    live_ns = tmp_path / "ns"
    (live_ns / "monero-miner-001").mkdir(parents=True)
    (live_ns / "monero-miner-001" / "bitmonero.log").write_text("2000-01-01 01:00:00 I Synced 5/5\n")
    (run / "shadow_output").mkdir()
    (run / "shadow_output" / "run_env.sh").write_text(
        f'MONEROSIM_RUN_ID="20260904_120000_fx"\nMONEROSIM_RUN_DIR="{run}"\n'
        f'MONEROSIM_SHADOW_DATA_DIR="{run}/shadow.data"\nMONEROSIM_DAEMON_DATA_DIR="{live_ns}"\n'
    )
    (run / ".owner_pid").write_text(str(os.getpid() if live else 2**22 - 1))
    return run


def _check(args, env=None):
    e = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/"), "VIRTUAL_ENV": "x"}
    e.update(env or {})
    return subprocess.run(["bash", str(ROOT / "scripts" / "check_sim.sh"), *args],
                          capture_output=True, text=True, env=e, cwd=ROOT)


def test_explicit_run_dir_live(tmp_path):
    run = _fixture_run(tmp_path)
    r = _check([str(run)])
    assert r.returncode == 0, r.stderr
    assert f"run: {run} (live)" in r.stderr
    assert "miner-001: height 5" in r.stdout
    assert "Sim time: 2000-01-01 01:00:00" in r.stdout


def test_shadow_data_path_maps_to_run_dir(tmp_path):
    run = _fixture_run(tmp_path, live=False)
    r = _check([str(run / "shadow.data")])
    assert r.returncode == 0, r.stderr
    assert f"run: {run} (incomplete)" in r.stderr


def test_newest_run_under_archive_base(tmp_path):
    run = _fixture_run(tmp_path, live=False)
    r = _check([], env={"MONEROSIM_ARCHIVE_BASE": str(tmp_path / "archived_runs")})
    assert r.returncode == 0, r.stderr
    assert f"run: {run} (incomplete)" in r.stderr


def test_no_run_is_an_error(tmp_path):
    r = _check([], env={"MONEROSIM_ARCHIVE_BASE": str(tmp_path / "none")})
    assert r.returncode != 0 and "no run directory" in r.stderr
