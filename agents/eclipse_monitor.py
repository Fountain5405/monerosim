"""Eclipse-attack measurement agent for the "Are Unreachable Nodes Truly Safe?"
(Nyx) reproduction.

Script-only agent (no local daemon/wallet). Every poll it:
  * loads the agent registry, classifying each node by attribute eclipse_role
    in {attacker, benign, target, ...} and by ip_addr;
  * for each TARGET node (the firewalled/unreachable victim), computes:
      - CTR: fraction of the target's OUTGOING connections whose peer IP is
        attacker-controlled  (get_connections),
      - target whitelist/graylist occupation by attacker vs benign records,
      - B_target: benign graylist entry count  (get_peer_list);
  * for a sample of BENIGN reachable relays, computes whitelist/graylist
    occupation rate (OR) — the paper's N-I metric;
  * appends one JSONL record per poll to <shared_dir>/eclipse_metrics.jsonl and
    logs a compact summary line.

Metrics mirror the paper (OR, CTR, B, TTE, eclipse stability). Nothing here
touches the target inbound; measurement is read-only RPC to each node's own
daemon, exactly as an operator could self-observe.
"""

import json
import sys
import time
from pathlib import Path

from agents.base_agent import BaseAgent, SHADOW_EPOCH
from agents.agent_discovery import AgentDiscovery
from agents.monero_rpc import MoneroRPC, RPCError


def _ip_of_peerlist_entry(entry):
    """get_peer_list entries: v0.18 uses string 'host'; older uses int 'ip'."""
    if not isinstance(entry, dict):
        return None
    h = entry.get("host")
    if isinstance(h, str) and h:
        return h
    ip = entry.get("ip")
    if isinstance(ip, int):
        # monerod stores ip as little-endian uint32 in the legacy field
        return ".".join(str((ip >> (8 * i)) & 0xFF) for i in range(4))
    if isinstance(ip, str) and ip:
        return ip
    return None


def _ip_of_address(addr):
    """'1.2.3.4:18080' -> '1.2.3.4'  (also tolerates bare ip)."""
    if not isinstance(addr, str) or not addr:
        return None
    a = addr.strip()
    if a.startswith("["):  # [ipv6]:port
        return a[1:].split("]", 1)[0]
    return a.rsplit(":", 1)[0] if ":" in a else a


