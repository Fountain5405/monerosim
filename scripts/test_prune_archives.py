"""prune_archives.sh must never prune a run whose owner pid is alive."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prune_archives.sh"


def _archive(tmp_path, *, owner):
    a = tmp_path / "20260904_120000_p"
    (a / "shadow.data" / "hosts" / "user-007").mkdir(parents=True)
    (a / "daemon_logs" / "monero-user-007").mkdir(parents=True)
    (a / "summary.txt").write_text("Exit code: 0\n")
    (a / ".owner_pid").write_text(str(owner))
    return a


def _run(args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT)


def test_live_run_is_refused(tmp_path):
    a = _archive(tmp_path, owner=os.getpid())
    r = _run(["--dry-run", str(a)])
    assert "LIVE" in r.stderr and "WOULD DELETE" not in r.stdout


def test_live_run_pruned_with_force(tmp_path):
    a = _archive(tmp_path, owner=os.getpid())
    r = _run(["--dry-run", "--force", str(a)])
    assert "WOULD DELETE" in r.stdout


def test_dead_owner_is_pruned_normally(tmp_path):
    a = _archive(tmp_path, owner=2**31 - 1)
    r = _run(["--dry-run", str(a)])
    assert "WOULD DELETE" in r.stdout and "LIVE" not in r.stderr


# Eclipse runs: every node's peer-list dump is the measurement, and the configs
# carry no simulation-monitor, so there is never a summary.txt. Prune must
# compress them instead of deleting, without asking for --force.

def _eclipse_archive(tmp_path, *, owner, dumps=True):
    a = tmp_path / "20261004_120000_eclipse"
    for n in ("monero-miner-001", "monero-relay-2001", "monero-relay-2002"):
        d = a / "daemon_logs" / n
        d.mkdir(parents=True)
        (d / "bitmonero.log").write_text("log line\n" * 1000)
        if dumps:
            (d / "peerlist_dump.jsonl").write_text('{"t": 1, "white": []}\n' * 100)
    (a / "shadow.data" / "hosts" / "relay-2001").mkdir(parents=True)
    (a / ".owner_pid").write_text(str(owner))
    return a


def test_eclipse_run_is_compressed_not_deleted(tmp_path):
    a = _eclipse_archive(tmp_path, owner=2**31 - 1)
    r = _run([str(a)])
    assert r.returncode == 0, r.stderr
    assert "no summary.txt" not in r.stderr
    for n in ("monero-miner-001", "monero-relay-2001", "monero-relay-2002"):
        d = a / "daemon_logs" / n
        assert (d / "bitmonero.log.gz").exists() and (d / "peerlist_dump.jsonl.gz").exists()
        assert not (d / "bitmonero.log").exists() and not (d / "peerlist_dump.jsonl").exists()
    assert (a / "shadow.data" / "hosts" / "relay-2001").is_dir()


def test_eclipse_dry_run_deletes_and_compresses_nothing(tmp_path):
    a = _eclipse_archive(tmp_path, owner=2**31 - 1)
    r = _run(["--dry-run", str(a)])
    assert "WOULD COMPRESS 6 files" in r.stdout and "WOULD DELETE" not in r.stdout
    assert (a / "daemon_logs" / "monero-relay-2001" / "bitmonero.log").exists()


def test_eclipse_run_detected_from_its_agents(tmp_path):
    a = _eclipse_archive(tmp_path, owner=2**31 - 1, dumps=False)
    (a / "shadow_agents.yaml").write_text("args: -m agents.eclipse_fakepeer --id relay-2001\n")
    r = _run(["--dry-run", str(a)])
    assert "WOULD COMPRESS 3 files" in r.stdout and "WOULD DELETE" not in r.stdout


def test_live_eclipse_run_is_refused(tmp_path):
    a = _eclipse_archive(tmp_path, owner=os.getpid())
    r = _run([str(a)])
    assert "LIVE" in r.stderr
    assert (a / "daemon_logs" / "monero-relay-2001" / "bitmonero.log").exists()


def test_other_runs_without_summary_still_need_force(tmp_path):
    a = _archive(tmp_path, owner=2**31 - 1)
    (a / "summary.txt").unlink()
    r = _run(["--dry-run", str(a)])
    assert "no summary.txt" in r.stderr and "WOULD DELETE" not in r.stdout
