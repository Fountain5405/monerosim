#!/usr/bin/env python3
"""Sidecar RAW-DATA dumper for the eclipse reproduction.

Co-located with a monerod daemon (like the miners' autonomous_miner), this
script queries its OWN LOCAL daemon and appends the RAW get_connections /
get_info / get_peer_list responses -- each tagged with sim-time -- to shared
storage. It computes NO metrics during the run: raw data is king, so ANY metric
(CTR, benign graylist B, occupation OR, whitelist saturation, per-IP churn,
update_sync_search replacement events, ...) can be derived POST-HOC from the same
capture without re-running the (multi-day) simulation.

Why local RPC + shared FS (not the remote monitor's RPC): in Shadow the daemon
binds RPC on the host's own IP and a co-located script reaches it without an
inter-host WAN hop (the miners mine via the same self.daemon_rpc). The output
path is in shared_dir -- the real filesystem shared by every host -- so writing
it uses no simulated network either.

Two decoupled cadences (this matters): the full get_peer_list is a ~1 MB response
and monerod's RPC thread can be starved by heavy P2P load, so a single call may
block for many seconds. It therefore runs in its OWN background thread with its
OWN RPC session, so it never stalls the cheap, frequent get_connections /
get_info capture in the main loop.
"""
import gzip
import json
import threading
import time
from pathlib import Path

from agents.base_agent import BaseAgent, SHADOW_EPOCH
from agents.monero_rpc import MoneroRPC


class EclipseProbeAgent(BaseAgent):
    def __init__(self, interval=30, peerlist_interval=60, peerlist_timeout=600, **kwargs):
        super().__init__(**kwargs)
        self._interval = interval
        self._peerlist_interval = peerlist_interval
        self._peerlist_timeout = peerlist_timeout
        self._fh = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._role = "?"
        self._peerlist_url = None
        self._pl_rpc = None

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
        for key, attr in (("interval", "_interval"),
                          ("peerlist_interval", "_peerlist_interval"),
                          ("peerlist_timeout", "_peerlist_timeout")):
            if key in a:
                try:
                    setattr(self, attr, int(a[key]))
                except (TypeError, ValueError):
                    pass
        self._role = a.get("eclipse_role", "?")
        raw_dir = Path(self.shared_dir if self.shared_dir else ".") / "raw_probe"
        try:
            raw_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._path = raw_dir / ("raw_%s.jsonl.gz" % (self.agent_id or "node"))
        self._fh = gzip.open(self._path, "at")  # gzip append, one stream, flushed per write
        if self.daemon_rpc:
            self._peerlist_url = self.daemon_rpc.url.replace("/json_rpc", "/get_peer_list")
            # SEPARATE session for the peer_list thread (requests.Session is not
            # safe for concurrent use with the main loop's get_connections/info).
            self._pl_rpc = MoneroRPC(self.rpc_host, self.daemon_rpc_port,
                                     timeout=self._peerlist_timeout)
            threading.Thread(target=self._peerlist_loop, daemon=True).start()
        self.logger.info("EclipseProbe up: role=%s interval=%ss peerlist=%ss(to=%ss) -> %s",
                         self._role, self._interval, self._peerlist_interval,
                         self._peerlist_timeout, self._path)

    def _dump(self, kind, obj, sim_t):
        try:
            line = json.dumps({"sim_t": round(sim_t, 1), "id": self.agent_id,
                               "role": self._role, "kind": kind, "data": obj}) + "\n"
            with self._lock:
                self._fh.write(line)
                self._fh.flush()
        except Exception as e:  # noqa: BLE001
            self.logger.warning("dump %s failed: %s", kind, e)

    def _peerlist_loop(self):
        """Background: the big ~1 MB get_peer_list, own session + generous timeout,
        so a slow/starved RPC never blocks the main connections/info capture."""
        url = self.daemon_rpc.url.replace("/json_rpc", "/get_peer_list")
        while not self._stop.is_set():
            sim_t = time.time() - SHADOW_EPOCH
            try:
                r = self._pl_rpc.session.post(
                    url, json={}, timeout=self._peerlist_timeout,
                    headers={"Content-Type": "application/json"})
                r.raise_for_status()
                self._dump("peer_list", r.json(), sim_t)
            except Exception as e:  # noqa: BLE001
                self._dump("peer_list_err", str(e)[:200], sim_t)
            self._stop.wait(self._peerlist_interval)

    def run_iteration(self):
        sim_t = time.time() - SHADOW_EPOCH
        if not self.daemon_rpc:
            return self._interval
        try:
            self._dump("connections", self.daemon_rpc._make_request("get_connections"), sim_t)
        except Exception as e:  # noqa: BLE001
            self._dump("connections_err", str(e)[:200], sim_t)
        try:
            self._dump("info", self.daemon_rpc._make_request("get_info"), sim_t)
        except Exception as e:  # noqa: BLE001
            self._dump("info_err", str(e)[:200], sim_t)
        return self._interval


def main():
    parser = BaseAgent.create_argument_parser("Eclipse raw-data probe (sidecar)")
    parser.add_argument("--interval", dest="interval", type=int, default=30,
                        help="seconds between connections/info dumps")
    parser.add_argument("--peerlist_interval", "--peerlist-interval", dest="peerlist_interval",
                        type=int, default=60, help="seconds between full get_peer_list dumps")
    parser.add_argument("--peerlist_timeout", "--peerlist-timeout", dest="peerlist_timeout",
                        type=int, default=600, help="timeout (s) for the large get_peer_list")
    args, _unknown = parser.parse_known_args()
    agent = EclipseProbeAgent(
        agent_id=args.id, shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port, wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port, rpc_host=args.rpc_host, log_level=args.log_level,
        attributes=args.attributes, interval=args.interval,
        peerlist_interval=args.peerlist_interval, peerlist_timeout=args.peerlist_timeout,
    )
    agent.run()


if __name__ == "__main__":
    main()
