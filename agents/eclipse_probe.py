#!/usr/bin/env python3
"""Sidecar RAW-DATA dumper for the eclipse reproduction.

Co-located with a monerod daemon (like the miners' autonomous_miner), this
script queries its OWN LOCAL daemon and appends the RAW get_connections /
get_info / get_peer_list responses -- each tagged with sim-time -- to shared
storage. It computes NO metrics during the run: raw data is king, so ANY metric
(CTR, benign graylist B, occupation OR, whitelist saturation, per-IP churn,
update_sync_search replacement events, ...) can be derived POST-HOC from the same
capture without ever re-running the (multi-day) simulation.

Why local RPC + shared FS (not the remote monitor's RPC): in Shadow the daemon
binds RPC on the host's own IP and a co-located script reaches it INTRA-HOST, so
the ~1 MB get_peer_list response never crosses a modeled inter-host WAN link
(which timed out the remote monitor at 2,200-host scale). The output path is in
shared_dir -- the real filesystem shared by every host -- so writing it uses no
simulated network either. BaseAgent already builds self.daemon_rpc from
--rpc-host <host_ip> --daemon-rpc-port <port> exactly as autonomous_miner uses.
"""
import gzip
import json
import time
from pathlib import Path

from agents.base_agent import BaseAgent, SHADOW_EPOCH


class EclipseProbeAgent(BaseAgent):
    def __init__(self, interval=45, **kwargs):
        super().__init__(**kwargs)
        self._interval = interval
        self._fh = None
        self._iter = 0
        self._role = "?"
        self._peerlist_url = None

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
        if "interval" in a:
            try:
                self._interval = int(a["interval"])
            except (TypeError, ValueError):
                pass
        self._role = a.get("eclipse_role", "?")
        base = self.shared_dir if self.shared_dir else Path(".")
        raw_dir = Path(base) / "raw_probe"
        try:
            raw_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._path = raw_dir / ("raw_%s.jsonl.gz" % (self.agent_id or "node"))
        # gzip append: one continuous stream, flushed once per cycle so a kill
        # loses at most the last cycle. Highly repetitive peerlists compress ~15x.
        self._fh = gzip.open(self._path, "at")
        if self.daemon_rpc:
            self._peerlist_url = self.daemon_rpc.url.replace("/json_rpc", "/get_peer_list")
        self.logger.info("EclipseProbe up: role=%s interval=%ss -> %s",
                         self._role, self._interval, self._path)

    def _dump(self, kind, obj, sim_t):
        try:
            self._fh.write(json.dumps({
                "sim_t": round(sim_t, 1), "id": self.agent_id,
                "role": self._role, "kind": kind, "data": obj}) + "\n")
        except Exception as e:  # noqa: BLE001
            self.logger.warning("dump %s failed: %s", kind, e)

    def run_iteration(self):
        self._iter += 1
        sim_t = time.time() - SHADOW_EPOCH
        if not self.daemon_rpc:
            return self._interval
        # get_connections (CTR source) + get_info (peerlist sizes): tiny, local.
        try:
            self._dump("connections", self.daemon_rpc._make_request("get_connections"), sim_t)
        except Exception as e:  # noqa: BLE001
            self._dump("connections_err", str(e)[:200], sim_t)
        try:
            self._dump("info", self.daemon_rpc._make_request("get_info"), sim_t)
        except Exception as e:  # noqa: BLE001
            self._dump("info_err", str(e)[:200], sim_t)
        # get_peer_list: the ~1 MB white+gray dump. Direct endpoint (not /json_rpc).
        # Local RPC so it stays fast; generous timeout as a safety margin.
        if self._peerlist_url:
            try:
                r = self.daemon_rpc.session.post(
                    self._peerlist_url, json={}, timeout=120,
                    headers={"Content-Type": "application/json"})
                r.raise_for_status()
                self._dump("peer_list", r.json(), sim_t)
            except Exception as e:  # noqa: BLE001
                self._dump("peer_list_err", str(e)[:200], sim_t)
        try:
            self._fh.flush()
        except Exception:  # noqa: BLE001
            pass
        return self._interval


def main():
    parser = BaseAgent.create_argument_parser("Eclipse raw-data probe (sidecar)")
    parser.add_argument("--interval", dest="interval", type=int, default=45,
                        help="seconds between raw dumps")
    args, _unknown = parser.parse_known_args()
    agent = EclipseProbeAgent(
        agent_id=args.id, shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port, wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port, rpc_host=args.rpc_host, log_level=args.log_level,
        attributes=args.attributes, interval=args.interval,
    )
    agent.run()


if __name__ == "__main__":
    main()
