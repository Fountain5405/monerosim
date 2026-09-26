#!/usr/bin/env python3
"""Poll a monerod daemon's RPC and append one JSON line per tick.

Each tick calls get_info + get_connections (json_rpc) and, every
--peerlist-interval seconds, /get_peer_list (plain). Ticks append to daily
files (`connections-YYYYMMDD.jsonl`, `peerlist-YYYYMMDD.jsonl`); on a UTC-date
rollover the previous day's files are gzipped in place. RPC errors are logged
and skipped (the tick is still recorded, with `error` set and the RPC field
null) so the poller never dies mid-week. State-free: safe to kill and
restart at any time (e.g. under `systemd-run --user`).

Usage:
    python3 poll_node.py --rpc http://127.0.0.1:12345 --out DIR \\
        --interval 60 --peerlist-interval 600 --duration 7d
"""
import argparse
import gzip
import json
import logging
import shutil
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger("poll_node")


# ---- RPC ---------------------------------------------------------------
def rpc_json(url, method, timeout=10):
    r = requests.post(url.rstrip("/") + "/json_rpc",
                      json={"jsonrpc": "2.0", "id": "0", "method": method},
                      timeout=timeout)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(body["error"])
    return body["result"]


def rpc_plain(url, path, timeout=10):
    r = requests.post(url.rstrip("/") + path, json={}, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---- pure helpers (tested without network) ------------------------------
def parse_duration(s):
    """'7d' / '12h' / '30m' / '90s' / a bare number of seconds -> float
    seconds."""
    s = str(s).strip()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if s and s[-1] in units:
        try:
            return float(s[:-1]) * units[s[-1]]
        except ValueError:
            pass
    return float(s)


def utc_date_str(ts=None):
    dt = datetime.now(timezone.utc) if ts is None else datetime.fromtimestamp(ts, timezone.utc)
    return dt.strftime("%Y%m%d")


def build_connections_tick(ts, get_info=None, connections=None, error=None):
    return {"ts": ts, "get_info": get_info, "connections": connections, "error": error}


def build_peerlist_tick(ts, white_list=None, gray_list=None, error=None):
    return {"ts": ts, "white_list": white_list, "gray_list": gray_list, "error": error}


def connection_counts(connections):
    """(in_count, out_count) from a get_connections result list."""
    inc = sum(1 for c in connections or [] if c.get("incoming"))
    out = sum(1 for c in connections or [] if not c.get("incoming"))
    return inc, out


def median_live_time(connections):
    vals = [c.get("live_time") for c in connections or [] if c.get("live_time") is not None]
    return statistics.median(vals) if vals else None


def hourly_summary_line(ticks):
    """ticks: list of get_connections results (may include None/error ticks).
    Returns a one-line summary string, or None if there is nothing to report."""
    usable = [t for t in ticks if t is not None]
    if not usable:
        return None
    last = usable[-1]
    inc, out = connection_counts(last)
    med = median_live_time(last)
    return ("ticks=%d last_in=%d last_out=%d median_live_time=%s" %
           (len(usable), inc, out, "%.0f" % med if med is not None else "n/a"))


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


def gzip_and_remove(path):
    path = Path(path)
    if not path.exists():
        return
    gz_path = path.with_name(path.name + ".gz")
    with open(path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    path.unlink()


def rollover_if_needed(out_dir, prefix, prev_date, cur_date):
    """Gzip prefix-<prev_date>.jsonl if the UTC date changed. No-op if the
    file is already gone (already rolled over) or prev_date == cur_date."""
    if prev_date is None or prev_date == cur_date:
        return
    gzip_and_remove(Path(out_dir) / ("%s-%s.jsonl" % (prefix, prev_date)))


# ---- the poll loop --------------------------------------------------------
class Poller:
    def __init__(self, rpc, out_dir, interval=60, peerlist_interval=600,
                duration=None, sleep_fn=time.sleep, now_fn=time.time):
        self.rpc = rpc
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.interval = interval
        self.peerlist_interval = peerlist_interval
        self.duration = duration
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn
        self.stop = False
        self._recent_connections = []  # for the hourly summary
        self._last_summary_ts = None
        self._last_peerlist_ts = None
        self._cur_date = None
        self._cur_peerlist_date = None

    def _write_pidfile(self):
        import os
        (self.out_dir / "poll_node.pid").write_text(str(os.getpid()))

    def tick_connections(self):
        ts = self.now_fn()
        try:
            info = rpc_json(self.rpc, "get_info")
            conns = rpc_json(self.rpc, "get_connections").get("connections")
            tick = build_connections_tick(ts, info, conns)
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_info/get_connections failed: %s", exc)
            tick = build_connections_tick(ts, error=str(exc))
        date = utc_date_str(ts)
        rollover_if_needed(self.out_dir, "connections", self._cur_date, date)
        self._cur_date = date
        append_jsonl(self.out_dir / ("connections-%s.jsonl" % date), tick)
        self._recent_connections.append(tick.get("connections"))
        self._recent_connections = self._recent_connections[-10000:]
        return tick

    def tick_peerlist(self):
        ts = self.now_fn()
        try:
            res = rpc_plain(self.rpc, "/get_peer_list")
            tick = build_peerlist_tick(ts, res.get("white_list"), res.get("gray_list"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_peer_list failed: %s", exc)
            tick = build_peerlist_tick(ts, error=str(exc))
        date = utc_date_str(ts)
        rollover_if_needed(self.out_dir, "peerlist", self._cur_peerlist_date, date)
        self._cur_peerlist_date = date
        append_jsonl(self.out_dir / ("peerlist-%s.jsonl" % date), tick)
        return tick

    def maybe_summarize(self, now):
        if self._last_summary_ts is not None and now - self._last_summary_ts < 3600:
            return
        line = hourly_summary_line(self._recent_connections)
        if line:
            logger.info(line)
        self._last_summary_ts = now
        self._recent_connections = []

    def run(self):
        self._write_pidfile()
        start = self.now_fn()
        stop_at = start + self.duration if self.duration else None
        self._last_peerlist_ts = 0
        self._last_summary_ts = start
        logger.info("poll_node starting: rpc=%s out=%s interval=%ds peerlist_interval=%ds",
                   self.rpc, self.out_dir, self.interval, self.peerlist_interval)
        while not self.stop:
            now = self.now_fn()
            if stop_at is not None and now >= stop_at:
                break
            self.tick_connections()
            if now - self._last_peerlist_ts >= self.peerlist_interval:
                self.tick_peerlist()
                self._last_peerlist_ts = now
            self.maybe_summarize(now)
            self.sleep_fn(self.interval)
        logger.info("poll_node stopping")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rpc", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--interval", type=float, default=60)
    p.add_argument("--peerlist-interval", type=float, default=600)
    p.add_argument("--duration", default=None,
                  help="e.g. 7d, 12h, 600s; omit to run until killed")
    args = p.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                 logging.FileHandler(Path(args.out) / "poll_node.log")],
    )

    duration = parse_duration(args.duration) if args.duration else None
    poller = Poller(args.rpc, args.out, interval=args.interval,
                    peerlist_interval=args.peerlist_interval, duration=duration)

    import signal

    def _handle_term(_signum, _frame):
        poller.stop = True

    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)

    poller.run()


if __name__ == "__main__":
    main()
