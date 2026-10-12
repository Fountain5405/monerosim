#!/usr/bin/env python3
"""Compare wall time and eclipse outcome of runs of the 2232-host eclipse config.

Usage: compare_eclipse_runs.py RUN_DIR [RUN_DIR...]
Reads memory_samples.csv (wall vs sim time) and eclipse_metrics.jsonl (target
relay-4000) from each run dir; for a live run the metrics come from
/tmp/monerosim-<run_id>/shared/. Phase boundaries are this config's: monerod
starts end at sim 1.3 h, attackers start at 14.0-17.45 h, stop at 50 h.
Used for docs/20261006_bootfast_eclipse_reproduction.md.
"""
import csv, json, os, sys


def samples(run):
    rows = list(csv.DictReader(open(os.path.join(run, "memory_samples.csv"))))
    rows = [r for r in rows if int(r["sim_s"]) >= 0]
    t0 = int(list(csv.DictReader(open(os.path.join(run, "memory_samples.csv"))))[0]["epoch"])
    return [(int(r["epoch"]) - t0, int(r["sim_s"]), int(r["nprocs"]), int(r["total_mb"])) for r in rows]


def wall_at(s, sim_target):
    for wall, sim, _, _ in s:
        if sim >= sim_target:
            return wall / 3600
    return None


def metrics(run):
    p = os.path.join(run, "eclipse_metrics.jsonl")
    if not os.path.exists(p):
        p = f"/tmp/monerosim-{os.path.basename(run.rstrip('/'))}/shared/eclipse_metrics.jsonl"
    return [json.loads(l) for l in open(p) if l.strip()]


def at(rows, t):
    return min(rows, key=lambda r: abs(r["sim_t"] - t))


def shadow_wall(run):
    last = None
    for line in open(os.path.join(run, "shadow_run.log"), errors="replace"):
        if line.startswith("Progress:"):
            last = line
    return last.strip() if last else None


def main():
    runs = sys.argv[1:]
    names = [os.path.basename(r.rstrip("/"))[:15] for r in runs]
    S = [samples(r) for r in runs]

    print("== Wall-clock hours to reach each simulated time (from memory_samples.csv)")
    marks = [("startup done (sim 1.5 h)", 5400), ("sim 10 h", 36000),
             ("burn-in done, attackers start (sim 15.7 h)", 56520),
             ("all attackers up (sim 17.5 h)", 63000), ("sim 30 h", 108000),
             ("sim 40 h", 144000), ("end (sim 50 h)", 179800)]
    print(f"{'':45s}" + "".join(f"{n:>17s}" for n in names))
    for label, t in marks:
        vals = [wall_at(s, t) for s in S]
        print(f"{label:45s}" + "".join(f"{v:17.2f}" if v is not None else f"{'-':>17s}" for v in vals))
    for n, s in zip(names, S):
        print(f"{n}: peak memory {max(x[3] for x in s)/1024:.0f} GB, last sample sim {s[-1][1]/3600:.2f} h at wall {s[-1][0]/3600:.2f} h")
    for n, r in zip(names, runs):
        try:
            print(f"{n}: {shadow_wall(r)}")
        except OSError:
            pass

    print("\n== Phase durations (wall hours)")
    for n, s in zip(names, S):
        a, b, c, d = (wall_at(s, 5400), wall_at(s, 56520), wall_at(s, 63000), wall_at(s, 179800))
        if None in (a, b, c, d):
            print(f"{n}: incomplete"); continue
        print(f"{n}: startup {a:.2f}  burn-in {b-a:.2f}  attacker start-up {c-b:.2f}  attack {d-c:.2f}  total {d:.2f}")

    print("\n== Target relay-4000: attacker share of outbound connections (out_attacker/n_out)")
    M = [metrics(r) for r in runs]
    print(f"{'sim h':>6s}" + "".join(f"{n:>17s}" for n in names))
    for h in range(15, 51, 2):
        cells = []
        for rows in M:
            if rows[-1]["sim_t"] < h * 3600 - 300:
                cells.append(f"{'-':>17s}"); continue
            tg = at(rows, h * 3600)["targets"][0]
            cells.append(f"{tg['out_attacker']:>9d}/{tg['n_out']:<7d}")
        print(f"{h:6d}" + "".join(cells))
    for n, rows in zip(names, M):
        tg = rows[-1]["targets"][0]
        tte = tg.get("tte_sim_t")
        full = [r["sim_t"] for r in rows if r["targets"][0]["n_out"] and
                r["targets"][0]["out_attacker"] == r["targets"][0]["n_out"]]
        frac = len(full) / max(1, sum(1 for r in rows if r["sim_t"] >= (tte or 1e12)))
        print(f"{n}: tte {tte/3600 if tte else float('nan'):.2f} h; final {tg['out_attacker']}/{tg['n_out']} at sim "
              f"{rows[-1]['sim_t']/3600:.2f} h; fully eclipsed in {frac:.0%} of polls after tte; "
              f"max white {max(r['targets'][0]['white_size'] for r in rows)}, "
              f"max gray {max(r['targets'][0]['gray_size'] for r in rows)}")


if __name__ == "__main__":
    main()
