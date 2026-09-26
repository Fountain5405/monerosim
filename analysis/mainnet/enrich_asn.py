#!/usr/bin/env python3
"""Bulk ASN/country lookup of a crawl's IPs via the Team Cymru whois bulk
interface (whois.cymru.com:43), chunked at <=2000 IPs per query and cached
on disk so re-runs don't re-query already-known IPs.

Usage:
    python3 enrich_asn.py --in nodes.jsonl --out asn.jsonl [--cache PATH]
"""
import argparse
import json
import socket
from pathlib import Path

CYMRU_HOST = "whois.cymru.com"
CYMRU_PORT = 43
CHUNK_SIZE = 2000


def unique_ips(nodes_path):
    """IPs from a nodes.jsonl file, in first-seen order."""
    seen = []
    seen_set = set()
    with open(nodes_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            ip = rec.get("ip")
            if ip and ip not in seen_set:
                seen_set.add(ip)
                seen.append(ip)
    return seen


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def parse_cymru_response(text):
    """Team Cymru bulk 'verbose' response -> {ip: {ip, asn, as_name, cc, prefix}}.

    Line format: 'AS | IP | BGP Prefix | CC | Registry | Allocated | AS Name'
    The first line is the header and is skipped.
    """
    out = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 7:
            continue
        asn, ip, prefix, cc, _registry, _allocated, as_name = parts[:7]
        if asn == "AS" or ip == "IP":  # header row
            continue
        out[ip] = {"ip": ip, "asn": asn, "as_name": as_name, "cc": cc, "prefix": prefix}
    return out


def raw_cymru_query(ips, timeout=15):
    """Send one bulk-mode query over TCP and return the raw response text."""
    req = "begin\nverbose\n" + "\n".join(ips) + "\nend\n"
    sock = socket.create_connection((CYMRU_HOST, CYMRU_PORT), timeout=timeout)
    sock.settimeout(timeout)
    try:
        sock.sendall(req.encode())
        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks).decode(errors="replace")
    finally:
        sock.close()


def bulk_lookup(ips, timeout=15, query_fn=raw_cymru_query):
    result = {}
    for chunk in chunked(list(ips), CHUNK_SIZE):
        text = query_fn(chunk, timeout=timeout)
        result.update(parse_cymru_response(text))
    return result


def load_cache(path):
    path = Path(path)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_cache(path, cache):
    with open(path, "w") as f:
        json.dump(cache, f)


def enrich(nodes_path, out_path, cache_path=None, timeout=15, query_fn=raw_cymru_query):
    out_path = Path(out_path)
    cache_path = Path(cache_path) if cache_path else out_path.with_name(".asn_cache.json")
    ips = unique_ips(nodes_path)
    cache = load_cache(cache_path)
    missing = [ip for ip in ips if ip not in cache]
    if missing:
        cache.update(bulk_lookup(missing, timeout=timeout, query_fn=query_fn))
        save_cache(cache_path, cache)
    with open(out_path, "w") as f:
        for ip in ips:
            rec = cache.get(ip, {"ip": ip, "asn": None, "as_name": None, "cc": None, "prefix": None})
            f.write(json.dumps(rec) + "\n")
    return len(ips), len(missing)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="nodes_path", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cache", default=None)
    p.add_argument("--timeout", type=float, default=15)
    args = p.parse_args()
    total, looked_up = enrich(args.nodes_path, args.out, cache_path=args.cache, timeout=args.timeout)
    print("enriched %d IPs (%d newly looked up)" % (total, looked_up))


if __name__ == "__main__":
    main()
