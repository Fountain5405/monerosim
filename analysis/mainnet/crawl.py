#!/usr/bin/env python3
"""BFS crawl of the live Monero P2P network via raw Levin handshakes.

Seeds from a controlled node's white+gray peer lists (RPC) plus live DNS
resolution of the mainnet fallback seed hostnames. For every unique
``ip:port`` reached, sends exactly ONE COMMAND_HANDSHAKE (honest sync data
copied from the seed RPC's current height/top hash, so we look like a normal
peer) followed by one COMMAND_PING, and records reachability, RTT, the
handshake peer_id, top height, support-flags presence, and the peer's
advertised peerlist. Peers found in a response are added to the frontier.

Politeness: one probe per ip:port for the whole crawl (a `visited` set is
updated before submission, not after), concurrency capped at 64, one
connect+read timeout, no retries.

Output (in --out):
  nodes.jsonl        one line per probed ip:port
  edges.jsonl.gz     one line per (src, dst) peerlist-adjacency edge
  crawl_summary.json counts, duration, failure classes

Usage:
    python3 crawl.py --seed-rpc http://127.0.0.1:12345 --out DIR \\
        --max-nodes 2000 --concurrency 48 --timeout 8
"""
import argparse
import gzip
import json
import random
import socket
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents import levin_lib as L  # noqa: E402

DEFAULT_P2P_PORT = 18080
DNS_SEED_HOSTS = [
    "seeds.moneroseeds.se",
    "seeds.moneroseeds.ae.org",
    "seeds.moneroseeds.ch",
    "seeds.moneroseeds.li",
]


# ---- RPC helpers (seed only, to bootstrap the frontier and sync data) -----
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


def normalize_ip(ip):
    """monerod's get_peer_list occasionally reports an IPv4 host as an
    IPv6-mapped literal ('::ffff:1.2.3.4'); strip the prefix so it round-trips
    through the IPv4-only Levin codec (network_address_ipv4)."""
    if ip.startswith("::ffff:") and ip.count(".") == 3:
        return ip[len("::ffff:"):]
    return ip


def seed_peers(seed_rpc, timeout=10):
    """(ip, port) pairs from the seed node's white+gray peer lists."""
    out = set()
    try:
        res = rpc_plain(seed_rpc, "/get_peer_list", timeout=timeout)
    except Exception:  # noqa: BLE001
        return out
    for key in ("white_list", "gray_list"):
        for e in res.get(key, []) or []:
            ip = e.get("host") or e.get("ip")
            port = e.get("port") or DEFAULT_P2P_PORT
            if ip:
                out.add((normalize_ip(str(ip)), int(port)))
    return out


def resolve_dns_seeds(hosts=DNS_SEED_HOSTS):
    """(ip, port=18080) pairs from live DNS resolution of the mainnet
    fallback seed hostnames. Best-effort: a hostname that fails to resolve
    is skipped."""
    out = set()
    for host in hosts:
        try:
            infos = socket.getaddrinfo(host, None, family=socket.AF_INET)
        except OSError:
            continue
        for info in infos:
            out.add((info[4][0], DEFAULT_P2P_PORT))
    return out


# ---- probing ---------------------------------------------------------------
def classify_exception(exc):
    if isinstance(exc, socket.timeout):
        return "timeout"
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, OSError):
        return "unreachable"
    return "protocol"


def new_node_record(ip, port):
    return {
        "ip": ip,
        "port": port,
        "ts": time.time(),
        "reachable": False,
        "rtt": None,
        "peer_id": None,
        "top_height": None,
        "top_id": None,
        "support_flags": {"present": False, "value": None},
        "peerlist_size": None,
        "peerlist": [],
        "ping_peer_id": None,
        "peer_id_mismatch": None,
        "error_class": None,
    }


