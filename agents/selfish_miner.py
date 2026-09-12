"""Selfish-mining attacker agent.

Runs on the attacker's OFFLINE miner daemon (native throttled RandomX). Its
own daemon (self.daemon_rpc) withholds by construction because it has no P2P.
A separate, normally-connected bridge daemon (discovered from
agent_registry.json by the `bridge_agent` attribute) is the read/write path to
the honest network. Each tick this agent forwards new honest blocks into the
offline miner and releases private blocks to the bridge per the SelfishStrategy
decision. See docs/SELFISH_MINING.md.

Attributes (via --attributes KEY VALUE):
    strategy            "honest" | "eyal_sirer"  (default "honest")
    bridge_agent        agent id of the bridge node (required)
    attack_start_height block count at which withholding begins (default 0)
    reaction_delay_ms   poll/reaction interval in ms (default 200)
"""
import logging

from agents.autonomous_miner import AutonomousMinerAgent
from agents.monero_rpc import MoneroRPC, RPCError
from agents.selfish_strategy import SelfishStrategy


class SelfishMinerAgent(AutonomousMinerAgent):
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        self.strategy_name = self.attributes.get("strategy", "honest")
        self.bridge_agent_id = self.attributes.get("bridge_agent")
        self.attack_start_height = int(self.attributes.get("attack_start_height", "0") or 0)
        self.reaction_delay_ms = int(self.attributes.get("reaction_delay_ms", "200") or 200)
        self.bridge_rpc = None
        self.strategy = None
        self._forwarded_index = -1     # highest honest block index forwarded to the miner
        self._released_index = -1      # highest private block index released to the bridge
        self._forwarded_hashes = {}    # height -> hash last forwarded, for reorg detection (C3)
        self._tx_warned = False        # C4: warn once if a block carries transactions

    # How many trailing honest blocks to re-check for reorgs each tick. Selfish
    # and natural forks are shallow; a submit of an unchanged/already-present
    # block is harmless (rejected).
    REORG_WINDOW = 6

    def _block_hash(self, blk) -> str:
        return (blk.get("block_header") or {}).get("hash")

    def _warn_if_has_txs(self, blk, idx: int, which: str) -> None:
        """Phase 1 moves BARE block blobs; a block carrying tx hashes will be
        rejected by submit_block ('tx not found in pool'). Phase-1 configs
        generate no transactions, so this is latent — warn once if it ever is
        not (review C4)."""
        if blk.get("tx_hashes") and not self._tx_warned:
            self.logger.warning(
                f"block {idx} ({which}) carries {len(blk['tx_hashes'])} transaction(s); "
                "phase-1 selfish mining relays bare block blobs only, so submit_block "
                "may reject it. Phase-1 configs should generate no transactions.")
            self._tx_warned = True

    def _reaction_interval_s(self) -> float:
        return max(self.reaction_delay_ms, 1) / 1000.0

    def _ensure_strategy(self, start_height: int) -> None:
        if self.strategy is None:
            self.strategy = SelfishStrategy(self.strategy_name, start_height)

    def _connect_bridge(self) -> bool:
        registry = self.read_shared_state("agent_registry.json") or {}
        for agent in registry.get("agents", []):
            if agent.get("id") == self.bridge_agent_id:
                host = agent.get("ip_addr")
                port = agent.get("daemon_rpc_port")
                if host and port:
                    self.bridge_rpc = MoneroRPC(host, int(port))
                    self.logger.info(f"Bridge connected: {self.bridge_agent_id} at {host}:{port}")
                    return True
        self.logger.debug(f"Bridge {self.bridge_agent_id} not yet in registry")
        return False

    def _forward_one(self, idx: int, blk=None) -> None:
        """Fetch honest block `idx` from the bridge and submit it into the
        offline miner, recording its hash for reorg detection."""
        try:
            if blk is None:
                blk = self.bridge_rpc.get_block(height=idx)
        except RPCError as e:
            self.logger.debug(f"forward honest block {idx}: fetch failed {e}")
            return
        self._warn_if_has_txs(blk, idx, "honest")
        blob = blk.get("blob")
        if blob:
            try:
                self.daemon_rpc.submit_block(blob)
            except RPCError as e:
                # Already-have / alt on the miner is expected and harmless.
                self.logger.debug(f"forward honest block {idx}: submit {e}")
        h = self._block_hash(blk)
        if h:
            self._forwarded_hashes[idx] = h

    def _forward_public_blocks(self, pub_height: int) -> None:
        """Forward honest blocks into the offline miner, reorg-aware (review C3).

        New blocks above the high-water mark are forwarded once. A trailing
        window is then re-checked: if the honest block at a height we already
        forwarded now has a different hash, the honest chain reorged there, so
        re-forward it — otherwise the miner would stay wedged on a dead honest
        branch and mine a private chain that the network can never accept."""
        for idx in range(self._forwarded_index + 1, pub_height):
            self._forward_one(idx)
            self._forwarded_index = idx
        floor = max(1, pub_height - self.REORG_WINDOW)
        for idx in range(floor, pub_height):
            try:
                blk = self.bridge_rpc.get_block(height=idx)
            except RPCError as e:
                self.logger.debug(f"reorg recheck {idx}: {e}")
                continue
            h = self._block_hash(blk)
            if h and self._forwarded_hashes.get(idx) != h:
                self.logger.info(f"honest reorg detected at height {idx}; re-forwarding")
                self._forward_one(idx, blk)

    def _release_up_to(self, release_from: int, release_index: int) -> None:
        """Submit the attacker's divergent private blocks to the bridge in order.

        `release_from` comes from the strategy decision (the fork BEFORE the
        step mutated it); reading the post-update strategy.fork here would make
        the reveal submit an empty range and the attacker could never win
        (review C1)."""
        start = max(release_from, self._released_index + 1)
        for idx in range(start, release_index + 1):
            try:
                blk = self.daemon_rpc.get_block(height=idx)
                self._warn_if_has_txs(blk, idx, "private")
                blob = blk.get("blob")
                if blob:
                    self.bridge_rpc.submit_block(blob)
            except RPCError as e:
                # Expected for equal-height alts (gamma=0) and already-present blocks.
                self.logger.debug(f"release private block {idx}: {e}")
            self._released_index = max(self._released_index, idx)

    def run_iteration(self) -> float:
        # 1. Keep the offline miner mining.
        try:
            self._native_run_iteration()
        except RPCError as e:
            self.logger.warning(f"native mining iteration: {e}")

        # 2. Ensure the bridge is connected.
        if self.bridge_rpc is None and not self._connect_bridge():
            return 1.0

        # 3/4. Read both chain heights.
        try:
            pub_height = int(self.bridge_rpc.get_info().get("height", 0))
            priv_height = int(self.daemon_rpc.get_info().get("height", 0))
        except RPCError as e:
            self.logger.warning(f"height read failed: {e}")
            return self._reaction_interval_s()

        self._ensure_strategy(self.attack_start_height)

        # 5. Forward new honest blocks into the offline miner.
        self._forward_public_blocks(pub_height)

        # 6. Strategy decision -> release.
        decision = self.strategy.update(pub_height, priv_height)
        if decision.release_to is not None:
            self._release_up_to(decision.release_from, decision.release_to)

        return self._reaction_interval_s()


def main():
    parser = SelfishMinerAgent.create_argument_parser("Selfish-mining attacker agent")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    agent = SelfishMinerAgent(
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
