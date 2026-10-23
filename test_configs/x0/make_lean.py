#!/usr/bin/env python3
"""Lean peer-selection cells: push the honest-reachable-/24 : spy-/24 ratio toward
mainnet's without a full replica (docs/X0_CALIBRATION.md, "Scaling the /24 cells").

X0's cell is 83% unreachable light nodes. An unreachable node is in nobody's peer list,
so it doesn't decide the spies' share of outbound slots; the reachable honest /24s and
the spy /24s do. This builds the X0 replica with the unreachable majority cut to --users
and the reachable honest set grown to --reachable, so mainnet's ~3,700 honest /24s
against 6-9 spy /24s is reached with ~700 daemons instead of ~3,700. A node skips the
subnet of every peer it picks, so k spy /24s hold at most k of its outbound slots: one
dense /24 (--spy-subnets 1) caps `legacy` near 0.07; use 6 for a share near X0's.

Same classes, sizes and hubs as x0_2024.scenario.yaml (5 miners, 48 medium, 8 observers,
6 seeds), plus --reachable minus those as pinned-reachable relays (relay-r-*), the spies
(15% of reachable IPs, variant R, announced through the seeds), and --users unreachable
users. Relays start one every --interval sim-seconds so RandomX caches don't outrun KSM.

Spy /24s beyond 6 need --spy-node0 away from 828: placement is sequential from each region's first
node and prefix sharing packs relays onto its last ones, and the script refuses a cell in which a spy
/24 also holds an honest daemon. X1's two 2026-09 presets at H=300 (docs/20261018_spy_node_defenses.md
§5.3; /24 counts keep mainnet's spy : honest ratio, 9 : 3,732 dense, ~322 : 3,732 tail):
  core  --reachable 300 --spy-subnets 1  --spies-per-subnet 113 --dedup 24 --warmup 21600
  tail  --reachable 300 --spy-subnets 21 --spies-per-subnet 2   --dedup 24 --warmup 21600 --spy-node0 600

Usage: test_configs/x0/make_lean.py --reachable 600 --spy-subnets 1 [--dedup 24] [--list half]
Writes test_configs/x0/cells/lean_<dedup>_<list>_h<H>_k<K>_s<seed>.yaml
"""
import argparse
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PY = REPO / "venv" / "bin" / "python"
SRC = HERE / "x0_2024.scenario.yaml"
OUT = HERE / "cells"

# Fallback seeds, in the order monero-seed-001..006 get them (as in x0_2024.scenario.yaml).
SEED_IPS = ["176.9.0.187", "88.198.163.90", "192.99.8.110", "37.187.74.171", "88.99.195.15", "5.104.84.64"]
FIXED_HONEST = 5 + 48 + 8 + 6   # miners + medium + observers + seeds
SPY_NODE0 = 828                  # NA GML nodes 828.. as in X0
MONEROSIM = REPO / "target" / "release" / "monerosim"
# --probe: the monitor log categories plus net.p2p:DEBUG, which logs each outbound pick's
# "Looking at N subnet-deduplicated peers out of M" and the candidate it considers.
PROBE_LOG = ("*:WARNING,blockchain:INFO,txpool:INFO,net.p2p:DEBUG,net.p2p.msg:INFO,daemon.rpc:INFO,"
             "global:INFO,stacktrace:INFO,logging:INFO,msgwriter:INFO,verify:FATAL,serialization:FATAL,perf.*:FATAL")


def opts(d, ban):
    items = dict(d)
    if ban:
        items["ban-list"] = f'"{ban}"'
    return "{" + ", ".join(f"{k}: {v}" for k, v in items.items()) + "}"


