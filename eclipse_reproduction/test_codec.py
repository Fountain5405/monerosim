#!/usr/bin/env python3
import struct
import sys
sys.path.insert(0, "/home/lever65/monerosim_work/monerosim/.claude/worktrees/v0.3.1")
from agents import levin_lib as L

sec = {
    "node_data": L.basic_node_data(L.NETWORK_ID_MAINNET, 18080, 0xDEADBEEF),
    "payload_data": L.core_sync_data(1, 1, b"\x00" * 32, 1),
    "local_peerlist_new": ("arr_obj", [
        L.peerlist_entry("181.0.0.10", 18080, peer_id=5, last_seen=123),
        L.peerlist_entry("105.0.0.10", 18081),
    ]),
}
blob = L.serialize(sec)
print("serialized %d bytes" % len(blob))
d = L.parse(blob)
print("top keys:", sorted(d.keys()))
nd = d["node_data"]
print("network_id len:", len(nd["network_id"]), "==16:", len(nd["network_id"]) == 16)
print("my_port:", nd["my_port"], "peer_id:", hex(nd["peer_id"]))
pl = d["local_peerlist_new"]
print("peerlist count:", len(pl))
e0 = pl[0]
mip = e0["adr"]["addr"]["m_ip"]
ip = ".".join(str((mip >> (8 * k)) & 0xFF) for k in range(4))
print("entry0 ip decoded:", ip, "==181.0.0.10:", ip == "181.0.0.10", "port:", e0["adr"]["addr"]["m_port"])
hdr = L.pack_header(L.COMMAND_HANDSHAKE, len(blob), L.LEVIN_PACKET_RESPONSE, return_code=1, expect_response=False)
sig, cb, hr, cmd, rcode, flags, ver = struct.unpack("<QQBiiII", hdr)
print("header len:", len(hdr), "sig_ok:", sig == L.LEVIN_SIGNATURE, "cmd:", cmd, "flags:", flags, "ver:", ver, "cb:", cb)
ok = (len(nd["network_id"]) == 16 and nd["my_port"] == 18080 and len(pl) == 2
      and ip == "181.0.0.10" and len(hdr) == 33 and sig == L.LEVIN_SIGNATURE)
print("ALL_OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
