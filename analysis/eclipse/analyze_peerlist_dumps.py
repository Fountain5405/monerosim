#!/usr/bin/env python3
"""Compute the paper's B (benign graylist count) and OR (whitelist occupation)
trajectories from the patched-monerod peer-list file dumps + agent_registry.json.

The patched target (relay-4000) and the 30 observed benign relays each append
full white+gray peer-list snapshots to <data-dir>/fake/peerlist_dump.jsonl
(schema: {"t":<sim-clock>,"white_n","gray_n","white":[["ip:port",last_seen],...],
"gray":[...]}). This classifies every entry's IP via the registry:
  benign / attacker (eclipse_fakepeer) / injector / miner / seed / target,
  and "trash" for any IP not in the registry (= attacker-injected junk).

  B(t)   = benign entries in the TARGET's gray list over time (paper Nyx 717 -> ~2)
  OR     = attacker-controlled fraction of a WHITE list
           (attacker + injector + trash) / white_total

Usage: analyze_peerlist_dumps.py <run_dir>
  <run_dir> may be either layout:
    archived run  archived_runs/<run_id>/ -- dumps in daemon_logs/<node>/,
                  registry in transaction_registry/agent_registry.json
    raw/live dir  /tmp/monerosim-<run_id>/ or a preserved raw-data tree --
                  dumps in <node>/fake/, registry in shared/
  Also accepts an explicit --registry <path> override.
"""
import sys, os, json, glob, gzip

args = [a for a in sys.argv[1:] if not a.startswith("--")]
run = args[0].rstrip("/")
reg_override = None
if "--registry" in sys.argv:
    reg_override = sys.argv[sys.argv.index("--registry") + 1]

# ---- registry: ip_addr -> role ----
# run_sim.sh archives the registry to transaction_registry/; a live or
# preserved raw run dir has it in shared/. Try every known home before failing,
# so the same command works on an archive and on a backup-volume raw tree.
REGISTRY_CANDIDATES = (
    ("shared", "agent_registry.json"),               # live /tmp run dir, raw backup tree
    ("transaction_registry", "agent_registry.json"), # archived_runs/<run_id>
    ("agent_registry.json",),                        # hand-assembled dir
)
reg_path = reg_override
if not reg_path:
    for parts in REGISTRY_CANDIDATES:
        cand = os.path.join(run, *parts)
        if os.path.exists(cand):
            reg_path = cand
            break
if not reg_path or not os.path.exists(reg_path):
    sys.exit("no agent_registry.json under %s (looked in %s); pass --registry <path>"
             % (run, ", ".join("/".join(c) for c in REGISTRY_CANDIDATES)))
reg = json.load(open(reg_path))
agents = reg["agents"] if isinstance(reg, dict) and "agents" in reg else reg
ip_role = {}
for a in agents:
    ip = a.get("ip_addr")
    attrs = a.get("attributes") or {}
    role = attrs.get("eclipse_role")
    if not role:
        us, idn = a.get("user_script") or "", a.get("id") or ""
        if "autonomous_miner" in us:
            role = "miner"
        elif idn.startswith("monero-seed"):
            role = "seed"
        else:
            role = "other"
    if ip:
        ip_role[ip] = role
print("registry: %s  (%d ip->role)" % (reg_path, len(ip_role)))

ATTACKER_ROLES = ("attacker", "injector", "trash")

def classify(addr):
    ip = addr.rsplit(":", 1)[0]
    return ip_role.get(ip, "trash")  # not in registry => injected trash

def load_dump(path):
    snaps = []
    op = gzip.open if path.endswith(".gz") else open
    try:
        for ln in op(path, "rt"):
            ln = ln.strip()
            if ln:
                try:
                    snaps.append(json.loads(ln))
                except Exception:
                    pass
    except (OSError, EOFError):
        pass
    return snaps

def breakdown(entries):
    c = {}
    for e in entries:
        addr = e[0] if isinstance(e, (list, tuple)) else e
        r = classify(addr)
        c[r] = c.get(r, 0) + 1
    return c

def atk(c):
    return sum(c.get(r, 0) for r in ATTACKER_ROLES)

# ---- where the per-node dumps live ----
# archive_daemon_logs() moves each dump to daemon_logs/<node>/peerlist_dump.jsonl;
# in a raw run dir the node dirs sit at the top level and the dump is one deeper
# (<node>/fake/). The recursive glob covers both once rooted correctly.
node_root = os.path.join(run, "daemon_logs")
if not os.path.isdir(node_root):
    node_root = run

# ---- TARGET B(t) + OR_white(t) ----
tgt = glob.glob(os.path.join(node_root, "monero-relay-4000", "**", "peerlist_dump.jsonl"), recursive=True)
print("\n=== TARGET relay-4000: B (benign gray) and whitelist OR over time ===")
if tgt:
    snaps = load_dump(tgt[0])
    print("dump: %s  (%d snapshots)" % (tgt[0], len(snaps)))
    print("  t_rel(s)  Wtot Wben Watk  OR_white |  Gtot   B(ben)  Gatk Gtrash")
    t0 = snaps[0]["t"] if snaps else 0
    for s in snaps:
        wb, gb = breakdown(s.get("white") or []), breakdown(s.get("gray") or [])
        wt, gt = sum(wb.values()), sum(gb.values())
        orw = (atk(wb) / wt) if wt else 0.0
        print("  %8d  %4d %4d %4d   %.3f   | %5d  %5d  %4d %5d" % (
            s["t"] - t0, wt, wb.get("benign", 0), atk(wb), orw,
            gt, gb.get("benign", 0), gb.get("attacker", 0) + gb.get("injector", 0), gb.get("trash", 0)))
    if snaps:
        Bs = [breakdown(s.get("gray") or []).get("benign", 0) for s in snaps]
        print("  B trajectory: peak=%d  final=%d  (paper Nyx: 717 -> ~2)" % (max(Bs), Bs[-1]))
else:
    print("NO target dump found under %s/monero-relay-4000/" % node_root)

# ---- OBSERVED BENIGN whitelist OR ----
print("\n=== OBSERVED BENIGN whitelist OR (final snapshot per node) ===")
allb = glob.glob(os.path.join(node_root, "monero-relay-*", "**", "peerlist_dump.jsonl"), recursive=True)
benign_dumps = [p for p in allb if "relay-4000" not in p]
ors = []
for p in benign_dumps:
    snaps = load_dump(p)
    if not snaps:
        continue
    wb = breakdown(snaps[-1].get("white") or [])
    wt = sum(wb.values())
    if wt:
        ors.append(atk(wb) / wt)
if ors:
    ors.sort()
    print("benign nodes with dumps: %d ; whitelist OR: mean=%.3f median=%.3f min=%.3f max=%.3f (paper: ~0.985)" % (
        len(ors), sum(ors) / len(ors), ors[len(ors) // 2], ors[0], ors[-1]))
else:
    print("no benign dumps parsed (%d files found)" % len(benign_dumps))
