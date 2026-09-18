"""Minimal Monero Levin + epee portable-storage codec for the eclipse
reproduction's peer-record injector.

Implements just enough of the wire format to (a) frame Levin buckets and (b)
serialize/parse the epee "portable storage" KV payloads used by COMMAND_HANDSHAKE
(1001), COMMAND_TIMED_SYNC (1002) and COMMAND_PING (1003), so a Python node can
act as a Monero P2P *responder* and hand a dialing monerod a poisoned
local_peerlist_new.

Typed values are represented explicitly as (tag, value) tuples to avoid any
type-guessing: 'u8','u16','u32','u64','i64','bool','str','blob','obj','arr_obj'.
"""
import socket
import struct

# ---- Levin bucket header -------------------------------------------------
LEVIN_SIGNATURE = 0x0101010101012101
LEVIN_PACKET_REQUEST = 1
LEVIN_PACKET_RESPONSE = 2
LEVIN_PROTOCOL_VER_1 = 1
LEVIN_DEFAULT_MAX_PACKET_SIZE = 100 * 1024 * 1024

# Monero network_id. FAKECHAIN (monerod --regtest --keep-fakechain, used by
# monerosim) returns the MAINNET config, so the P2P handshake network_id is the
# mainnet UUID (cryptonote_config.h). It MUST match exactly or monerod drops us.
NETWORK_ID_MAINNET = bytes([0x12, 0x30, 0xF1, 0x71, 0x61, 0x04, 0x41, 0x61,
                            0x17, 0x31, 0x00, 0x82, 0x16, 0xA1, 0xA1, 0x10])

P2P_COMMANDS_POOL_BASE = 1000
COMMAND_HANDSHAKE = P2P_COMMANDS_POOL_BASE + 1     # 1001
COMMAND_TIMED_SYNC = P2P_COMMANDS_POOL_BASE + 2    # 1002
COMMAND_PING = P2P_COMMANDS_POOL_BASE + 3          # 1003
COMMAND_REQUEST_SUPPORT_FLAGS = P2P_COMMANDS_POOL_BASE + 7  # 1007

PING_OK_RESPONSE_STATUS_TEXT = b"OK"

_HEADER = struct.Struct("<QQBiiII")  # signature, cb, have_to_return, command, return_code, flags, proto
HEADER_SIZE = _HEADER.size  # 33


def pack_header(command, payload_len, flags, return_code=0, expect_response=True):
    return _HEADER.pack(LEVIN_SIGNATURE, payload_len,
                        1 if expect_response else 0,
                        command, return_code, flags, LEVIN_PROTOCOL_VER_1)


def read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def read_bucket(sock):
    """Return (command, flags, return_code, expect_response, payload_bytes)."""
    hdr = read_exact(sock, HEADER_SIZE)
    sig, cb, have_ret, command, return_code, flags, proto = _HEADER.unpack(hdr)
    if sig != LEVIN_SIGNATURE:
        raise ValueError("bad Levin signature 0x%x" % sig)
    if cb > LEVIN_DEFAULT_MAX_PACKET_SIZE:
        raise ValueError("payload too large: %d" % cb)
    payload = read_exact(sock, cb) if cb else b""
    return command, flags, return_code, bool(have_ret), payload


# ---- epee portable storage ----------------------------------------------
PORTABLE_STORAGE_SIGNATUREA = 0x01011101
PORTABLE_STORAGE_SIGNATUREB = 0x01020101
PORTABLE_STORAGE_FORMAT_VER = 1

SERIALIZE_TYPE_INT64 = 1
SERIALIZE_TYPE_INT32 = 2
SERIALIZE_TYPE_INT16 = 3
SERIALIZE_TYPE_INT8 = 4
SERIALIZE_TYPE_UINT64 = 5
SERIALIZE_TYPE_UINT32 = 6
SERIALIZE_TYPE_UINT16 = 7
SERIALIZE_TYPE_UINT8 = 8
SERIALIZE_TYPE_DOUBLE = 9
SERIALIZE_TYPE_STRING = 10
SERIALIZE_TYPE_BOOL = 11
SERIALIZE_TYPE_OBJECT = 12
SERIALIZE_TYPE_ARRAY = 13
SERIALIZE_FLAG_ARRAY = 0x80