class EclipseMonitorAgent(BaseAgent):
    def __init__(self, poll_interval=30, benign_sample=12, **kwargs):
        super().__init__(**kwargs)
        self._poll_interval = poll_interval
        self._benign_sample = benign_sample
        self._discovery = None
        self._rpc_cache = {}
        self._metrics_path = None
        self._iter = 0
        self._logged_schema = False
        # First sim-time we saw CTR == 12/12 per target (Time-To-Eclipse)
        self._tte = {}

    # ----- attribute helpers -------------------------------------------------
    def _attrs_dict(self):
        raw = getattr(self, "attributes", None) or []
        if isinstance(raw, dict):
            return dict(raw)
        d = {}
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                d[item[0]] = item[1]
        return d

    def _setup_agent(self):
        a = self._attrs_dict()
        if "poll_interval" in a:
            try:
                self._poll_interval = int(a["poll_interval"])
            except (TypeError, ValueError):
                pass
        shared = str(self.shared_dir) if self.shared_dir else None
        self._discovery = AgentDiscovery(shared) if shared else AgentDiscovery()
        self._metrics_path = (self.shared_dir / "eclipse_metrics.jsonl") if self.shared_dir else Path("eclipse_metrics.jsonl")
        self.logger.info(
            "EclipseMonitor up: poll=%ss metrics=%s", self._poll_interval, self._metrics_path
        )

    # ----- registry classification ------------------------------------------
    def _agents_list(self):
        reg = self._discovery.get_agent_registry(force_refresh=True)
        agents = reg.get("agents", [])
        if isinstance(agents, dict):
            agents = list(agents.values())
        return agents or []

    @staticmethod
    def _role_of(agent):
        attrs = agent.get("attributes", {}) or {}
        if isinstance(attrs, list):  # tolerate list-of-pairs
            attrs = {k: v for k, v in attrs if isinstance((k, v), tuple)}
        return attrs.get("eclipse_role")

    def _rpc(self, host, port):
        key = "%s:%s" % (host, port)
        r = self._rpc_cache.get(key)
        if r is None:
            r = MoneroRPC(host, int(port))
            self._rpc_cache[key] = r
        return r

    def _peer_list(self, rpc):
        """monerod exposes get_peer_list as a DIRECT endpoint (/get_peer_list),
        NOT a /json_rpc method, so MoneroRPC.get_peer_list() (which posts to
        /json_rpc) returns -32601. POST to the direct endpoint instead.

        KNOWN ISSUE / TODO (found in the 2,211-host nyx_full run, 2026-09-15):
        at scale the graylist grows into the thousands, so this response gets
        large and `timeout=rpc.timeout` (~10-30s) starts raising "Read timed
        out" under Shadow latency — the graylist-B and occupation (OR) series
        go blank from ~sim 66m on, while CTR (get_connections, tiny payload) is
        unaffected. FIX for future runs: give this call its own generous timeout
        (e.g. 60-120s), and cap wasted time on repeated failures (shrink
        benign_sample and/or stop peerlist polls after N consecutive timeouts).
        The victim's raw monerod log still records peer/graylist events, so B/OR
        remain reconstructable post-hoc."""
        url = rpc.url.replace("/json_rpc", "/get_peer_list")
        resp = rpc.session.post(url, json={}, timeout=rpc.timeout,
                                headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # ----- per-node measurements --------------------------------------------
    def _occupation(self, entries, attacker_ips, benign_ips):
        atk = ben = other = 0
        for e in entries or []:
            ip = _ip_of_peerlist_entry(e)
            if ip in attacker_ips:
                atk += 1
            elif ip in benign_ips:
                ben += 1
            else:
                other += 1
        return atk, ben, other

    def _target_metrics(self, host, port, attacker_ips, benign_ips):
        rpc = self._rpc(host, port)
        out = {"host": host}
        # ---- connections -> CTR ----
        try:
            conns = rpc._make_request("get_connections").get("connections", [])
        except (RPCError, Exception) as e:  # noqa: BLE001
            conns = []
            out["conn_err"] = str(e)[:120]
        if conns and not self._logged_schema:
            self.logger.info("SAMPLE get_connections[0]=%s", json.dumps(conns[0])[:400])
        outgoing = [c for c in conns if not c.get("incoming", False)]
        atk_out = ben_out = oth_out = 0
        for c in outgoing:
            ip = _ip_of_address(c.get("address", ""))
            if ip in attacker_ips:
                atk_out += 1
            elif ip in benign_ips:
                ben_out += 1
            else:
                oth_out += 1
        out.update(
            n_out=len(outgoing), n_in=len(conns) - len(outgoing),
            out_attacker=atk_out, out_benign=ben_out, out_other=oth_out,
            ctr=(atk_out / len(outgoing)) if outgoing else 0.0,
        )
        # ---- peer list -> occupation, B_target ----
        try:
            pl = self._peer_list(rpc)
            if not self._logged_schema and (pl.get("white_list") or pl.get("gray_list")):
                sample = (pl.get("white_list") or pl.get("gray_list"))[0]
                self.logger.info("SAMPLE peer_entry=%s", json.dumps(sample)[:300])
                self._logged_schema = True
            wa, wb, wo = self._occupation(pl.get("white_list"), attacker_ips, benign_ips)
            ga, gb, go = self._occupation(pl.get("gray_list"), attacker_ips, benign_ips)
            out.update(
                white_attacker=wa, white_benign=wb, white_other=wo, white_total=wa + wb + wo,
                gray_attacker=ga, gray_benign=gb, gray_other=go, gray_total=ga + gb + go,
                or_white=(wa / (wa + wb + wo)) if (wa + wb + wo) else 0.0,
                B_target=gb,
            )
        except (RPCError, Exception) as e:  # noqa: BLE001
            out["peerlist_err"] = str(e)[:120]
        return out

    def _benign_or(self, benign_nodes, attacker_ips, benign_ips):
        """Mean whitelist OR across a sample of benign relays (paper N-I)."""
        ors = []
        sample = benign_nodes[: self._benign_sample]
        for n in sample:
            host = n.get("ip_addr")
            port = n.get("daemon_rpc_port") or n.get("rpc_port")
            if not host or not port:
                continue
            try:
                pl = self._peer_list(self._rpc(host, port))
                wa, wb, wo = self._occupation(pl.get("white_list"), attacker_ips, benign_ips)
                tot = wa + wb + wo
                if tot:
                    ors.append(wa / tot)
            except (RPCError, Exception):  # noqa: BLE001
                continue
        if not ors:
            return {"benign_or_n": 0}
        ors.sort()
        return {
            "benign_or_n": len(ors),
            "benign_or_mean": sum(ors) / len(ors),
            "benign_or_median": ors[len(ors) // 2],
            "benign_or_min": ors[0],
            "benign_or_max": ors[-1],
        }

    # ----- main loop ---------------------------------------------------------
    def run_iteration(self):
        self._iter += 1
        sim_t = time.time() - SHADOW_EPOCH
        try:
            agents = self._agents_list()
        except Exception as e:  # noqa: BLE001
            self.logger.warning("registry load failed: %s", e)
            return self._poll_interval

        attacker_ips, benign_ips = set(), set()
        targets, benign_nodes = [], []
        for ag in agents:
            role = self._role_of(ag)
            ip = ag.get("ip_addr")
            if role in ("attacker", "injector") and ip:
                attacker_ips.add(ip)
            elif role == "benign" and ip:
                benign_ips.add(ip)
                benign_nodes.append(ag)
            elif role == "target":
                targets.append(ag)

        rec = {
            "iter": self._iter, "sim_t": round(sim_t, 1),
            "n_attacker": len(attacker_ips), "n_benign": len(benign_ips),
            "n_target": len(targets), "targets": [],
        }
        rec.update(self._benign_or(benign_nodes, attacker_ips, benign_ips))

        for tg in targets:
            host = tg.get("ip_addr")
            port = tg.get("daemon_rpc_port") or tg.get("rpc_port")
            if not host or not port:
                continue
            tm = self._target_metrics(host, port, attacker_ips, benign_ips)
            tm["id"] = tg.get("id")
            # Time-To-Eclipse: first time the full 12-slot outbound is all attacker
            if tm.get("n_out", 0) >= 12 and tm.get("out_attacker", 0) == tm.get("n_out", 0) \
                    and tm.get("out_benign", 0) == 0 and tm.get("out_other", 0) == 0:
                self._tte.setdefault(tm["id"], sim_t)
            tm["tte_sim_t"] = self._tte.get(tm["id"])
            rec["targets"].append(tm)

        # persist + log compact summary
        try:
            with open(self._metrics_path, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
        except Exception as e:  # noqa: BLE001
            self.logger.warning("metrics write failed: %s", e)

        if rec["targets"]:
            t0 = rec["targets"][0]
            self.logger.info(
                "t=%.0fs benignOR(med)=%.3f | target %s: CTR=%d/%d (atk/out) benign_out=%d other=%d "
                "| white a/b/o=%d/%d/%d gray a/b/o=%d/%d/%d B=%s TTE=%s",
                sim_t, rec.get("benign_or_median", 0.0),
                t0.get("id"), t0.get("out_attacker", 0), t0.get("n_out", 0),
                t0.get("out_benign", 0), t0.get("out_other", 0),
                t0.get("white_attacker", 0), t0.get("white_benign", 0), t0.get("white_other", 0),
                t0.get("gray_attacker", 0), t0.get("gray_benign", 0), t0.get("gray_other", 0),
                t0.get("B_target"), t0.get("tte_sim_t"),
            )
        else:
            self.logger.info("t=%.0fs no target nodes discovered yet (agents=%d)", sim_t, len(agents))
        return self._poll_interval


def main():
    parser = BaseAgent.create_argument_parser("Eclipse-attack measurement monitor")
    # monerosim passes each YAML attribute as --<key> <value> with underscores
    # preserved (e.g. --poll_interval 30). Accept those spellings; tolerate any
    # other attributes the orchestrator forwards via parse_known_args().
    parser.add_argument("--poll_interval", "--poll-interval", dest="poll_interval",
                        type=int, default=30, help="seconds between polls")
    parser.add_argument("--benign_sample", "--benign-sample", dest="benign_sample",
                        type=int, default=12, help="benign relays sampled for OR")
    args, _unknown = parser.parse_known_args()
    agent = EclipseMonitorAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes,
        poll_interval=args.poll_interval,
        benign_sample=args.benign_sample,
    )
    agent.run()


if __name__ == "__main__":
    main()
