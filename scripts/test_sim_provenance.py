"""run_sim.sh refuses a monerod-sim built from other patches than patches/series.

The check compares the binary's recorded patch sha256s with the series, in
order. Paths do not matter: a patch keeps its identity when it moves.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from scripts.run_sim_helpers import read_patch_series, sim_provenance_mismatch

REPO = Path(__file__).resolve().parent.parent


def _series_shas():
    return [hashlib.sha256((REPO / r["path"]).read_bytes()).hexdigest()
            for r in read_patch_series()]


def _write_binary(tmp_path, shas, paths=None):
    binary = tmp_path / "monerod-sim"
    binary.write_text("#!/bin/sh\n")
    lines = ["binary: monerod-sim (alias: monerod-hf)", "base: v0.18.5.1 (monero.pin)"]
    for i, sha in enumerate(shas):
        lines += [f"patch: {(paths or {}).get(i, f'patches/p{i}.patch')}", f"patch_sha256: {sha}"]
    lines.append("built: 2026-11-01T00:00:00Z")
    (tmp_path / "monerod-sim.provenance").write_text("\n".join(lines) + "\n")
    return binary


def test_matching_provenance_passes_whatever_the_recorded_paths(tmp_path):
    binary = _write_binary(tmp_path, _series_shas(), paths={0: "somewhere/else.patch"})
    assert sim_provenance_mismatch(str(binary)) is None


def test_reordered_patches_are_refused(tmp_path):
    shas = _series_shas()
    shas[0], shas[1] = shas[1], shas[0]
    msg = sim_provenance_mismatch(str(_write_binary(tmp_path, shas)))
    assert msg and "patch 1" in msg


def test_a_changed_patch_is_refused(tmp_path):
    shas = _series_shas()
    shas[-1] = "0" * 64
    msg = sim_provenance_mismatch(str(_write_binary(tmp_path, shas)))
    assert msg and f"patch {len(shas)}" in msg


def test_a_missing_or_extra_patch_is_refused(tmp_path):
    shas = _series_shas()
    assert sim_provenance_mismatch(str(_write_binary(tmp_path, shas[:-1])))
    assert sim_provenance_mismatch(str(_write_binary(tmp_path, shas + ["1" * 64])))


def test_no_provenance_file_is_refused(tmp_path):
    binary = tmp_path / "monerod-sim"
    binary.write_text("#!/bin/sh\n")
    msg = sim_provenance_mismatch(str(binary))
    assert msg and "monerod-sim.provenance" in msg


def test_the_alias_reads_the_real_binary_provenance(tmp_path):
    _write_binary(tmp_path, _series_shas())
    alias = tmp_path / "monerod-hf"
    os.symlink("monerod-sim", alias)
    assert sim_provenance_mismatch(str(alias)) is None


def test_cli_exit_codes(tmp_path):
    good = _write_binary(tmp_path, _series_shas())
    cli = [sys.executable, str(REPO / "scripts" / "run_sim_helpers.py"), "sim-provenance-check", "--binary"]
    assert subprocess.run(cli + [str(good)], capture_output=True).returncode == 0
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    bad = _write_binary(bad_dir, ["2" * 64])
    r = subprocess.run(cli + [str(bad)], capture_output=True, text=True)
    assert r.returncode == 1 and "patches/series" in r.stdout + r.stderr