_TAG2TYPE = {
    "i64": SERIALIZE_TYPE_INT64, "i32": SERIALIZE_TYPE_INT32, "i16": SERIALIZE_TYPE_INT16,
    "i8": SERIALIZE_TYPE_INT8, "u64": SERIALIZE_TYPE_UINT64, "u32": SERIALIZE_TYPE_UINT32,
    "u16": SERIALIZE_TYPE_UINT16, "u8": SERIALIZE_TYPE_UINT8, "bool": SERIALIZE_TYPE_BOOL,
    "str": SERIALIZE_TYPE_STRING, "blob": SERIALIZE_TYPE_STRING, "obj": SERIALIZE_TYPE_OBJECT,
}
_SCALAR_STRUCT = {
    "i64": "<q", "i32": "<i", "i16": "<h", "i8": "<b",
    "u64": "<Q", "u32": "<I", "u16": "<H", "u8": "<B",
}


def pack_varint(n):
    if n <= 0x3F:
        return struct.pack("<B", (n << 2) | 0)
    if n <= 0x3FFF:
        return struct.pack("<H", (n << 2) | 1)
    if n <= 0x3FFFFFFF:
        return struct.pack("<I", (n << 2) | 2)
    return struct.pack("<Q", (n << 2) | 3)


def unpack_varint(buf, off):
    b0 = buf[off]
    mark = b0 & 0x03
    if mark == 0:
        return b0 >> 2, off + 1
    if mark == 1:
        return struct.unpack_from("<H", buf, off)[0] >> 2, off + 2
    if mark == 2:
        return struct.unpack_from("<I", buf, off)[0] >> 2, off + 4
    return struct.unpack_from("<Q", buf, off)[0] >> 2, off + 8


def _ser_scalar(tag, val):
    return struct.pack(_SCALAR_STRUCT[tag], val)


def _ser_string(val):
    if isinstance(val, str):
        val = val.encode()
    return pack_varint(len(val)) + val


def _ser_storage_entry(tag, val):
    """Serialize one value with its leading type byte (handles arrays)."""
    if tag == "arr_obj":
        out = bytes([SERIALIZE_TYPE_OBJECT | SERIALIZE_FLAG_ARRAY])
        out += pack_varint(len(val))
        for item in val:
            out += _ser_section(item)
        return out
    if tag.startswith("arr_"):  # arr_u32 etc: array of scalars
        etag = tag[4:]
        out = bytes([_TAG2TYPE[etag] | SERIALIZE_FLAG_ARRAY])
        out += pack_varint(len(val))
        for item in val:
            out += _ser_scalar(etag, item)
        return out
    t = _TAG2TYPE[tag]
    out = bytes([t])
    if tag in ("str", "blob"):
        out += _ser_string(val)
    elif tag == "bool":
        out += struct.pack("<B", 1 if val else 0)
    elif tag == "obj":
        out += _ser_section(val)
    else:
        out += _ser_scalar(tag, val)
    return out


def _ser_section(section):
    """section: dict name -> (tag, value)."""
    out = pack_varint(len(section))
    for name, (tag, val) in section.items():
        nb = name.encode()
        out += bytes([len(nb)]) + nb
        out += _ser_storage_entry(tag, val)
    return out


def serialize(section):
    """Top-level portable-storage blob."""
    hdr = struct.pack("<IIB", PORTABLE_STORAGE_SIGNATUREA,
                      PORTABLE_STORAGE_SIGNATUREB, PORTABLE_STORAGE_FORMAT_VER)
    return hdr + _ser_section(section)


