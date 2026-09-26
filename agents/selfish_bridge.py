"""Bridge node for the selfish-mining apparatus.

A do-nothing agent whose only job is to run on the attacker's bridge daemon
host so BaseAgent.setup() registers the bridge's RPC endpoint (ip_addr,
daemon_rpc_port) in agent_registry.json. The SelfishMinerAgent looks the
bridge up there. The bridge daemon itself is a stock, fully-connected relay;
this agent issues no blockchain RPCs.

ISLAND MODE (eclipse composition, v7): with a `victims` attribute (comma
list of eclipsed victim agent ids) the agent becomes a bidirectional RPC
relay between its island daemon and the victims — push new island-main
blocks to every victim, pull each victim's new main blocks into the island.
This is necessary because monerod does NOT relay RPC-submitted blocks over
P2P and a "synchronized" node does not poll for them (measured: victim
stuck at height 1 for 4+ sim-hours while the island held 109 blocks), and
it is faithful to a real eclipse: the attacker's infrastructure IS the
victim's only source of blocks.
"""
import logging

from agents.base_agent import BaseAgent
from agents.monero_rpc import MoneroRPC, RPCError

BRIDGE_IDLE_INTERVAL_S = 60.0
ISLAND_RELAY_INTERVAL_S = 1.0


def _undelivered(e: Exception) -> bool:
    """True when an RPCError is a TRANSPORT failure (request never reached
    the daemon) rather than a daemon-side rejection. A rejected block was
    processed (already-have / alt / invalid) and need not be retried; an
    undelivered one MUST be, or the watermark skips it forever — exactly
    what happened to every block mirrored while the victim was absent."""
    return "Request failed" in str(e) or "Max retries" in str(e)