def probe_peer(ip, port, network_id, my_peer_id, height, cumdiff,
               cumdiff_top64, top_id, top_version=1, timeout=8):
    """One handshake + one ping against ip:port. Never raises.

    `top_version` must be the CURRENT hard-fork version for the claimed
    `height` (see `crawl()`: fetched via the seed's `hard_fork_info`).
    monerod's `process_payload_sync_data` rejects (drops the connection and
    returns a blank, all-default handshake response instead of real data --
    counted here as reachable but a protocol-level non-answer) any peer
    claiming a post-v6 height with a stale/default top_version, exactly the
    'genesis trick' fingerprint described in the literature -- so getting
    this wrong makes every live mainnet node look like a decoy."""
    rec = new_node_record(ip, port)
    t0 = time.monotonic()
    try:
        sock = L.connect(ip, port, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        rec["error_class"] = classify_exception(exc)
        return rec

    try:
        hs_peer_id = None
        try:
            req = L.handshake_request(network_id, 0, my_peer_id, height, cumdiff,
                                      top_id, top_version=top_version,
                                      cumdiff_top64=cumdiff_top64)
            resp = L.request_response(sock, L.COMMAND_HANDSHAKE, req)
            rec["rtt"] = time.monotonic() - t0
            node_data = resp.get("node_data") or {}
            payload_data = resp.get("payload_data") or {}
            hs_peer_id = node_data.get("peer_id")
            rec["peer_id"] = "%016x" % hs_peer_id if hs_peer_id is not None else None
            rec["top_height"] = payload_data.get("current_height")
            top_id_b = payload_data.get("top_id")
            rec["top_id"] = top_id_b.hex() if isinstance(top_id_b, (bytes, bytearray)) else None
            rec["support_flags"] = {
                "present": "support_flags" in node_data,
                "value": node_data.get("support_flags"),
            }
            peerlist = L.parse_peerlist(resp.get("local_peerlist_new"))
            rec["peerlist_size"] = len(peerlist)
            rec["peerlist"] = ["%s:%d" % (p["ip"], p["port"]) for p in peerlist]
            # Reachable = TCP ok + handshake ok (spec). Some real nodes close
            # the connection right after handshaking an unreachable
            # (my_port=0) peer, before a follow-up PING gets a reply -- that
            # must not undo a successful handshake.
            rec["reachable"] = True
        except Exception as exc:  # noqa: BLE001
            rec["error_class"] = classify_exception(exc)
            return rec

        try:
            ping_resp = L.request_response(sock, L.COMMAND_PING, L.ping_request())
            ping_peer_id = ping_resp.get("peer_id")
            rec["ping_peer_id"] = "%016x" % ping_peer_id if ping_peer_id is not None else None
            if hs_peer_id is not None and ping_peer_id is not None:
                rec["peer_id_mismatch"] = hs_peer_id != ping_peer_id
        except Exception:  # noqa: BLE001
            pass  # ping is a best-effort fingerprint; its failure doesn't affect reachability
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return rec


def _peerlist_targets(rec):
    for entry in rec.get("peerlist") or []:
        ip, _, port = entry.rpartition(":")
        if ip:
            yield ip, int(port)


def crawl(seed_rpc, out_dir, max_nodes=2000, concurrency=48, timeout=8,
         dns_hosts=DNS_SEED_HOSTS, progress_interval=30):
    concurrency = max(1, min(64, concurrency))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    info = rpc_json(seed_rpc, "get_info", timeout=timeout)
    network_id = L.NETWORK_ID_MAINNET
    my_peer_id = random.getrandbits(64)
    height = info.get("height", 1)
    cumdiff = info.get("cumulative_difficulty", 1)
    cumdiff_top64 = info.get("cumulative_difficulty_top64", 0)
    top_hash_hex = info.get("top_block_hash") or ("00" * 32)
    top_id = bytes.fromhex(top_hash_hex)
    try:
        top_version = rpc_json(seed_rpc, "hard_fork_info", timeout=timeout).get("version", 1)
    except Exception:  # noqa: BLE001
        top_version = 1

    frontier = seed_peers(seed_rpc, timeout=timeout) | resolve_dns_seeds(dns_hosts)
    visited = set()
    error_classes = {}
    reachable_count = 0

    start = time.monotonic()
    last_progress = start
    nodes_path = out_dir / "nodes.jsonl"
    edges_path = out_dir / "edges.jsonl.gz"
    with open(nodes_path, "w") as nodes_f, gzip.open(edges_path, "wt") as edges_f, \
            ThreadPoolExecutor(max_workers=concurrency) as pool:
        while frontier and len(visited) < max_nodes:
            batch = []
            for ip, port in frontier:
                if (ip, port) in visited:
                    continue
                if len(visited) >= max_nodes:
                    break
                visited.add((ip, port))
                batch.append((ip, port))
            frontier = set()
            if not batch:
                break
            futures = {
                pool.submit(probe_peer, ip, port, network_id, my_peer_id,
                           height, cumdiff, cumdiff_top64, top_id, top_version, timeout): (ip, port)
                for ip, port in batch
            }
            for fut in as_completed(futures):
                rec = fut.result()
                nodes_f.write(json.dumps(rec) + "\n")
                if rec["reachable"]:
                    reachable_count += 1
                else:
                    ec = rec["error_class"] or "unknown"
                    error_classes[ec] = error_classes.get(ec, 0) + 1
                src = "%s:%d" % (rec["ip"], rec["port"])
                for ip, port in _peerlist_targets(rec):
                    edges_f.write(json.dumps({"src": src, "dst": "%s:%d" % (ip, port)}) + "\n")
                    if (ip, port) not in visited and len(visited) < max_nodes:
                        frontier.add((ip, port))
                now = time.monotonic()
                if now - last_progress >= progress_interval:
                    print("[crawl] visited=%d reachable=%d elapsed=%.0fs" %
                         (len(visited), reachable_count, now - start), flush=True)
                    last_progress = now

    duration = time.monotonic() - start
    summary = {
        "seed_rpc": seed_rpc,
        "duration_s": duration,
        "total_probed": len(visited),
        "reachable": reachable_count,
        "unreachable": len(visited) - reachable_count,
        "error_classes": error_classes,
        "max_nodes": max_nodes,
        "concurrency": concurrency,
    }
    with open(out_dir / "crawl_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("[crawl] done: %s" % json.dumps(summary))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed-rpc", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-nodes", type=int, default=2000)
    p.add_argument("--concurrency", type=int, default=48)
    p.add_argument("--timeout", type=float, default=8)
    args = p.parse_args()
    crawl(args.seed_rpc, args.out, max_nodes=args.max_nodes,
         concurrency=args.concurrency, timeout=args.timeout)


if __name__ == "__main__":
    main()