# ---- minimal parser (to advance the stream / read a few fields) ----------
def _parse_storage_entry(buf, off):
    t = buf[off]; off += 1
    is_arr = bool(t & SERIALIZE_FLAG_ARRAY)
    base = t & ~SERIALIZE_FLAG_ARRAY
    if is_arr:
        count, off = unpack_varint(buf, off)
        vals = []
        for _ in range(count):
            v, off = _parse_value(base, buf, off)
            vals.append(v)
        return vals, off
    return _parse_value(base, buf, off)


def _parse_value(base, buf, off):
    if base == SERIALIZE_TYPE_OBJECT:
        return _parse_section(buf, off)
    if base == SERIALIZE_TYPE_STRING:
        ln, off = unpack_varint(buf, off)
        return buf[off:off + ln], off + ln
    if base == SERIALIZE_TYPE_BOOL:
        return bool(buf[off]), off + 1
    inv = {v: k for k, v in _SCALAR_STRUCT.items()}
    for tag, tid in _TAG2TYPE.items():
        if tid == base and tag in _SCALAR_STRUCT:
            fmt = _SCALAR_STRUCT[tag]
            v = struct.unpack_from(fmt, buf, off)[0]
            return v, off + struct.calcsize(fmt)
    raise ValueError("unknown storage type %d at %d" % (base, off))


def _parse_section(buf, off):
    n, off = unpack_varint(buf, off)
    d = {}
    for _ in range(n):
        nl = buf[off]; off += 1
        name = buf[off:off + nl].decode("latin1"); off += nl
        val, off = _parse_storage_entry(buf, off)
        d[name] = val
    return d, off


def parse(payload):
    if len(payload) < 9:
        return {}
    a, b, ver = struct.unpack_from("<IIB", payload, 0)
    if a != PORTABLE_STORAGE_SIGNATUREA or b != PORTABLE_STORAGE_SIGNATUREB:
        return {}
    d, _ = _parse_section(payload, 9)
    return d


# ---- helpers for Monero structs -----------------------------------------
def ipv4_m_ip(ip_str):
    """monerod ipv4_network_address.m_ip == inet_addr(ip): dotted octets packed
    little-endian (a | b<<8 | c<<16 | d<<24)."""
    a, b, c, d = (int(x) for x in ip_str.split("."))
    return a | (b << 8) | (c << 16) | (d << 24)


def network_address_ipv4(ip_str, port):
    # network_address is a polymorphic {type, addr:{m_ip,m_port}} object; type 1 = IPv4
    return ("obj", {
        "type": ("u8", 1),
        "addr": ("obj", {
            "m_ip": ("u32", ipv4_m_ip(ip_str)),
            "m_port": ("u16", port),
        }),
    })


def peerlist_entry(ip_str, port, peer_id=0, last_seen=0, rpc_port=0):
    return {
        "adr": network_address_ipv4(ip_str, port),
        "id": ("u64", peer_id),
        "last_seen": ("i64", last_seen),
        "pruning_seed": ("u32", 0),
        "rpc_port": ("u16", rpc_port),
        "rpc_credits_per_hash": ("u32", 0),
    }


def basic_node_data(network_id_bytes, my_port, peer_id, rpc_port=0, support_flags=1):
    return ("obj", {
        "network_id": ("blob", network_id_bytes),
        "peer_id": ("u64", peer_id),
        "my_port": ("u32", my_port),
        "rpc_port": ("u16", rpc_port),
        "rpc_credits_per_hash": ("u32", 0),
        "support_flags": ("u32", support_flags),
    })


def core_sync_data(height, cumdiff, top_id_bytes, top_version=1, cumdiff_top64=0, pruning_seed=0):
    return ("obj", {
        "current_height": ("u64", height),
        "cumulative_difficulty": ("u64", cumdiff),
        "cumulative_difficulty_top64": ("u64", cumdiff_top64),
        "top_id": ("blob", top_id_bytes),
        "top_version": ("u8", top_version),
        "pruning_seed": ("u32", pruning_seed),
    })


def connect(ip, port, timeout=20):
    s = socket.create_connection((ip, port), timeout=timeout)
    s.settimeout(timeout)
    return s
