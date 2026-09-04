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
    a = _archive(tmp_path, owner=2**22 - 1)
    r = _run(["--dry-run", str(a)])
    assert "WOULD DELETE" in r.stdout and "LIVE" not in r.stderr
