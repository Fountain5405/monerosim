"""Selfish-mining attacker agent.

Runs on the attacker's OFFLINE miner daemon (native throttled RandomX). Its
own daemon (self.daemon_rpc) withholds by construction because it has no P2P.
One or more separate, normally-connected bridge daemons (discovered from
agent_registry.json by the `bridges` attribute) are the read/write path to
the honest network: the first bridge is the read source, and on release every
private block is submitted to EVERY bridge (this is what lifts gamma). Each
tick this agent forwards new honest blocks into the offline miner and
releases private blocks to the bridges per the SelfishStrategy decision. See
docs/SELFISH_MINING.md.

Attributes (via --attributes KEY VALUE):
    strategy            "honest" | "eyal_sirer"  (default "honest")
    bridges             comma-separated bridge agent ids (required)
    bridge_agent        single-bridge alias for `bridges` (phase-1 configs)
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
        bridges_attr = self.attributes.get("bridges") or self.attributes.get("bridge_agent") or ""
        self.bridge_agent_ids = [b.strip() for b in bridges_attr.split(",") if b.strip()]
        self.bridge_rpcs = []
        self.bridge_rpc = None
        self._connected_ids = set()
        self.attack_start_height = int(self.attributes.get("attack_start_height", "0") or 0)
        self.reaction_delay_ms = int(self.attributes.get("reaction_delay_ms", "200") or 200)
        self.trail_depth = int(self.attributes.get("trail_depth", "1") or 1)  # trail_stubborn only
        self.strategy = None
        self._forwarded_index = -1     # highest honest block index forwarded to the miner
        self._released_index = -1      # highest private block index released to the bridge
        self._forwarded_hashes = {}    # height -> hash last forwarded, for reorg detection (C3)
        self._last_pub_tip_hash = None # honest tip hash last seen; gates the reorg rescan (C3)
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
            self.strategy = SelfishStrategy(self.strategy_name, start_height, trail_depth=self.trail_depth)

    def _connect_bridges(self) -> bool:
        """Connect any bridge in `bridge_agent_ids` not yet connected. Returns
        True once every configured bridge has been connected at least once."""
        registry = self.read_shared_state("agent_registry.json") or {}
        by_id = {agent.get("id"): agent for agent in registry.get("agents", [])}
        for bid in self.bridge_agent_ids:
            if bid in self._connected_ids:
                continue
            agent = by_id.get(bid)
            host = agent.get("ip_addr") if agent else None
            port = agent.get("daemon_rpc_port") if agent else None
            if host and port:
                self.bridge_rpcs.append(MoneroRPC(host, int(port)))
                self._connected_ids.add(bid)
                self.logger.info(f"Bridge connected: {bid} at {host}:{port}")
            else:
                self.logger.debug(f"Bridge {bid} not yet in registry")
        if self.bridge_rpcs:
            self.bridge_rpc = self.bridge_rpcs[0]
        return len(self._connected_ids) == len(self.bridge_agent_ids) > 0

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

    def _forward_public_blocks(self, pub_height: int, tip_hash=None, forward_to=None) -> None:
        """Forward honest blocks into the offline miner, reorg-aware (review C3).

        `forward_to` (from the strategy decision) caps how far honest blocks
        may reach the miner: effective_tip = pub_height if forward_to is None
        else min(pub_height, forward_to). A later stubborn strategy uses this
        to keep the miner from seeing honest blocks past a chosen point.

        Order matters: a reorg that raises the height (…,X1 → …,Y1,Y2) must
        forward the new parent Y1 BEFORE its child Y2, or the miner orphans Y2
        and never retries it, wedging on a dead branch. So on a tip change we
        first find the lowest already-forwarded height whose hash changed, then
        forward everything from there up to the tip in ascending (parent-first)
        order; new blocks append the same way. The rescan is gated on the
        honest tip hash, so idle ticks do no extra RPC."""
        effective_tip = pub_height if forward_to is None else min(pub_height, forward_to)
        reorg = tip_hash is not None and tip_hash != self._last_pub_tip_hash
        start = self._forwarded_index + 1          # default: only not-yet-forwarded heights
        if reorg:
            floor = max(1, effective_tip - self.REORG_WINDOW)
            hi = min(self._forwarded_index, effective_tip - 1)
            for idx in range(floor, hi + 1):
                try:
                    cur = self._block_hash(self.bridge_rpc.get_block(height=idx))
                except RPCError as e:
                    self.logger.debug(f"reorg rescan {idx}: {e}")
                    cur = None
                if self._forwarded_hashes.get(idx) != cur:
                    self.logger.info(f"honest reorg at height {idx}; re-forwarding from there")
                    start = idx                     # ascending from here => parent before child
                    break
            if self._forwarded_index >= effective_tip:  # chain shrank below our high-water mark
                start = min(start, floor)
        for idx in range(start, effective_tip):
            self._forward_one(idx)
        if effective_tip > 0:
            self._forwarded_index = effective_tip - 1
        for k in [k for k in self._forwarded_hashes if k >= effective_tip]:
            del self._forwarded_hashes[k]           # forget hashes above a shrunk tip
        if tip_hash is not None:
            self._last_pub_tip_hash = tip_hash

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
            except RPCError as e:
                self.logger.debug(f"release private block {idx}: {e}")
                blob = None
            if blob:
                for rpc in self.bridge_rpcs:
                    try:
                        rpc.submit_block(blob)
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

        # 2. Ensure all bridges are connected.
        if len(self.bridge_rpcs) < len(self.bridge_agent_ids):
            self._connect_bridges()
        if not self.bridge_rpcs:
            return 1.0

        # 3/4. Read both chains (height + honest tip hash for reorg detection).
        try:
            pub_info = self.bridge_rpc.get_info()
            pub_height = int(pub_info.get("height", 0))
            pub_tip_hash = pub_info.get("top_block_hash")
            priv_height = int(self.daemon_rpc.get_info().get("height", 0))
        except RPCError as e:
            self.logger.warning(f"height read failed: {e}")
            return self._reaction_interval_s()

        self._ensure_strategy(self.attack_start_height)

        # 5. Strategy decision first: forward_to (below) depends on it.
        decision = self.strategy.update(pub_height, priv_height)

        # 6. Forward honest blocks into the offline miner (reorg-aware, capped
        #    by decision.forward_to).
        self._forward_public_blocks(pub_height, pub_tip_hash, decision.forward_to)

        # 7. Release per decision.
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