class SelfishBridgeAgent(BaseAgent):
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        victims_attr = self.attributes.get("victims") or ""
        self.victim_agent_ids = [v.strip() for v in victims_attr.split(",") if v.strip()]
        self.victim_rpcs = []
        self._victim_connected = set()
        self._pushed_index = 0        # highest island-main height pushed to victims
        self._pulled_index = []       # per-victim highest main-chain height pulled back
        # Reorg detection (review 2026-09-26): a height DECREASE was the only
        # signal, so an equal-length branch switch on either side was never
        # re-relayed. Now, as in SelfishMinerAgent._forward_public_blocks, a
        # tip-hash change rescans the last REORG_WINDOW heights against the
        # hashes relayed before and re-relays from the first changed one.
        self._pushed_hashes = {}      # island idx -> hash pushed
        self._island_tip = None
        self._pulled_hashes = []      # per-victim {idx: hash pulled}
        self._victim_tip = []         # per-victim last-seen tip hash

    def _setup_agent(self):
        # No agent-specific setup; BaseAgent.setup() -> _register_self()
        # publishing this host's RPC endpoint is the entire point of this
        # agent. Required override: BaseAgent._setup_agent is abstract.
        pass

    def _connect_victims(self) -> None:
        registry = self.read_shared_state("agent_registry.json") or {}
        by_id = {a.get("id"): a for a in registry.get("agents", [])}
        for vid in self.victim_agent_ids:
            if vid in self._victim_connected:
                continue
            entry = by_id.get(vid)
            host = entry.get("ip_addr") if entry else None
            port = entry.get("daemon_rpc_port") if entry else None
            if host and port:
                self.victim_rpcs.append(MoneroRPC(host, int(port)))
                self._victim_connected.add(vid)
                self.logger.info(f"Victim connected: {vid} at {host}:{port}")

    REORG_WINDOW = 6

    @staticmethod
    def _hash_of(blk) -> str:
        return (blk.get("block_header") or {}).get("hash")

    def _rescan_start(self, rpc, seen: dict, next_index: int, count: int, tip, last_tip, what: str) -> int:
        """Where to (re)start relaying from a source whose tip hash changed:
        the first height in the trailing window whose hash differs from the
        one relayed before (parent-first from there), else next_index."""
        start = next_index
        if tip is None or tip == last_tip or next_index == 0:
            return start
        floor = max(0, count - self.REORG_WINDOW)
        hi = min(next_index - 1, count - 1)
        for idx in range(floor, hi + 1):
            try:
                cur = self._hash_of(rpc.get_block(height=idx))
            except RPCError as e:
                self.logger.debug(f"{what} reorg rescan {idx}: {e}")
                cur = None
            if seen.get(idx) != cur:
                self.logger.info(f"{what} reorg at height {idx}; re-relaying from there")
                return idx
        return start

    def _relay_tick(self) -> None:
        """One bidirectional island<->victims relay pass, parent-first in
        both directions. RPC rejections are debug-logged: shorter branches
        land as alts and monerod keeps whichever main chain is longer."""
        self._connect_victims()
        if not self.victim_rpcs:
            return
        while len(self._pulled_index) < len(self.victim_rpcs):
            self._pulled_index.append(0)
            self._pulled_hashes.append({})
            self._victim_tip.append(None)
        try:
            island_info = self.daemon_rpc.get_info()
            island_height = int(island_info.get("height", 0))
            island_tip = island_info.get("top_block_hash")
        except RPCError as e:
            self.logger.debug(f"island height read: {e}")
            return
        if island_height < self._pushed_index:
            self._pushed_index = 0        # island reorg: re-push from genesis
        start = self._rescan_start(self.daemon_rpc, self._pushed_hashes, self._pushed_index,
                                   island_height, island_tip, self._island_tip, "island")
        pushed = 0
        # HEIGHT CONVENTION: get_info heights are COUNTS (top index + 1);
        # block indexes are 0-based. The victim at count V needs indexes V..;
        # the island at count I supplies 0..I-1. (Asking for index I — one
        # past the top — errors, and skipping an index orphans the rest.)
        for idx in range(start, island_height):
            try:
                blk = self.daemon_rpc.get_block(height=idx)
                blob = blk.get("blob")
            except RPCError as e:
                self.logger.debug(f"relay push {idx}: {e}")
                break
            if not blob:
                break                       # nothing to relay for this index yet: retry next tick
            if blob:
                undelivered = False
                for rpc in self.victim_rpcs:
                    try:
                        rpc.submit_block(blob)
                        pushed += 1
                    except RPCError as e:
                        self.logger.debug(f"relay push {idx} to victim: {e}")
                        if _undelivered(e):
                            undelivered = True
                if undelivered:
                    break                   # retry this index next tick
            h = self._hash_of(blk)
            if h:
                self._pushed_hashes[idx] = h
            self._pushed_index = max(self._pushed_index, idx + 1)
        for k in [k for k in self._pushed_hashes if k >= island_height]:
            del self._pushed_hashes[k]
        if island_tip is not None:
            self._island_tip = island_tip
        pulled = 0
        for i, rpc in enumerate(self.victim_rpcs):
            try:
                vinfo = rpc.get_info()
                victim_height = int(vinfo.get("height", 0))
                victim_tip = vinfo.get("top_block_hash")
            except RPCError as e:
                self.logger.debug(f"victim {i} height read: {e}")
                continue
            if victim_height < self._pulled_index[i]:
                self._pulled_index[i] = 0    # victim reorg: re-pull
            start = self._rescan_start(rpc, self._pulled_hashes[i], self._pulled_index[i],
                                       victim_height, victim_tip, self._victim_tip[i], f"victim {i}")
            for idx in range(start, victim_height):
                try:
                    blk = rpc.get_block(height=idx)
                    blob = blk.get("blob")
                except RPCError as e:
                    self.logger.debug(f"relay pull {idx}: {e}")
                    break
                if not blob:
                    break
                try:
                    self.daemon_rpc.submit_block(blob)
                    pulled += 1
                except RPCError as e:
                    self.logger.debug(f"relay pull {idx} into island: {e}")
                    if _undelivered(e):
                        break           # retry this index next tick
                h = self._hash_of(blk)
                if h:
                    self._pulled_hashes[i][idx] = h
                self._pulled_index[i] = max(self._pulled_index[i], idx + 1)
            for k in [k for k in self._pulled_hashes[i] if k >= victim_height]:
                del self._pulled_hashes[i][k]
            if victim_tip is not None:
                self._victim_tip[i] = victim_tip
        if pushed or pulled:
            self.logger.info(f"island relay: pushed {pushed}, pulled {pulled}")

    def run_iteration(self) -> float:
        if self.victim_agent_ids:
            try:
                self._relay_tick()
            except RPCError as e:
                self.logger.warning(f"island relay tick: {e}")
            return ISLAND_RELAY_INTERVAL_S
        # Registered in setup(); nothing to do but stay alive.
        return BRIDGE_IDLE_INTERVAL_S

    def _cleanup_agent(self):
        """Record this honest node's final main chain (height -> hash) so the
        selfish-mining analysis can attribute each canonical block to its
        finder. At gamma=0 the bridge's main chain IS the honest canonical
        chain. Best-effort: a failure here must not break shutdown."""
        try:
            height = int(self.daemon_rpc.get_info().get("height", 0))
            chain = []
            for h in range(1, height):   # skip genesis (height 0)
                try:
                    header = self.daemon_rpc.get_block_header_by_height(h)
                except RPCError as e:
                    self.logger.warning(f"canonical chain dump stopped at height {h}: {e}")
                    break
                block_hash = header.get("hash")
                if block_hash:
                    # Block timestamp (miner-declared, sim clock): lets
                    # time-based analysis bucket canonical blocks without the
                    # hash-join against miner logs, and covers blocks no
                    # logged miner found. For a withholding attacker this is
                    # the PRIVATE find time, not the public arrival time.
                    chain.append({"height": h, "hash": block_hash,
                                  "timestamp": header.get("timestamp")})
            self.write_shared_state(f"canonical_chain_{self.agent_id}.json",
                                    {"observer": self.agent_id, "chain": chain})
            self.logger.info(f"Canonical chain recorded: {len(chain)} blocks")
        except RPCError as e:
            self.logger.warning(f"canonical chain dump failed: {e}")


def main():
    parser = SelfishBridgeAgent.create_argument_parser("Selfish-mining bridge node")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    agent = SelfishBridgeAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
