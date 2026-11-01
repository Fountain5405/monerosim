#!/usr/bin/env python3
"""Reveal audit for param_stubborn sim runs (2026-10-27): the sims' attacker
logged 1.7-1.9x the race model's reveals per 72 h at every alpha. The model
counts one reveal per settled race (sop_race_model.SopEnv._reveal: the race
ends, the attacker's blocks are final); the agent logs "<strategy>: reveal
fork=F a=A h=H ..." on every release above the fork point. This groups one
run's reveal lines by fork and reports: reveal lines, distinct forks, the
reveals-per-fork histogram, (a, h) at the first and at repeat reveals, and
how many forks were also publish-released.
Usage: sop_reveal_audit.py RUN_DIR [RUN_DIR...]"""
import collections
import glob
import re
import sys

LINE = re.compile(r"^(\S+ \S+) - attacker-miner - SelfishMinerAgent\[attacker-miner\] - INFO - "
                  r"param_stubborn: (reveal|publish) fork=(\d+) a=(-?\d+) h=(-?\d+) objects=(\d+) "
                  r"weight=(\d+) honest_weight=(\d+)")


def parse(lines):
    """-> [(ts, kind, fork, a, h, objects, weight, honest_weight)], deduplicated."""
    seen, out = set(), []
    for ln in lines:
        m = LINE.match(ln)
        if not m:
            continue
        key = m.group(0)
        if key in seen:
            continue
        seen.add(key)
        ts, kind, *nums = m.groups()
        out.append((ts, kind, *map(int, nums)))
    return out


def summarize(events):
    reveals = [e for e in events if e[1] == "reveal"]
    by_fork = collections.defaultdict(list)
    for e in reveals:
        by_fork[e[2]].append(e)
    publish_forks = {e[2] for e in events if e[1] == "publish"}
    per_fork = collections.Counter(len(v) for v in by_fork.values())
    first_ah = collections.Counter((v[0][3], v[0][4]) for v in by_fork.values())
    repeat_ah = collections.Counter((e[3], e[4]) for v in by_fork.values() for e in v[1:])
    return {
        "reveal_lines": len(reveals),
        "distinct_forks": len(by_fork),
        "per_fork": dict(sorted(per_fork.items())),
        "first_ah": first_ah.most_common(8),
        "repeat_ah": repeat_ah.most_common(8),
        "forks_also_published": len(set(by_fork) & publish_forks),
        "publish_lines": sum(1 for e in events if e[1] == "publish"),
    }


def main(argv):
    for rd in argv[1:]:
        files = glob.glob(f"{rd}/shadow.data/hosts/attacker-miner/bash.*.stdout")
        lines = []
        for f in files:
            with open(f, errors="replace") as fh:
                lines += [ln for ln in fh if "param_stubborn: " in ln]
        s = summarize(parse(lines))
        print(rd.rstrip("/").split("/")[-1].split("__")[-1])
        for k, v in s.items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