def agents_yaml(a, ban):
    """ban: path of the ban list, or '' for none."""
    L = []
    w = L.append
    w("agents:")
    w("  miner-{001..005}:")
    w("    daemon: monerod-sim\n    wallet: monero-wallet-rpc\n    script: agents.autonomous_miner")
    w("    start_time: 0s\n    start_time_stagger: 1s\n    hashrate: [10, 10, 10, 10, 10]")
    w("    can_receive_distributions: true")
    w("    daemon_options:\n      out-peers: 100\n      in-peers: 100\n      hide-my-port: false\n")

    for letter, out in (("a", 16), ("b", 22), ("c", 28)):
        for rng, adopter in (("001..008", True), ("009..016", False)):
            w(f"  medium-{letter}-{{{rng}}}:")
            w("    daemon: monerod-sim\n    start_time: 0s\n    start_time_stagger: auto")
            w("    daemon_options: " + opts({"out-peers": out, "hide-my-port": "false"}, ban if adopter else ""))
    w("")

    half_u = a.users // 2
    for rng, adopter in ((f"001..{half_u:03d}", True), (f"{half_u + 1:03d}..{a.users:03d}", False)):
        if rng.split("..")[0] > rng.split("..")[1]:
            continue
        w(f"  user-{{{rng}}}:")
        w("    daemon: monerod-sim\n    wallet: monero-wallet-rpc\n    script: agents.regular_user")
        w("    start_time: 1200s\n    start_time_stagger: auto\n    transaction_interval: 300")
        w("    activity_start_time: auto\n    can_receive_distributions: true")
        if adopter and ban:
            w("    daemon_options: " + opts({}, ban))
    w("")

    r = max(0, a.reachable - FIXED_HONEST)
    ra = (r + 1) // 2
    rb = r - ra
    T = a.interval
    for tag, n, adopter, off in (("a", ra, True, 0), ("b", rb, False, T)):
        if n <= 0:
            continue
        k = min(a.probe, n // 2)
        # head and tail relays of each start order are probes; the middle is plain
        for lo, hi, probe in ((1, k, True), (k + 1, n - k, False), (n - k + 1, n, True)):
            if lo > hi:
                continue
            w(f"  relay-r-{tag}-{{{lo:03d}..{hi:03d}}}:")
            w("    daemon: monerod-sim")
            w(f"    start_time: {1200 + off + (lo - 1) * 2 * T}s\n    start_time_stagger: {2 * T}s")
            extra = {"hide-my-port": "false"}
            if probe:
                extra["peerlist-dump-file"] = "peerlist_dump.jsonl"
                extra["log-level"] = f'"{PROBE_LOG}"'
            w("    daemon_options: " + opts(extra, ban if adopter else ""))
    w("")

    for rng, adopter in (("001..004", True), ("005..008", False)):
        w(f"  observer-{{{rng}}}:")
        w("    daemon: monerod-sim\n    start_time: 0s\n    start_time_stagger: 3s")
        w("    daemon_options: " + opts({"hide-my-port": "false", "peerlist-dump-file": "peerlist_dump.jsonl"},
                                         ban if adopter else ""))
    w("  monero-seed-{001..006}:\n    daemon: monerod-sim\n    start_time: 0s\n    start_time_stagger: 1s\n")

    # One group per spy /24 once there are more than 6 (each group dials one fallback seed, so
    # the seeds are shared round-robin); up to 6 /24s the groups stay a-f, as in X0.
    groups = max(6, a.spy_subnets)
    counts = [a.spies // groups + (1 if j < a.spies % groups else 0) for j in range(groups)]
    for j, n in enumerate(counts):
        if n <= 0:
            continue
        tag = "abcdefghijklmnopqrstuvwxyz"[j] if j < 26 else f"x{j}"
        w(f"  spy-{tag}-{{001..{n:03d}}}:")
        w("    daemon: monerod-sim")
        w(f"    start_time: {10 * j}s\n    start_time_stagger: 60s")
        w(f"    topology_node: {a.spy_node0 + (j % a.spy_subnets)}")
        w("    daemon_options: " + opts({"hide-my-port": "false",
                                         "add-exclusive-node": f'"{SEED_IPS[j % len(SEED_IPS)]}:18080"'}, ""))
    w("\n  miner-distributor:\n    script: agents.miner_distributor\n    wait_time: auto\n")
    w("  simulation-monitor:\n    script: agents.simulation_monitor\n    poll_interval: 300")
    return "\n".join(L) + "\n"


def scenario_text(a, ban):
    src = SRC.read_text()
    head = src[src.index("general:"):src.index("\nagents:")]
    last_relay = 1200 + a.interval * max(0, a.reachable - FIXED_HONEST)
    bootstrap = max(2 * 3600, int(math.ceil((last_relay + a.warmup) / 1800.0)) * 1800)
    stop = bootstrap + 4 * 3600
    head = re.sub(r"(?m)^(  simulation_seed:).*", rf"\1 {a.seed}", head)
    head = re.sub(r"(?m)^(    sim-subnet-dedup:).*", rf'\1 "{a.dedup}"', head)
    if a.fixed_rx_seed:
        head = re.sub(r"(?m)^(    sim-subnet-dedup:)", r"    sim-fixed-randomx-seed: true\n\1", head)
    head = re.sub(r"(?m)^(  stop_time:).*", rf"\1 {stop}s", head)
    head = re.sub(r"(?m)^(  bootstrap_end_time:).*", rf"\1 {bootstrap}s", head)
    n_spy = a.spies
    title = (f"# Lean cell: {a.reachable} honest reachable daemons, {n_spy} spies in {a.spy_subnets} /24"
             f"{'s' if a.spy_subnets != 1 else ''}, {a.users} unreachable users; "
             f"dedup {a.dedup}, ban list {a.list}, seed {a.seed}.\n"
             f"# Generated by test_configs/x0/make_lean.py; see that file's docstring.\n")
    return title + head + "\n" + agents_yaml(a, ban)


def expand(a, ban, out):
    with tempfile.NamedTemporaryFile("w", dir=OUT, suffix=".scenario.yaml", delete=False) as tmp:
        tmp.write(scenario_text(a, ban))
        name = tmp.name
    try:
        subprocess.run([str(PY), str(REPO / "scripts" / "generate_config.py"), "--from", name, "-o", str(out),
                        "--no-safe-tx-interval"], check=True, stdout=subprocess.DEVNULL)
    finally:
        Path(name).unlink(missing_ok=True)


def check_layout(cell):
    """Fail if a spy /24 holds an honest daemon: placement is sequential from each region's first node
    and prefix sharing packs relays onto the region's last nodes, so pins there can collide. Costs a
    dry run of monerosim (seconds). Returns the colliding /24s."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([str(MONEROSIM), "--config", str(cell), "--output", tmp], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        hosts = yaml.safe_load(Path(tmp, "shadow_agents.yaml").read_text())["hosts"]
    subnets = {}
    for name, h in hosts.items():
        ip = h.get("ip_addr")
        if ip and any("monerod" in str(p.get("path", "")) for p in h.get("processes", [])):
            subnets.setdefault(ip.rsplit(".", 1)[0], set()).add(name.startswith("spy"))
    return sorted(s for s, kinds in subnets.items() if len(kinds) == 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reachable", type=int, default=71, help="honest reachable daemons (X0: 71)")
    ap.add_argument("--spies", type=int, default=None, help="default: 15%% of reachable IPs (0.1765 x reachable)")
    ap.add_argument("--spy-subnets", type=int, default=1, help="spy /24s (X0: 6)")
    ap.add_argument("--spy-node0", type=int, default=SPY_NODE0,
                    help="first GML node for the spy /24s (North America is nodes 0-849; honest agents sit "
                         "on its first ~250 nodes and its last ~25, so 828.. collides beyond 6 /24s: use 600)")
    ap.add_argument("--spies-per-subnet", type=int, default=None,
                    help="spy daemons in each spy /24; sets --spies to this x --spy-subnets")
    ap.add_argument("--users", type=int, default=40, help="unreachable users with wallets")
    ap.add_argument("--dedup", choices=["legacy", "24", "none"], default="legacy")
    ap.add_argument("--list", choices=["none", "half"], default="none")
    ap.add_argument("--ban-coverage", type=float, default=1.0,
                    help="with --list half: fraction of the spy /24s the list names, densest first "
                         "(scripts/spy_ban_list.py --coverage); the real list misses part of a diversified tail")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--fixed-rx-seed", action="store_true",
                    help="every daemon gets --sim-fixed-randomx-seed (needs a monerod-sim built with "
                         "patches/monero-sim-fixed-randomx-seed.patch). Without it a cell that runs past chain height "
                         "2113 (about 20 h) has all its daemons re-derive their RandomX cache at once and a 32 GB box "
                         "runs out of memory (journal E18); with it there is no limit on --warmup")
    ap.add_argument("--interval", type=int, default=20, help="sim-seconds between relay starts")
    ap.add_argument("--probe", type=int, default=0,
                    help="relays at the head and at the tail of each start order that dump their peer list "
                         "every 30 s and log net.p2p at DEBUG (a few MB each; 0 = none)")
    ap.add_argument("--warmup", type=int, default=3600,
                    help="sim-seconds between the last relay start and the first user activity; outbound "
                         "connections made from the early, small peer lists last ~1.5 h, so a /24 cell's "
                         "share falls for ~3 h of activity (use 21600 to start near steady state)")
    a = ap.parse_args()
    if a.spies_per_subnet is not None:
        if a.spies is not None:
            ap.error("--spies and --spies-per-subnet are alternatives")
        a.spies = a.spies_per_subnet * a.spy_subnets
    if a.spies is None:
        a.spies = round(0.1765 * a.reachable)
    OUT.mkdir(exist_ok=True)
    wtag = (("" if a.warmup == 3600 else f"_w{a.warmup // 3600}h") + (f"_p{a.probe}" if a.probe else "")
            + (f"_m{a.spies_per_subnet}" if a.spies_per_subnet is not None else "")
            + (f"_n{a.spy_node0}" if a.spy_node0 != SPY_NODE0 else "")
            + (f"_c{round(100 * a.ban_coverage)}" if a.list == "half" and a.ban_coverage != 1.0 else "")
            + ("_fx" if a.fixed_rx_seed else ""))
    stem = f"lean_{a.dedup}_{a.list}_h{a.reachable}_k{a.spy_subnets}{wtag}_s{a.seed}"
    out = OUT / f"{stem}.yaml"
    ban = ""
    if a.list == "half":
        ban_file = OUT / f"banlist_{stem.removeprefix('lean_').split('_', 2)[2]}.txt"
        probe = OUT / f".probe_{stem}.yaml"
        expand(a, "", probe)
        subprocess.run([str(PY), str(REPO / "scripts" / "spy_ban_list.py"), str(probe), "-o", str(ban_file),
                        "--coverage", str(a.ban_coverage), "--seed", str(a.seed)],
                       check=True, stdout=subprocess.DEVNULL)
        probe.unlink(missing_ok=True)
        ban = str(ban_file)
    expand(a, ban, out)
    shared = check_layout(out)
    if shared:
        out.unlink()
        sys.exit(f"{stem}: {len(shared)} spy /24s also hold honest daemons ({', '.join(shared[:4])}...); "
                 f"try --spy-node0 (now {a.spy_node0})")
    print(out)


if __name__ == "__main__":
    sys.exit(main())
