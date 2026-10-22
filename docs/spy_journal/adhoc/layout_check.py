import sys, collections, yaml
sys.path.insert(0, "/home/lever65/monerosim/analysis/spy")
import x0_calibration as x
for d in sys.argv[1:]:
    hosts = yaml.safe_load(open(f"{d}/shadow_agents.yaml"))["hosts"]
    sub = collections.defaultdict(lambda: [0, 0])      # /24 -> [spy, honest] monerod daemons
    for name, h in hosts.items():
        ip = h.get("ip_addr")
        if not ip or not any("monerod" in str(p.get("path", "")) for p in h.get("processes", [])):
            continue
        sub[".".join(ip.split(".")[:3])][0 if name.startswith("spy") else 1] += 1
    spy = {s: c for s, c in sub.items() if c[0]}
    mixed = {s: c for s, c in spy.items() if c[1]}
    honest = [s for s, c in sub.items() if c[1]]
    print(d.rsplit("/", 1)[1])
    print(f"  spy daemons {sum(c[0] for c in spy.values())} in {len(spy)} /24s; honest daemons {sum(c[1] for c in sub.values())} in {len(honest)} /24s; spy /24s shared with honest: {len(mixed)}")
    print("  model:", x.subnet_model(d))
