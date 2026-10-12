"""compress_archives.sh gzips finished runs' daemon logs in place and never touches a live run."""
import gzip
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "compress_archives.sh"
DEAD = 2**31 - 1  # a pid that cannot exist


def _run_dir(base, name, *, owner, nodes=("monero-miner-001", "monero-relay-001"), dump=False):
    a = base / name
    for n in nodes:
        d = a / "daemon_logs" / n
        d.mkdir(parents=True)
        (d / "bitmonero.log").write_text(f"{n} log line\n" * 1000)
        if dump:
            (d / "peerlist_dump.jsonl").write_text('{"t": 1, "white": []}\n' * 100)
    (a / ".owner_pid").write_text(str(owner))
    return a


def _run(args, base=None):
    env = dict(os.environ)
    if base is not None:
        env["MONEROSIM_ARCHIVE_BASE"] = str(base)
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, env=env)


def _log(a, node="monero-relay-001"):
    return a / "daemon_logs" / node / "bitmonero.log"


def test_finished_run_is_compressed_in_place(tmp_path):
    a = _run_dir(tmp_path, "20261004_120000_done", owner=DEAD)
    r = _run([str(a)])
    assert r.returncode == 0, r.stderr
    for node in ("monero-miner-001", "monero-relay-001"):
        gz = Path(str(_log(a, node)) + ".gz")
        assert not _log(a, node).exists()
        assert gzip.open(gz, "rt").read() == f"{node} log line\n" * 1000


def test_live_run_is_untouched(tmp_path):
    a = _run_dir(tmp_path, "20261004_120000_live", owner=os.getpid())
    r = _run([str(a)])
    assert "LIVE" in r.stderr
    assert _log(a).exists() and not Path(str(_log(a)) + ".gz").exists()


def test_dry_run_changes_nothing(tmp_path):
    a = _run_dir(tmp_path, "20261004_120000_done", owner=DEAD)
    r = _run(["--dry-run", str(a)])
    assert r.returncode == 0, r.stderr
    assert "WOULD COMPRESS 2 files" in r.stdout
    assert _log(a).exists() and not Path(str(_log(a)) + ".gz").exists()


def test_no_args_covers_every_run_under_the_archive_base(tmp_path):
    done = _run_dir(tmp_path, "20261004_120000_done", owner=DEAD)
    live = _run_dir(tmp_path, "20261004_130000_live", owner=os.getpid())
    r = _run([], base=tmp_path)
    assert r.returncode == 0, r.stderr
    assert not _log(done).exists() and Path(str(_log(done)) + ".gz").exists()
    assert _log(live).exists()


def test_peerlist_dumps_only_with_flag(tmp_path):
    a = _run_dir(tmp_path, "20261004_120000_ecl", owner=DEAD, dump=True)
    dump = a / "daemon_logs" / "monero-relay-001" / "peerlist_dump.jsonl"
    _run([str(a)])
    assert dump.exists()
    r = _run(["--peerlist-dumps", str(a)])
    assert r.returncode == 0, r.stderr
    assert not dump.exists() and Path(str(dump) + ".gz").exists()


def test_rotated_logs_compressed_existing_gz_kept_and_rerun_is_noop(tmp_path):
    a = _run_dir(tmp_path, "20261004_120000_done", owner=DEAD)
    d = a / "daemon_logs" / "monero-relay-001"
    (d / "bitmonero.log-2026-10-04-01-00-00").write_text("rotated\n" * 100)
    (d / "bitmonero.log-2026-10-03-01-00-00.gz").write_bytes(gzip.compress(b"older\n"))
    assert _run([str(a)]).returncode == 0
    assert (d / "bitmonero.log-2026-10-04-01-00-00.gz").exists()
    assert gzip.open(d / "bitmonero.log-2026-10-03-01-00-00.gz", "rt").read() == "older\n"
    assert not (d / "bitmonero.log-2026-10-03-01-00-00.gz.gz").exists()
    r = _run([str(a)])
    assert r.returncode == 0, r.stderr
    assert "nothing to compress" in r.stdout


def test_monerod_stdout_compressed_agent_stdout_kept(tmp_path):
    """Under Shadow monerod's console log lands in shadow.data/hosts/<host>/
    monerod.<pid>.stdout, a second copy of bitmonero.log. Agents' stdout is
    their only log and stays plain."""
    a = _run_dir(tmp_path, "20261004_120000_done", owner=DEAD)
    hosts = a / "shadow.data" / "hosts"
    for host, name in (("relay-001", "monerod.1000.stdout"),
                       ("miner-001", "monerod-sim.1000.stdout"),
                       ("miner-001", "bash.1001.stdout"),
                       ("eclipse-monitor", "python3.1000.stdout")):
        (hosts / host).mkdir(parents=True, exist_ok=True)
        (hosts / host / name).write_text(f"{host} {name}\n" * 500)
    r = _run([str(a)])
    assert r.returncode == 0, r.stderr
    assert gzip.open(hosts / "relay-001" / "monerod.1000.stdout.gz", "rt").read() == \
        "relay-001 monerod.1000.stdout\n" * 500
    assert (hosts / "miner-001" / "monerod-sim.1000.stdout.gz").exists()
    assert (hosts / "miner-001" / "bash.1001.stdout").exists()
    assert (hosts / "eclipse-monitor" / "python3.1000.stdout").exists()
