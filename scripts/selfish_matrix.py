#!/usr/bin/env python3
"""Selfish-mining experiment matrix runner: strategy x countermeasure x alpha
cells -> generated configs -> paired runs -> one table.

The countermeasure-testing harness (docs/SELFISH_MINING.md §10): a matrix
spec names a base config and one overlay per axis value; every cell is the
cartesian product of axis values applied to the base, so within a matrix all
cells share seed/shape and differ only by the axis variables — paired
comparisons by construction. Countermeasures are overlays too: a flag-gated
monerod-sim patch is a `honest: {daemon_options: {...}}` overlay on the
honest miners; an agent-level countermeasure overrides `script`/`attributes`
the same way.

Spec (YAML):

    name: pop_vs_es            # matrix name; workdir matrix_runs/<name>/
    base: test_configs/selfish_micro.yaml
    stop_time: 6h              # optional base overrides
    seed: 12345
    parallel: 2                # concurrent runs (box fits 2 x 6h selfish runs)
    axes:
      strategy:                # axis -> {value: overlay}
        es:     {attacker: {attributes: {strategy: eyal_sirer}}}
        es_r2:  {attacker: {attributes: {release_lead: "2"}}}
        honest: {attacker: {attributes: {strategy: honest}}}
      countermeasure:
        none: {}
        pop:   {honest: {daemon_options: {sim-publish-or-perish: true}}}
      alpha:                   # hashrate may be a scalar or a per-miner list
        a040:  {attacker: {hashrate: 4}, honest: {hashrate: [3, 3]}}
    exclude:                   # optional: partial cell matches to skip
      - {strategy: honest, countermeasure: pop}

Overlay targets: `attacker` (the one agents.selfish_miner), `honest` (every
agents.autonomous_miner that is not the attacker and not eclipsed — eclipse
victims are a separate population), `bridges` (every agents.selfish_bridge),
`all` (every agent with a daemon). Sub-dicts (attributes, daemon_options)
MERGE; scalars override.

Per cell the runner writes the generated config, invokes
`nice -n10 ./run_sim.sh --config <cfg> --name <run> --no-monitor`, analyzes
the archived run with scripts.selfish_mining_analysis.analyze_run (structured
— no report parsing), and records one row. Rows persist as
matrix_runs/<name>/cells/<cell>.json, so re-running the spec resumes: only
cells without a marker run again (--fresh discards them). Output:
matrix_runs/<name>/{table.md, results.json}. Exit 0 iff every cell ran and
analyzed (verdict FAILs inside a completed run are results, not errors).
"""
import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Matrix workdirs are reproducible from spec + base (both committed); the runs
# themselves are archived under archived_runs/ like any hand-launched run.
DEFAULT_WORKROOT = REPO_ROOT / "matrix_runs"
DEFAULT_ARCHIVE = REPO_ROOT / "archived_runs"


