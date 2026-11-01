"""patches/series is the one ordered list of monerod-sim patches.

setup.sh, update.sh, setup.sh --help and run_sim.sh's capability gate all
read it; these tests keep them from growing their own lists again.
"""
import re
import subprocess
from pathlib import Path

from scripts.run_sim_helpers import SIM_FLAG_OPTIONS, read_patch_series

REPO = Path(__file__).resolve().parent.parent


def _added_lines(patch: Path) -> str:
    return "\n".join(l for l in patch.read_text().splitlines() if l.startswith("+"))


def test_series_names_existing_patches_once_each():
    rows = read_patch_series()
    assert rows, "patches/series lists no patches"
    paths = [r["path"] for r in rows]
    assert len(paths) == len(set(paths))
    for p in paths:
        assert (REPO / p).is_file(), p


def test_owner_is_core_or_an_existing_study():
    for r in read_patch_series():
        assert r["owner"] == "core" or (REPO / "studies" / r["owner"]).is_dir(), r


def test_every_listed_flag_is_defined_by_its_patch():
    for r in read_patch_series():
        added = _added_lines(REPO / r["path"])
        for flag in r["flags"]:
            assert f'"{flag[2:]}"' in added, f'{r["path"]} does not define {flag}'


def test_capability_gate_takes_its_flags_from_the_series():
    for r in read_patch_series():
        for flag in r["flags"]:
            assert SIM_FLAG_OPTIONS.get(flag[2:]) == flag[2:]


def test_capability_gate_keeps_the_flags_it_gated_before_the_series():
    before = {"fakechain-hard-forks", "peerlist-dump-file", "sim-relay-alt-blocks",
              "sim-publish-or-perish", "sim-pop-k", "sim-pop-delay-s", "sim-pop-det-tie",
              "sim-pop-uncles", "sim-pop-uncles-header", "sim-sop-w",
              "sim-share-or-perish", "sim-sop-delay-s", "sim-sop-k"}
    assert before <= set(SIM_FLAG_OPTIONS)


def test_shell_reader_returns_the_same_order():
    out = subprocess.run(
        ["bash", "-c", 'source scripts/patch_series.sh && patch_series_paths "$PWD"'],
        cwd=REPO, capture_output=True, text=True, check=True).stdout
    assert out.split() == [str(REPO / r["path"]) for r in read_patch_series()]


def test_setup_and_update_keep_no_patch_list_of_their_own():
    for script in ("setup.sh", "update.sh"):
        text = (REPO / script).read_text()
        assert not re.search(r"patches/monero-[a-z0-9-]+\.patch", text), script


def test_setup_help_prints_the_series():
    out = subprocess.run(["bash", "setup.sh", "--help"], cwd=REPO,
                         capture_output=True, text=True, timeout=30).stdout
    for r in read_patch_series():
        assert Path(r["path"]).name in out
    assert "vote bypass" not in out
