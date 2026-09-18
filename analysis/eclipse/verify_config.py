#!/usr/bin/env python3
"""Pre-run sanity check: confirm the firewall lands only on the target and the
registry carries eclipse_role labels. Usage: verify_config.py <shadow_out_dir> <shared_dir>"""
import json
import sys
import yaml

shadow_out, shared = sys.argv[1], sys.argv[2]

# 1) firewall assignment from shadow_agents.yaml
with open(shadow_out + "/shadow_agents.yaml") as fh:
    sh = yaml.safe_load(fh)
hosts = sh.get("hosts", {})
fw = []
for name, h in hosts.items():
    if not isinstance(h, dict):
        continue
    ports = h.get("blocked_inbound_ports") or h.get("host_options", {}).get("blocked_inbound_ports")
    if ports:
        fw.append((name, ports, h.get("ip_addr")))
print("hosts total:", len(hosts))
print("firewalled hosts (blocked_inbound_ports):", fw if fw else "NONE FOUND (check key name)")

# 2) registry eclipse_role classification
with open(shared + "/agent_registry.json") as fh:
    reg = json.load(fh)
agents = reg.get("agents", [])
if isinstance(agents, dict):
    agents = list(agents.values())
byrole = {}
for a in agents:
    role = (a.get("attributes") or {}).get("eclipse_role", "(none)")
    byrole.setdefault(role, []).append((a.get("id"), a.get("ip_addr"), a.get("daemon_rpc_port")))
print("\nregistry agents:", len(agents))
for role in sorted(byrole):
    lst = byrole[role]
    print("  role=%-9s n=%d  e.g. %s" % (role, len(lst), lst[:3]))

# 3) attacker /24 distinctness
atk = [ip for _, ip, _ in byrole.get("attacker", []) if ip]
s24 = {".".join(ip.split(".")[:3]) for ip in atk}
print("\nattacker IPs: %d, distinct /24: %d" % (len(atk), len(s24)))
tgt = byrole.get("target", [])
print("target:", tgt)
