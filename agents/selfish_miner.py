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

Eclipse composition (experiment 3): the `islands` attribute names ISLAND
bridges — relays P2P-isolated from the honest network whose only peers are
eclipsed victim miners pinned to them (orchestrator `peers:`/`eclipsed:`
knobs). Each tick the agent MIRRORS its own daemon's chain onto every island
(victims unknowingly extend the withheld private chain) and PULLS the
islands' new main-chain blocks back into the offline miner (victim blocks
join the private branch, so the existing release path cashes the combined
chain and the strategy sees the recruited hashrate as its own lead).

Attributes (via --attributes KEY VALUE):
    strategy            "honest" | "eyal_sirer"  (default "honest")
    bridges             comma-separated bridge agent ids (required)
    bridge_agent        single-bridge alias for `bridges` (phase-1 configs)
    islands             comma-separated ISLAND bridge agent ids (optional;
                        eclipse-composition experiments only)
    attack_start_height block count at which withholding begins (default 0)
    reaction_delay_ms   poll/reaction interval in ms (default 200)
    release_lead        cash out the private chain once honest closes to within
                        this many blocks (default 1 = textbook Eyal-Sirer;
                        2 = Qubic's observed conservative release, Lee & Kim
                        2025 -- see agents/selfish_strategy.py)
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
        islands_attr = self.attributes.get("islands") or ""
        self.island_agent_ids = [b.strip() for b in islands_attr.split(",") if b.strip()]
        self.island_rpcs = []
        self._connected_island_ids = set()
        self._mirrored_index = 0    # highest own-chain height pushed to islands
        self._island_pulled = []    # per-island next index the miner needs (counts: see _pull_island_blocks)
        self._island_heights = []   # per-island last-known main-chain height
        self._island_seen = []      # per-island {height: hash} last pulled (reorg detection)
        self._island_tiphash = []   # per-island last-seen island tip hash (reorg gate)
        self.island_cash_lead = int(self.attributes.get("island_cash_lead", "2") or 2)
        self.attack_start_height = int(self.attributes.get("attack_start_height", "0") or 0)
        self.reaction_delay_ms = int(self.attributes.get("reaction_delay_ms", "200") or 200)
        self.trail_depth = int(self.attributes.get("trail_depth", "1") or 1)  # trail_stubborn only
        self.release_lead = int(self.attributes.get("release_lead", "1") or 1)  # cash-out threshold
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
            self.strategy = SelfishStrategy(self.strategy_name, start_height,
                                            trail_depth=self.trail_depth,
                                            release_lead=self.release_lead)

    def _lookup_agents(self, agent_ids, connected_ids, rpcs, what: str) -> None:
        """Resolve agent ids to RPC endpoints from the shared registry,
        appending any not yet connected (shared by bridges and islands)."""
        registry = self.read_shared_state("agent_registry.json") or {}
        by_id = {agent.get("id"): agent for agent in registry.get("agents", [])}
        for bid in agent_ids:
            if bid in connected_ids:
                continue
            agent = by_id.get(bid)
            host = agent.get("ip_addr") if agent else None
            port = agent.get("daemon_rpc_port") if agent else None
            if host and port:
                rpcs.append(MoneroRPC(host, int(port)))
                connected_ids.add(bid)
                self.logger.info(f"{what} connected: {bid} at {host}:{port}")
            else:
                self.logger.debug(f"{what} {bid} not yet in registry")

    def _connect_bridges(self) -> bool:
        """Connect any bridge in `bridge_agent_ids` not yet connected. Returns
        True once every configured bridge has been connected at least once."""
        self._lookup_agents(self.bridge_agent_ids, self._connected_ids, self.bridge_rpcs, "Bridge")
        if self.bridge_rpcs:
            self.bridge_rpc = self.bridge_rpcs[0]
        return len(self._connected_ids) == len(self.bridge_agent_ids) > 0

    def _connect_islands(self) -> bool:
        """Connect any island in `island_agent_ids` not yet connected."""
        if self.island_agent_ids and not self._island_pulled:
            self._island_pulled = [0] * len(self.island_agent_ids)
        self._lookup_agents(self.island_agent_ids, self._connected_island_ids,
                            self.island_rpcs, "Island")
        return len(self._connected_island_ids) == len(self.island_agent_ids) > 0

    def _mirror_private_blocks(self, priv_height: int) -> None:
        """Push the offline miner's chain onto every island — extension-only
        (v4), and never above the strategy's fork (v12).

        The v12 gate is the rest-window design from the results doc, made
        precise: the island gets the committed prefix (indexes < fork) plus
        the PRIVATE suffix the miner is withholding above it — never the
        honest blocks the miner adopted from forwards. Without the gate, the
        mirror streamed the miner's full main chain (honest 5 h/s + attacker
        4 h/s) onto the island, and the victim's 6 h/s could never win
        first-seen there: its branches died at the island (v11 — victim 199
        finds, 0 canonical, network orphan rate 0.589). With it, the victim
        races only the attacker's hashrate above the fork, its branch IS the
        island main, and the pull + monerod's switch-to-longer deliver it
        into the miner's private chain for the next cash-out.

        HEIGHT CONVENTION (the v8 off-by-one): get_info heights are COUNTS
        (top index + 1); block indexes are 0-based. An island at count C
        needs indexes C, C+1, ...; the miner at count M can supply indexes
        0..M-1. Submitting index M (one past the top) asks for a block that
        does not exist, and submitting index C+1 before C orphans it — monerod
        answers orphaned submits with status OK, so both mistakes were
        invisible until submit_block status checking landed."""
        if not self.island_rpcs:
            return
        fork = self.strategy.fork if self.strategy else 0
        island_count = min(self._island_heights) if self._island_heights else 0
        if priv_height < self._mirrored_index:
            # Own reorg: heights can have changed anywhere above the new tip,
            # so re-mirror from genesis. Re-submits of unchanged blocks are
            # harmless already-have rejections at the islands.
            self._mirrored_index = 0
        start = max(self._mirrored_index, island_count)
        pushed = 0
        for idx in range(start, min(priv_height, fork)):
            try:
                blk = self.daemon_rpc.get_block(height=idx)
                blob = blk.get("blob")
            except RPCError as e:
                self.logger.debug(f"mirror private block {idx}: {e}")
                break                               # retry next tick
            if blob:
                undelivered = False
                for rpc in self.island_rpcs:
                    try:
                        rpc.submit_block(blob)
                    except RPCError as e:
                        # shorter-than-island-main submissions (post-concession
                        # resyncs) can land as alts; harmless.
                        self.logger.debug(f"mirror private block {idx} to island: {e}")
                        if "Request failed" in str(e) or "Max retries" in str(e):
                            undelivered = True
                if undelivered:
                    break                   # retry this index next tick
            self._mirrored_index = idx + 1
            pushed += 1
        if pushed:
            self.logger.info(f"island mirror: pushed {pushed} block(s) "
                             f"(gate at fork {fork}), island needs {self._mirrored_index}")

    def _pull_island_blocks(self) -> None:
        """Pull each island's main chain into the offline miner — divergence-
        aware (v5), the same reorg-aware pattern _forward_public_blocks uses
        for the honest feed, with the island as source and the offline miner
        as sink. Per island: remember the hash seen at each height; on a new
        island tip, walk parent-first from the first height whose hash
        changed (or the first new height), and submit every block that is
        EITHER above the miner's tip (an extension) OR a never-seen divergent
        block at a height the miner already holds (the first block(s) of a
        victim-led branch — submitting the whole branch lets monerod adopt it
        when it is longer). The v4 rule skipped exactly those first divergent
        blocks, orphaning every victim-led branch at birth: the majority-run
        instrumentation showed pulls firing (34 ticks) yet zero victim blocks
        ever entering the miner's chain."""
        try:
            miner_count = int(self.daemon_rpc.get_info().get("height", 0))
        except RPCError as e:
            self.logger.debug(f"miner height read for pull: {e}")
            return
        for i, rpc in enumerate(self.island_rpcs):
            while len(self._island_pulled) <= i:
                self._island_pulled.append(0)
            while len(self._island_seen) <= i:
                self._island_seen.append({})
            while len(self._island_tiphash) <= i:
                self._island_tiphash.append(None)
            try:
                info = rpc.get_info()
                island_count = int(info.get("height", 0))
                island_tip_hash = info.get("top_block_hash")
            except RPCError as e:
                self.logger.debug(f"island {i} height read: {e}")
                continue
            if i < len(self._island_heights):
                self._island_heights[i] = island_count
            else:
                self._island_heights.append(island_count)
            seen = self._island_seen[i]
            pulled = self._island_pulled[i]        # next island index the miner needs
            reorg = island_tip_hash is not None and island_tip_hash != self._island_tiphash[i]
            start = pulled
            if reorg:
                floor = max(1, island_count - self.REORG_WINDOW)
                hi = min(pulled, island_count - 1)
                for idx in range(floor, hi + 1):
                    try:
                        cur = self._block_hash(rpc.get_block(height=idx))
                    except RPCError as e:
                        self.logger.debug(f"island {i} reorg rescan {idx}: {e}")
                        cur = None
                    if seen.get(idx) != cur:
                        self.logger.info(f"island {i} reorg at height {idx}; re-pulling from there")
                        start = idx
                        break
                if pulled > island_count:          # island chain shrank
                    start = min(start, floor)
            submitted = 0
            for idx in range(start, island_count):
                try:
                    blk = rpc.get_block(height=idx)
                    blob = blk.get("blob")
                except RPCError as e:
                    self.logger.debug(f"pull island block {idx}: {e}")
                    break                           # retry next tick
                h = self._block_hash(blk)
                if blob and (idx >= miner_count or seen.get(idx) != h):
                    # an extension of the miner's main chain (idx >= count),
                    # or the head of a divergent branch: submit; monerod keeps
                    # whichever branch is longer from the fork.
                    try:
                        self.daemon_rpc.submit_block(blob)
                        submitted += 1
                    except RPCError as e:
                        self.logger.debug(f"pull island block {idx} into miner: {e}")
                if h:
                    seen[idx] = h
            for k in [k for k in seen if k >= island_count]:
                del seen[k]               # island main shrank: forget above the new tip
            self._island_pulled[i] = island_count
            self._island_tiphash[i] = island_tip_hash
            if submitted:
                self.logger.info(f"island {i}: pulled {submitted} block(s) "
                                 f"(miner count was {miner_count})")

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

    def _common_ancestor_with_bridge(self, pub_height: int, priv_height: int,
                                     limit: int = 256) -> int:
        """The highest height at which the offline miner's chain and the
        bridge's (public) chain hold the SAME block hash, found by walking
        down from min(pub, priv). The eclipse composition can leave the
        miner on a branch that diverged from the public chain far below the
        strategy's fork (a stale private branch the island resurrected), and
        releasing from `fork` then submits blocks whose parents the network
        never had — monerod files them as orphans and answers OK, so the
        loss is invisible (the v10 release-side failure)."""
        hi = min(pub_height, priv_height)
        for h in range(hi - 1, max(-1, hi - 1 - limit), -1):
            try:
                mine = self._block_hash(self.daemon_rpc.get_block(height=h))
                pubs = self._block_hash(self.bridge_rpc.get_block(height=h))
            except RPCError:
                continue
            if mine and pubs and mine == pubs:
                return h
        return 0

    def _island_cash_out(self, pub_height: int, priv_height: int) -> bool:
        """Cash-on-lead island lifecycle: the moment the island branch is
        `island_cash_lead` blocks ahead of the honest public chain, release
        the combined chain and commit the win.

        v11: the release starts at the hash-verified common ancestor with the
        bridge (NOT the strategy's fork — the miner may sit on a branch the
        fork bookkeeping no longer describes), and the fork commits ONLY on
        verified adoption (the bridge's height reaching ours). A submitted
        branch that fails to convince the network leaves fork and the
        release watermark untouched, so the next tick re-releases the same
        connected range instead of orphaning everything after a phantom
        commit — the fire-and-forget assumption that held at gamma~0 without
        islands does not survive them."""
        if not self.island_rpcs or not self._island_heights or not self.strategy:
            return False
        if self.strategy.fork >= priv_height:
            return False                      # nothing divergent to cash
        lead = max(self._island_heights) - pub_height
        if lead < self.island_cash_lead:
            return False
        ancestor = self._common_ancestor_with_bridge(pub_height, priv_height)
        if ancestor >= priv_height:
            return False                      # nothing divergent after all
        self._released_index = min(self._released_index, ancestor)
        self._release_up_to(ancestor, priv_height - 1)
        adopted = False
        try:
            adopted = int(self.bridge_rpc.get_info().get("height", 0)) >= priv_height
        except RPCError as e:
            self.logger.debug(f"cash-out adoption check: {e}")
        if adopted:
            self.strategy.fork = priv_height
            self.logger.info(f"Island cash-out at lead {lead} from ancestor "
                             f"{ancestor}: committed through height {priv_height}")
        else:
            self.logger.info(f"Island cash-out at lead {lead} from ancestor "
                             f"{ancestor}: NOT adopted yet (bridge behind) — will retry")
        return adopted

    def run_iteration(self) -> float:
        # 1. Keep the offline miner mining.
        try:
            self._native_run_iteration()
        except RPCError as e:
            self.logger.warning(f"native mining iteration: {e}")

        # 2. Ensure all bridges are connected (public read/publish path) and
        #    islands too (eclipse composition, if configured).
        if len(self.bridge_rpcs) < len(self.bridge_agent_ids):
            self._connect_bridges()
        if not self.bridge_rpcs:
            return 1.0
        if self.island_agent_ids and len(self.island_rpcs) < len(self.island_agent_ids):
            self._connect_islands()

        # 3/4. Read both chains (height + honest tip hash for reorg detection).
        try:
            pub_info = self.bridge_rpc.get_info()
            pub_height = int(pub_info.get("height", 0))
            pub_tip_hash = pub_info.get("top_block_hash")
            priv_height = int(self.daemon_rpc.get_info().get("height", 0))
        except RPCError as e:
            self.logger.warning(f"height read failed: {e}")
            return self._reaction_interval_s()

        # 4b. Eclipse composition: sync own chain with the islands BOTH ways
        #     BEFORE the strategy looks at heights — victim blocks pulled in
        #     here grow the private lead the strategy reasons about, and the
        #     mirror keeps victims building on the attacker's current chain.
        if self.island_rpcs:
            self._pull_island_blocks()
            try:
                priv_height = int(self.daemon_rpc.get_info().get("height", 0))
            except RPCError as e:
                self.logger.warning(f"private height re-read failed: {e}")
            self._mirror_private_blocks(priv_height)

        self._ensure_strategy(self.attack_start_height)

        # 5. Strategy decision first: forward_to (below) depends on it.
        decision = self.strategy.update(pub_height, priv_height)

        # 6. Forward honest blocks into the offline miner (reorg-aware, capped
        #    by decision.forward_to). Island mode (v13) additionally caps the
        #    feed at the strategy's fork while withholding: fed honest blocks
        #    compound into the miner's main (5 h/s of adoption + the
        #    attacker's own 4) and the victim's island branch (6 h/s) can
        #    never overtake it from behind — v12's measured stall. With the
        #    cap, the miner's main during withholding is the private branch
        #    alone; the longer victim branch takes it over via the pull, the
        #    attacker then mines ON it, and the concession path (fork = pub)
        #    re-opens the feed automatically. Base (non-island) behavior is
        #    byte-identical.
        cap = decision.forward_to
        if self.island_rpcs and self.strategy and cap is None:
            cap = self.strategy.fork
        self._forward_public_blocks(pub_height, pub_tip_hash, cap)

        # 7. Release per decision. The offline miner's chain already contains
        #    victim blocks (pulled above), so the release cashes the combined
        #    branch unchanged.
        if decision.release_to is not None:
            self._release_up_to(decision.release_from, decision.release_to)

        # 8. Island cash-out (v2 lifecycle): bank the combined branch the
        #    moment it leads honest by `island_cash_lead`, regardless of the
        #    strategy's own timing.
        if self.island_rpcs:
            self._island_cash_out(pub_height, priv_height)

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