def _sanitize(name: str) -> str:
    """run_sim.sh restricts run names to [A-Za-z0-9._-]; match it so the
    runner's recorded name equals the archived directory's."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def load_spec(path) -> dict:
    with open(path) as f:
        spec = yaml.safe_load(f)
    for key in ("name", "base", "axes"):
        if key not in spec:
            raise SystemExit(f"spec missing required key: {key}")
    if not Path(spec["base"]).is_absolute():
        spec["base"] = str(REPO_ROOT / spec["base"])
    return spec


def _agent_targets(cfg: dict) -> dict:
    """Classify agents into overlay targets. Eclipsed autonomous miners
    (eclipse victims) are deliberately NOT in `honest`: a countermeasure
    deployed on the honest network should not silently reach victims the
    attacker isolates anyway — compose explicitly via `all` or a new target
    if an experiment wants that."""
    agents = cfg["agents"]
    attackers = [k for k, v in agents.items() if v.get("script") == "agents.selfish_miner"]
    if len(attackers) != 1:
        raise SystemExit(f"base config must have exactly one agents.selfish_miner, found {attackers}")
    honest = [k for k, v in agents.items()
              if v.get("script") == "agents.autonomous_miner"
              and v.get("attributes", {}).get("eclipsed") != "true"]
    return {
        "attacker": attackers,
        "honest": honest,
        "bridges": [k for k, v in agents.items() if v.get("script") == "agents.selfish_bridge"],
        # Forwarding nodes: run a daemon but are neither miner nor bridge nor
        # attacker. SoP-style gossip countermeasures must reach these too —
        # a vanilla-monerod relay drops unknown levin messages (shares), so
        # those specs flip relays to monerod-sim via this target.
        "relays": [k for k, v in agents.items()
                   if "daemon" in v
                   and v.get("script") not in ("agents.autonomous_miner",
                                               "agents.selfish_miner",
                                               "agents.selfish_bridge")],
        "all": [k for k, v in agents.items() if "daemon" in v],
    }


def _merge_stanza(stanza: dict, overlay: dict, where: str) -> None:
    """Sub-dicts (attributes, daemon_options) merge; scalars override."""
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(stanza.get(key), dict):
            stanza[key].update(val)
        else:
            stanza[key] = val


def apply_overlay(cfg: dict, overlay: dict, where: str) -> None:
    targets = _agent_targets(cfg)
    for target, sub in overlay.items():
        if target not in targets:
            raise SystemExit(f"{where}: unknown overlay target {target!r} "
                             f"(known: {sorted(targets)})")
        agents = targets[target]
        if not agents:
            raise SystemExit(f"{where}: overlay target {target!r} matches no agents")
        for aid in agents:
            _merge_stanza(cfg["agents"][aid], sub, where)


def _apply_hashrates(cfg: dict, overlay: dict, where: str) -> None:
    """`hashrate` on honest may be a scalar (all miners) or a list applied in
    config order (per-miner splits); the list must name every honest miner so
    the split is never silently partial."""
    sub = overlay.get("honest")
    if not sub or "hashrate" not in sub:
        return
    hr = sub.pop("hashrate")
    honest = _agent_targets(cfg)["honest"]
    if isinstance(hr, list):
        if len(hr) != len(honest):
            raise SystemExit(f"{where}: honest hashrate list of {len(hr)} "
                             f"but {len(honest)} honest miner(s) {honest}")
        for aid, h in zip(honest, hr):
            cfg["agents"][aid]["hashrate"] = h
    else:
        for aid in honest:
            cfg["agents"][aid]["hashrate"] = hr


def build_config(spec: dict, cell_overlays: dict) -> dict:
    """Base config + general overrides + every axis overlay, in axis order."""
    with open(spec["base"]) as f:
        cfg = yaml.safe_load(f)
    if spec.get("stop_time"):
        cfg["general"]["stop_time"] = spec["stop_time"]
    if spec.get("seed"):
        cfg["general"]["simulation_seed"] = spec["seed"]
    for axis, overlay in cell_overlays.items():
        if not isinstance(overlay, dict):
            raise SystemExit(f"axis {axis!r} overlay must be a mapping, got {overlay!r}")
        _apply_hashrates(cfg, overlay, f"axis {axis!r}")
        apply_overlay(cfg, overlay, f"axis {axis!r}")
    return cfg


def plan_cells(spec: dict) -> list:
    """Cartesian product of axis values as (cell_name, values, overlays)
    tuples, minus excluded partial matches. Axis order is spec order."""
    axes = spec["axes"]
    names = list(axes)
    cells = []
    for combo in itertools.product(*(axes[a] for a in names)):
        values = dict(zip(names, combo))            # axis -> value label
        for excl in spec.get("exclude") or []:
            if all(values.get(k) == v for k, v in excl.items()):
                break
        else:
            cell = "_".join(_sanitize(v) for v in combo)
            overlays = {a: axes[a][lbl] for a, lbl in values.items()}
            cells.append((cell, values, overlays))
    return cells


def _find_new_rundir(archive: Path, run_name: str, before: set) -> Path:
    after = set(str(p) for p in archive.glob(f"*_{run_name}"))
    new = sorted(after - before)
    return Path(new[-1]) if new else None


def run_cell(spec, cell, values, overlays, workdir: Path, archive: Path,
             nice_level: int = 10) -> dict:
    """Generate the cell config, launch its run, analyze it, persist the row.
    `values` is the axis->label mapping (recorded in the row); `overlays` is
    the axis->overlay mapping build_config consumes. The row json doubles as
    the resume marker."""
    from scripts.selfish_mining_analysis import AnalysisInputError, analyze_run

    marker = workdir / "cells" / f"{cell}.json"
    if marker.exists():
        return json.loads(marker.read_text())

    cfg = build_config(spec, overlays)
    cfg_path = workdir / "configs" / f"{cell}.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    run_name = _sanitize(f"{spec['name']}__{cell}")
    before = set(str(p) for p in archive.glob(f"*_{run_name}"))
    t0 = time.time()
    proc = subprocess.run(
        ["nice", f"-n{nice_level}", "./run_sim.sh", "--config", str(cfg_path),
         "--name", run_name, "--no-monitor"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    row = {
        "cell": cell,
        "values": values,
        "config": str(cfg_path),
        "run_name": run_name,
        "returncode": proc.returncode,
        "wall_s": round(time.time() - t0, 1),
    }
    if proc.returncode != 0:
        row["error"] = (proc.stderr or proc.stdout or "").strip()[-2000:]
    else:
        run_dir = _find_new_rundir(archive, run_name, before)
        if run_dir is None:
            row["error"] = "run_sim exited 0 but no new archived run dir found"
        else:
            row["run_dir"] = str(run_dir)
            try:
                r = analyze_run(run_dir)
                row.update({k: r[k] for k in (
                    "alpha", "alpha_eff", "release_lead", "eclipse", "share",
                    "controlled", "gamma", "n_ties", "attacker_orphan_rate",
                    "network_orphan_rate", "canonical_blocks", "msb_max_z")})
                row["theory"] = r["theory"]
                row["verdicts"] = [(v["name"], v["pass"]) for v in r["verdicts"]]
                row["all_verdicts_pass"] = all(v["pass"] for v in r["verdicts"])
            except AnalysisInputError as e:
                row["error"] = f"analysis: {e}"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(row, indent=1, default=str))
    return row


def render_table(spec: dict, rows: list) -> str:
    axes = list(spec["axes"])
    head = (axes + ["alpha", "share", "ctrl", "gamma", "att_orph", "net_orph",
                    "msb_z", "blocks", "verdicts", "run"])
    lines = [f"# Matrix {spec['name']}", "",
             f"- base: `{spec['base']}`  seed: {spec.get('seed', '(base)')}"
             f"  stop_time: {spec.get('stop_time', '(base)')}",
             f"- cells: {len(rows)}  failures: "
             f"{sum(1 for r in rows if 'error' in r)}", "", "| " + " | ".join(head) + " |",
             "|" + "---|" * len(head)]
    for r in sorted(rows, key=lambda r: r["cell"]):
        verdict = ("-" if "error" in r else
                   ("PASS" if r.get("all_verdicts_pass") else "FAIL")
                   + f" ({len(r.get('verdicts', []))})")
        def fmt(k):
            return "-" if r.get(k) is None else f"{r[k]:.3f}"
        lines.append("| " + " | ".join(
            [r["cell"]] + [fmt("alpha"), fmt("share"), fmt("controlled"),
                           fmt("gamma"), fmt("attacker_orphan_rate"),
                           fmt("network_orphan_rate"), fmt("msb_max_z"),
                           str(r.get("canonical_blocks", "-")),
                           verdict,
                           Path(r.get("run_dir", "-")).name]) + " |")
    if failed := [r for r in rows if "error" in r]:
        lines += ["", "## Failed cells", ""]
        for r in failed:
            lines.append(f"- `{r['cell']}`: {r['error'][:400]}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="matrix spec YAML")
    ap.add_argument("--dry-run", action="store_true",
                    help="generate configs and list cells; run nothing")
    ap.add_argument("--fresh", action="store_true",
                    help="discard previous cell markers and re-run everything")
    ap.add_argument("--parallel", type=int, default=None,
                    help="concurrent runs (default: spec 'parallel', else 1)")
    ap.add_argument("--cells", default=None,
                    help="comma-separated substrings; run only matching cells")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    cells = plan_cells(spec)
    if args.cells:
        wanted = [s.strip() for s in args.cells.split(",") if s.strip()]
        cells = [c for c in cells if any(w in c[0] for w in wanted)]
    workroot = Path(os.environ.get("MONEROSIM_MATRIX_WORKROOT", DEFAULT_WORKROOT))
    workdir = workroot / _sanitize(spec["name"])
    workdir.mkdir(parents=True, exist_ok=True)
    with open(workdir / "spec.yaml", "w") as f:
        yaml.safe_dump(spec, f, sort_keys=False)

    if args.dry_run:
        for cell, values, overlays in cells:
            cfg = build_config(spec, overlays)
            out = workdir / "configs" / f"{cell}.yaml"
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w") as f2:
                yaml.safe_dump(cfg, f2, sort_keys=False)
            print(f"{cell}: {out}")
        print(f"{len(cells)} cell(s) planned (dry run)")
        return 0

    if args.fresh:
        for m in (workdir / "cells").glob("*.json"):
            m.unlink()

    archive = Path(os.environ.get("MONEROSIM_ARCHIVE_BASE", DEFAULT_ARCHIVE))
    parallel = args.parallel or spec.get("parallel", 1)
    rows = []
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futs = {pool.submit(run_cell, spec, cell, values, overlays,
                            workdir, archive): cell
                for cell, values, overlays in cells}
        for fut in as_completed(futs):
            row = fut.result()
            rows.append(row)
            status = "ERROR: " + row["error"][:120] if "error" in row else \
                (f"share {row['share']:.3f}" + (
                    f", controlled {row['controlled']:.3f}"
                    if row.get("controlled") is not None else ""))
            print(f"[matrix] {row['cell']}: {status}", flush=True)

    rows.sort(key=lambda r: r["cell"])
    (workdir / "results.json").write_text(json.dumps(rows, indent=1, default=str))
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    table = render_table(spec, rows)
    table = (f"commit: `{commit}`\n" + table)
    (workdir / "table.md").write_text(table)
    print(table)
    return 1 if any("error" in r for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
