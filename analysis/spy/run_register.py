#!/usr/bin/env python3
"""Run register for the spy-node experiments (docs/SPY_EXPERIMENT_JOURNAL.md).

An archived run is ~12 GB, sits on whichever box ran it, and gets pruned. `add` keeps what defines and
scores it, a few tens of KB, under docs/spy_journal/runs/<run_id>/:

  input_config.yaml      the exact cell that ran
  binary_provenance.txt  monerod-sim hash and the patches it was built from
  summary_head.txt       the head of the run summary (wall time, exit code, transactions)
  x0_calibration.{txt,json}   the scorer's report (computed from the archive if the run predates it)
  spy_estimators.{txt,json}   with --estimators, the origin-estimator report
  meta.json              box, wall time, exit code, minimum free RAM, and the headline numbers

`table` rebuilds the register table between the markers in the journal from those meta.json files.

Usage:
    run_register.py add <archive_dir> --box phantom [--note "..."] [--estimators report.txt[,report.json]]
    run_register.py annotate <run_id> "text"     (appends a dated note; never replaces the old one)
    run_register.py table
"""
import argparse
import csv
import datetime
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "docs" / "SPY_EXPERIMENT_JOURNAL.md"
RUNS = REPO / "docs" / "spy_journal" / "runs"
START, END = "<!-- register:start -->", "<!-- register:end -->"
COPY = ["input_config.yaml", "binary_provenance.txt", "x0_calibration.txt", "x0_calibration.json"]


def first(pattern, text, cast=str, default=None):
    m = re.search(pattern, text, re.M)
    return cast(m.group(1)) if m else default


def scoring(run_dir):
    """The x0_calibration.py report for a run, from the archive's own copy or computed (not written back)."""
    saved = Path(run_dir, "x0_calibration.json")
    if saved.exists():
        return json.loads(saved.read_text())[0]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp, "r.json")
        r = subprocess.run([sys.executable, "-I", str(REPO / "analysis/spy/x0_calibration.py"), str(run_dir),
                            "--json", str(out)], capture_output=True, text=True)
        return json.loads(out.read_text())[0] if r.returncode == 0 and out.exists() else None


def min_avail_mb(run_dir):
    f = Path(run_dir, "memory_samples.csv")
    if not f.exists():
        return None
    with open(f) as fh:
        vals = [int(r["avail_mb"]) for r in csv.DictReader(fh) if r.get("avail_mb")]
    return min(vals) if vals else None


def add(run_dir, box, note, estimators):
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    dest = RUNS / run_id
    dest.mkdir(parents=True, exist_ok=True)
    for name in COPY:
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, dest / name)
    summary = (run_dir / "summary.txt").read_text() if (run_dir / "summary.txt").exists() else ""
    (dest / "summary_head.txt").write_text("".join(summary.splitlines(True)[:45]))
    for f in estimators:
        shutil.copy2(f, dest / ("spy_estimators" + Path(f).suffix))
    prov = (run_dir / "binary_provenance.txt").read_text() if (run_dir / "binary_provenance.txt").exists() else ""
    rep = scoring(run_dir)
    meta = {
        "run_id": run_id,
        "box": box,
        "cell": re.sub(r"^\d{8}_\d{6}_", "", run_id),
        "archived_at": first(r"^archived_at: (\S+)", prov),
        "monerod_sim_sha": first(r"^monerod-sim: sha256=([0-9a-f]{12})", prov),
        "wall": first(r"^Wall time:\s+(.+)$", summary),
        "exit_code": first(r"^Exit code:\s+(\d+)", summary, int),
        "min_avail_mb": min_avail_mb(run_dir),
        "txs_created": first(r"^\s*Created:\s+(\d+)", summary, int),
        "txs_in_blocks": first(r"^\s*In blocks:\s+(\d+)", summary, int),
        "note": note,
    }
    if rep:
        slots, model, stems = rep["slots"], rep["model"], rep["stems"]
        dedup = rep["cell"].split("/")[0]
        meta.update({
            "scored_cell": rep["cell"],
            "spies": model.get("spies"), "spy_24s": model.get("spy_24s"),
            "honest_reachable": model.get("honest_reachable"), "honest_reachable_24s": model.get("honest_reachable_24s"),
            "light_out": slots.get("light", {}).get("out"),
            "light_out_quarters": [slots.get(f"light:q{i}", {}).get("out") for i in range(1, 5)],
            "model_out": model.get(dedup),
            "fluff_per_hop": stems.get("fluff_per_hop"), "stem_txs": stems.get("txs"),
            "stem_hops_implied": stems.get("stem_hops_implied"), "embargo_rate": stems.get("embargo_rate"),
        })
    (dest / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    return dest


def fmt(v, spec=""):
    return "-" if v is None else format(v, spec)


def table():
    rows = [json.loads(p.read_text()) for p in sorted(RUNS.glob("*/meta.json"))]
    out = ["| Run | Box | Spies / /24s | Honest reachable / /24s | Light out-share (model) | By quarter | "
           "Fluff per hop | Stem txs | Wall | Min free RAM (GiB, box) | Exit | Note |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in rows:
        q = m.get("light_out_quarters")
        quarters = ", ".join(fmt(x, ".3f") for x in q) if q and any(x is not None for x in q) else "-"
        gb = None if m.get("min_avail_mb") is None else m["min_avail_mb"] / 1024
        out.append("| " + " | ".join([
            f"`{m['run_id']}`", m["box"],
            f"{fmt(m.get('spies'))} / {fmt(m.get('spy_24s'))}",
            f"{fmt(m.get('honest_reachable'))} / {fmt(m.get('honest_reachable_24s'))}",
            f"{fmt(m.get('light_out'), '.4f')} ({fmt(m.get('model_out'), '.4f')})",
            quarters, fmt(m.get("fluff_per_hop"), ".3f"), fmt(m.get("stem_txs")),
            fmt(m.get("wall")), fmt(gb, ".1f"), fmt(m.get("exit_code")), m.get("note") or "",
        ]) + " |")
    text = JOURNAL.read_text()
    if START not in text or END not in text:
        sys.exit(f"{JOURNAL} lacks the {START} / {END} markers")
    head, rest = text.split(START, 1)
    tail = rest.split(END, 1)[1]
    JOURNAL.write_text(head + START + "\n" + "\n".join(out) + "\n" + END + tail)
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("archive_dir")
    a.add_argument("--box", required=True, help="the machine the run was on (phantom, simbox2, simbox3)")
    a.add_argument("--note", default="")
    a.add_argument("--estimators", default="", help="spy_estimators.py report(s), comma-separated .txt/.json")
    n = sub.add_parser("annotate")
    n.add_argument("run_id")
    n.add_argument("text")
    sub.add_parser("table")
    args = ap.parse_args(argv)
    if args.cmd == "add":
        est = [f for f in args.estimators.split(",") if f]
        print(add(args.archive_dir, args.box, args.note, est))
    elif args.cmd == "annotate":
        f = RUNS / args.run_id / "meta.json"
        meta = json.loads(f.read_text())
        meta["note"] = (meta.get("note") or "") + f" [{datetime.date.today()}] {args.text}"
        f.write_text(json.dumps(meta, indent=1) + "\n")
    else:
        print(f"{table()} runs in the register")
    return 0


if __name__ == "__main__":
    sys.exit(main())
