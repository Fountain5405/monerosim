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


class SelfishBridgeAgent(BaseAgent):
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        victims_attr = self.attributes.get("victims") or ""
        self.victim_agent_ids = [v.strip() for v in victims_attr.split(",") if v.strip()]
        self.victim_rpcs = []
        self._victim_connected = set()
        self._pushed_index = 0        # highest island-main height pushed to victims
        self._pulled_index = []       # per-victim highest main-chain height pulled back

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

    def _relay_tick(self) -> None:
        """One bidirectional island<->victims relay pass, parent-first in
        both directions. RPC rejections are debug-logged: shorter branches
        land as alts and monerod keeps whichever main chain is longer."""
        self._connect_victims()
        if not self.victim_rpcs:
            return
        while len(self._pulled_index) < len(self.victim_rpcs):
            self._pulled_index.append(0)
        try:
            island_height = int(self.daemon_rpc.get_info().get("height", 0))
        except RPCError as e:
            self.logger.debug(f"island height read: {e}")
            return
        if island_height < self._pushed_index:
            self._pushed_index = 0        # island reorg: re-push from genesis
        pushed = 0
        for idx in range(self._pushed_index + 1, island_height + 1):
            try:
                blob = self.daemon_rpc.get_block(height=idx).get("blob")
            except RPCError as e:
                self.logger.debug(f"relay push {idx}: {e}")
                break
            if blob:
                for rpc in self.victim_rpcs:
                    try:
                        rpc.submit_block(blob)
                        pushed += 1
                    except RPCError as e:
                        self.logger.debug(f"relay push {idx} to victim: {e}")
            self._pushed_index = idx
        pulled = 0
        for i, rpc in enumerate(self.victim_rpcs):
            try:
                victim_height = int(rpc.get_info().get("height", 0))
            except RPCError as e:
                self.logger.debug(f"victim {i} height read: {e}")
                continue
            if victim_height < self._pulled_index[i]:
                self._pulled_index[i] = 0    # victim reorg: re-pull
            for idx in range(self._pulled_index[i] + 1, victim_height + 1):
                try:
                    blob = rpc.get_block(height=idx).get("blob")
                except RPCError as e:
                    self.logger.debug(f"relay pull {idx}: {e}")
                    break
                if blob:
                    try:
                        self.daemon_rpc.submit_block(blob)
                        pulled += 1
                    except RPCError as e:
                        self.logger.debug(f"relay pull {idx} into island: {e}")
                self._pulled_index[i] = idx
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
