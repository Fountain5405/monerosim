#!/usr/bin/env python3
"""Fast standalone validation of the Levin injector against a REAL monerod
(no Shadow). Launches monerod (regtest/fakechain) with an exclusive-node
pointing at our injector, then checks that injected records appear in monerod's
graylist. Run from the worktree root with ./venv/bin/python.
"""
import os
import subprocess
import sys
import threading
import time

WORKTREE = "/home/lever65/monerosim_work/monerosim/.claude/worktrees/v0.3.1"
sys.path.insert(0, WORKTREE)
from agents import levin_lib as L  # noqa: E402
from agents import eclipse_injector as EI  # noqa: E402

MONEROD = "/home/lever65/.monerosim/bin/monerod-sim"
SCRATCH = "/tmp/claude-1006/-home-lever65-monerosim-work-monerosim/e9d9c24f-f881-46d0-9095-c61aabf017f3/scratchpad/inj_test"
P2P, RPC, INJ = 48080, 48081, 49080
INJECT = [("181.0.0.10", 18080), ("105.0.0.10", 18080), ("121.0.0.10", 18080),
          ("7.0.0.10", 18080), ("31.0.0.10", 18080), ("36.0.0.10", 18080)]
INJECT_IPS = {ip for ip, _ in INJECT}


def rpc_get_info():
    import requests
    r = requests.post("http://127.0.0.1:%d/json_rpc" % RPC,
                      json={"jsonrpc": "2.0", "id": "0", "method": "get_info"}, timeout=5)
    return r.json().get("result", {})


def rpc_peer_list():
    import requests
    r = requests.post("http://127.0.0.1:%d/get_peer_list" % RPC, json={}, timeout=5)
    return r.json()


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    # start injector
    cfg = EI.InjectorConfig(network_id=L.NETWORK_ID_MAINNET, peer_id=0xDEADBEEFCAFE,
                            my_port=INJ, records_fn=lambda: list(INJECT))
    stop = threading.Event()
    threading.Thread(target=EI.serve_forever, args=("127.0.0.1", INJ, cfg, stop), daemon=True).start()
    time.sleep(0.5)

    args = [MONEROD, "--regtest", "--keep-fakechain",
            "--data-dir=%s" % SCRATCH, "--log-file=%s/monerod.log" % SCRATCH,
            "--p2p-bind-ip=127.0.0.1", "--p2p-bind-port=%d" % P2P,
            "--rpc-bind-ip=127.0.0.1", "--rpc-bind-port=%d" % RPC,
            "--confirm-external-bind", "--rpc-access-control-origins=*",
            "--allow-local-ip", "--no-igd", "--hide-my-port", "--no-zmq",
            "--disable-dns-checkpoints", "--non-interactive", "--log-level=1",
            "--add-exclusive-node=127.0.0.1:%d" % INJ, "--out-peers=8"]
    print("launching monerod:", " ".join(args[1:]))
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # wait for RPC
        for _ in range(60):
            try:
                info = rpc_get_info()
                if info:
                    print("monerod up: height=%s" % info.get("height"))
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("FAIL: monerod RPC never came up")
            return 2
        # poll peer list for injected records
        found = set()
        for i in range(90):
            try:
                pl = rpc_peer_list()
                gray = pl.get("gray_list", []) or []
                white = pl.get("white_list", []) or []
                for e in gray + white:
                    ip = e.get("host") or e.get("ip")
                    if isinstance(ip, int):
                        ip = ".".join(str((ip >> (8 * k)) & 0xFF) for k in range(4))
                    if ip in INJECT_IPS:
                        found.add(ip)
                if i % 5 == 0:
                    print("t=%2ds gray=%d white=%d injected_found=%d cfg.injected=%d conns=%d"
                          % (i, len(gray), len(white), len(found), cfg.injected, cfg.conns))
                if len(found) >= 3:
                    break
            except Exception as e:
                print("peer_list err:", e)
            time.sleep(1)
        print("\nRESULT: injected records found in monerod peerlist: %d/%d %s"
              % (len(found), len(INJECT_IPS), sorted(found)))
        print("injector: connections=%d records_injected=%d" % (cfg.conns, cfg.injected))
        if found:
            print("PASS: monerod ingested attacker-injected peer records via Levin.")
            return 0
        print("FAIL: no injected records ingested. monerod.log tail:")
        try:
            for l in open("%s/monerod.log" % SCRATCH, errors="replace").read().splitlines()[-40:]:
                print("  ", l[:200])
        except OSError:
            pass
        return 1
    finally:
        stop.set()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
