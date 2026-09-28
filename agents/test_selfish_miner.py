from unittest.mock import MagicMock
import pytest
from agents.selfish_miner import SelfishMinerAgent
from agents.monero_rpc import RPCError


def _make_agent(strategy="eyal_sirer", start_height=0, reaction_ms=200):
    a = SelfishMinerAgent(
        agent_id="attacker-miner",
        attributes=[["strategy", strategy],
                    ["bridge_agent", "attacker-bridge"],
                    ["attack_start_height", str(start_height)],
                    ["reaction_delay_ms", str(reaction_ms)]],
    )
    a.logger = MagicMock()
    # Own daemon (offline miner) and bridge daemon are mocked.
    a.daemon_rpc = MagicMock()
    a.bridge_rpc = MagicMock()
    a.bridge_rpcs = [a.bridge_rpc]
    a.native_started = True            # skip real start_mining
    a._native_run_iteration = MagicMock(return_value=1.0)
    a._ensure_strategy(0)
    return a


def test_reads_attributes():
    a = _make_agent(strategy="eyal_sirer", start_height=5, reaction_ms=150)
    assert a.strategy_name == "eyal_sirer"
    assert a.bridge_agent_ids == ["attacker-bridge"]
    assert a.attack_start_height == 5
    assert abs(a._reaction_interval_s() - 0.15) < 1e-9


def test_connect_bridge_reads_registry(monkeypatch):
    a = SelfishMinerAgent(
        agent_id="attacker-miner",
        attributes=[["strategy", "honest"], ["bridge_agent", "attacker-bridge"]],
    )
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={
        "agents": [
            {"id": "attacker-miner", "ip_addr": "11.0.0.1", "daemon_rpc_port": 28081},
            {"id": "attacker-bridge", "ip_addr": "11.0.0.2", "daemon_rpc_port": 28082},
        ]
    })
    assert a._connect_bridges() is True
    assert a.bridge_rpc.url == "http://11.0.0.2:28082/json_rpc"


def test_connect_bridge_missing_returns_false():
    a = SelfishMinerAgent(agent_id="attacker-miner",
                          attributes=[["bridge_agent", "nope"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": []})
    assert a._connect_bridges() is False
    assert a.bridge_rpcs == []


def test_forward_public_blocks_submits_new_honest_blocks():
    a = _make_agent()
    a.bridge_rpc.get_block.side_effect = lambda height: {"blob": f"pub{height}"}
    a._forward_public_blocks(pub_height=3)   # indexes 0,1,2
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["pub0", "pub1", "pub2"]
    assert a._forwarded_index == 2
    # Idempotent: a second call with no new blocks submits nothing more.
    a.daemon_rpc.submit_block.reset_mock()
    a._forward_public_blocks(pub_height=3)
    a.daemon_rpc.submit_block.assert_not_called()


def test_release_up_to_submits_private_blocks_to_bridge():
    a = _make_agent()
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"priv{height}"}
    a.bridge_rpcs = [a.bridge_rpc]
    a._release_up_to(1, 3)   # release_from=1 -> indexes 1,2,3
    submitted = [c.args[0] for c in a.bridge_rpc.submit_block.call_args_list]
    assert submitted == ["priv1", "priv2", "priv3"]
    assert a._released_index == 3


def test_release_tolerates_rejected_alt():
    a = _make_agent()
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a.bridge_rpc.submit_block.side_effect = [RPCError("Block not accepted"), {"status": "OK"}]
    a.bridge_rpcs = [a.bridge_rpc]
    a._release_up_to(0, 1)   # index 0 rejected (alt), index 1 accepted -> no raise
    assert a._released_index == 1


def test_run_iteration_reveal_win_releases_to_bridge():
    """Integration guard for review C1: a reveal-and-win must actually submit the
    withheld blocks to the bridge. With the pre-fix code (release range read from
    the post-update strategy.fork) this submitted nothing."""
    a = _make_agent(strategy="eyal_sirer")
    a.daemon_rpc.get_block.side_effect = lambda height: {
        "blob": f"priv{height}", "block_header": {"hash": f"ph{height}"}}
    a.bridge_rpc.get_block.side_effect = lambda height: {
        "blob": f"pub{height}", "block_header": {"hash": f"hh{height}"}}

    # Tick 1: attacker 2 ahead (pub=1, priv=3) -> withhold, nothing to the bridge.
    a.bridge_rpc.get_info.return_value = {"height": 1}
    a.daemon_rpc.get_info.return_value = {"height": 3}
    a.run_iteration()
    assert a.bridge_rpc.submit_block.call_count == 0

    # Tick 2: honest catches to within one (pub=2, priv=3) -> reveal and win.
    a.bridge_rpc.get_info.return_value = {"height": 2}
    a.daemon_rpc.get_info.return_value = {"height": 3}
    a.run_iteration()
    assert a.bridge_rpc.submit_block.call_count >= 1   # winning blocks released


def test_forwarder_reforwards_on_honest_reorg():
    """Review C3: when an already-forwarded honest height changes hash (reorg),
    the forwarder must re-submit it to the offline miner."""
    a = _make_agent()
    hashes = {0: "x0", 1: "x1", 2: "x2"}
    a.bridge_rpc.get_block.side_effect = lambda height: {
        "blob": f"b{height}.{hashes[height]}", "block_header": {"hash": hashes[height]}}
    a._forward_public_blocks(3, tip_hash="x2")   # forwards indexes 0,1,2
    a.daemon_rpc.submit_block.reset_mock()
    hashes[2] = "y2"                              # height 2 reorged (same height)
    a._forward_public_blocks(3, tip_hash="y2")
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["b2.y2"]                 # only the reorged block re-forwarded


def test_forwarder_reorg_forwards_parent_before_child():
    """Review C3 ordering (re-review): a reorg that RAISES the height
    (…,X1 -> …,Y1,Y2) must forward the new parent Y1 before child Y2, or the
    miner orphans Y2 and wedges. The pre-fix code forwarded Y2 first."""
    a = _make_agent()
    chain = {0: "g", 1: "X1"}
    a.bridge_rpc.get_block.side_effect = lambda height: {
        "blob": f"b{height}.{chain[height]}", "block_header": {"hash": chain[height]}}
    a._forward_public_blocks(2, tip_hash="X1")    # forward g, X1
    a.daemon_rpc.submit_block.reset_mock()
    chain = {0: "g", 1: "Y1", 2: "Y2"}            # reorg: X1 replaced AND height grows
    a._forward_public_blocks(3, tip_hash="Y2")
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["b1.Y1", "b2.Y2"]        # parent Y1 strictly before child Y2


def test_forwarder_idle_tick_does_no_rpc_when_tip_unchanged():
    """The reorg rescan is gated on the tip hash, so a tick with no new block
    and an unchanged tip must not fetch anything (review perf note)."""
    a = _make_agent()
    chain = {0: "g", 1: "X1"}
    a.bridge_rpc.get_block.side_effect = lambda height: {
        "blob": f"b{height}.{chain[height]}", "block_header": {"hash": chain[height]}}
    a._forward_public_blocks(2, tip_hash="X1")
    a.bridge_rpc.get_block.reset_mock()
    a._forward_public_blocks(2, tip_hash="X1")    # same tip, nothing new
    a.bridge_rpc.get_block.assert_not_called()


def test_bridges_attribute_parsed_as_list():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1, b2 ,b3"]])
    a.logger = MagicMock()
    assert a.bridge_agent_ids == ["b1", "b2", "b3"]


def test_bridge_agent_is_single_element_alias():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridge_agent", "only"]])
    a.logger = MagicMock()
    assert a.bridge_agent_ids == ["only"]


def test_connect_bridges_all_and_read_source():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081},
        {"id": "b2", "ip_addr": "10.0.0.2", "daemon_rpc_port": 28082}]})
    assert a._connect_bridges() is True
    assert [r.url for r in a.bridge_rpcs] == [
        "http://10.0.0.1:28081/json_rpc", "http://10.0.0.2:28082/json_rpc"]
    assert a.bridge_rpc.url == "http://10.0.0.1:28081/json_rpc"


def test_connect_bridges_retries_missing():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081}]})
    assert a._connect_bridges() is False and len(a.bridge_rpcs) == 1
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081},
        {"id": "b2", "ip_addr": "10.0.0.2", "daemon_rpc_port": 28082}]})
    assert a._connect_bridges() is True and len(a.bridge_rpcs) == 2


def test_release_submits_to_all_bridges():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock(); a.daemon_rpc = MagicMock()
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    b1, b2 = MagicMock(), MagicMock(); a.bridge_rpcs = [b1, b2]; a.bridge_rpc = b1
    a._release_up_to(0, 1)
    assert [c.args[0] for c in b1.submit_block.call_args_list] == ["p0", "p1"]
    assert [c.args[0] for c in b2.submit_block.call_args_list] == ["p0", "p1"]


def test_forward_to_caps_forwarding():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1"]])
    a.logger = MagicMock(); a.daemon_rpc = MagicMock(); a.bridge_rpc = MagicMock()
    a.bridge_rpcs = [a.bridge_rpc]
    a.bridge_rpc.get_block.side_effect = lambda height: {"blob": f"h{height}"}
    a._forward_public_blocks(pub_height=5, tip_hash=None, forward_to=2)  # cap at index 1
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["h0", "h1"]          # indexes 0,1 only (forward_to=2 => heights <2)
    assert a._forwarded_index == 1


def test_trail_depth_attribute_flows_to_strategy():
    # Phase-2 gap fix: trail_depth from attributes must reach SelfishStrategy,
    # else stub_trail.yaml's trail_depth is inert (defaults to 1).
    a = SelfishMinerAgent(agent_id="atk", attributes=[
        ["strategy", "trail_stubborn"], ["trail_depth", "2"], ["bridges", "b1"]])
    a.logger = MagicMock()
    assert a.trail_depth == 2
    a._ensure_strategy(0)
    assert a.strategy.trail_depth == 2 and a.strategy.name == "trail_stubborn"


def test_trail_depth_defaults_to_one():
    a = SelfishMinerAgent(agent_id="atk", attributes=[
        ["strategy", "trail_stubborn"], ["bridges", "b1"]])
    a.logger = MagicMock()
    assert a.trail_depth == 1


def _make_island_agent():
    a = SelfishMinerAgent(agent_id="atk", attributes=[
        ["strategy", "eyal_sirer"], ["bridges", "b1"], ["islands", "i1,i2"]])
    a.logger = MagicMock()
    a.daemon_rpc = MagicMock()
    a.bridge_rpc = MagicMock()
    a.bridge_rpcs = [a.bridge_rpc]
    a.native_started = True
    a._native_run_iteration = MagicMock(return_value=1.0)
    a.daemon_rpc.get_info.return_value = {"height": 0}
    i1, i2 = MagicMock(), MagicMock()
    i1.get_info.return_value = {"height": 0}
    i2.get_info.return_value = {"height": 0}
    a.island_rpcs = [i1, i2]
    a._connected_island_ids = {"i1", "i2"}
    a._island_pulled = [0, 0]
    a._ensure_strategy(0)
    return a, i1, i2


def test_islands_attribute_parses():
    a, _, _ = _make_island_agent()
    assert a.island_agent_ids == ["i1", "i2"]


def test_connect_islands_reads_registry():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1"], ["islands", "i1"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081},
        {"id": "i1", "ip_addr": "10.0.0.9", "daemon_rpc_port": 28089}]})
    assert a._connect_islands() is True
    assert a.island_rpcs[0].url == "http://10.0.0.9:28089/json_rpc"
    assert a._island_pulled == [0]


def test_mirror_pushes_own_chain_to_every_island():
    a, i1, i2 = _make_island_agent()
    a.strategy.fork = 2                     # everything committed: gate transparent
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a._mirror_private_blocks(priv_height=2)            # count 2: indexes 0,1
    assert [c.args[0] for c in i1.submit_block.call_args_list] == ["p0", "p1"]
    assert [c.args[0] for c in i2.submit_block.call_args_list] == ["p0", "p1"]
    assert a._mirrored_index == 2
    # Watermark: no re-push of already-mirrored indexes
    i1.submit_block.reset_mock()
    a._mirror_private_blocks(priv_height=2)
    assert i1.submit_block.call_args_list == []


def test_mirror_resets_watermark_on_own_reorg():
    a, i1, _ = _make_island_agent()
    a.strategy.fork = 2                     # everything committed: gate transparent
    a._mirrored_index = 3
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a._mirror_private_blocks(priv_height=2)      # own chain shrank: count 2
    assert a._mirrored_index == 2
    assert [c.args[0] for c in i1.submit_block.call_args_list] == ["p0", "p1"]


def test_pull_submits_island_main_chain_into_miner():
    # COUNT CONVENTION: get_info heights are counts; block indexes 0..count-1.
    a, i1, i2 = _make_island_agent()
    a.daemon_rpc.get_info.return_value = {"height": 0}   # miner has nothing
    i1.get_info.return_value = {"height": 2}             # island indexes 0,1
    i2.get_info.return_value = {"height": 1}             # island indexes 0
    i1.get_block.side_effect = lambda height: {"blob": f"v{height}", "block_header": {"hash": f"h{height}"}}
    i2.get_block.side_effect = lambda height: {"blob": f"w{height}", "block_header": {"hash": f"g{height}"}}
    a._pull_island_blocks()
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["v0", "v1", "w0"]
    assert a._island_pulled == [2, 1]                    # next index needed per island
    # Next tick with one new island block: only the new one moves.
    a.daemon_rpc.submit_block.reset_mock()
    i1.get_info.return_value = {"height": 3}
    a._pull_island_blocks()
    assert [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list] == ["v2"]


def test_run_iteration_pulls_islands_before_strategy_decision():
    # Order matters: victim blocks pulled in BEFORE the strategy update grow
    # the private lead the strategy reasons about.
    from agents.selfish_strategy import ReleaseDecision
    a, i1, _ = _make_island_agent()
    calls = []

    def fake_update(pub, priv):
        calls.append(("strategy", pub, priv))
        return ReleaseDecision()

    a._pull_island_blocks = MagicMock(side_effect=lambda: calls.append("pull"))
    a._mirror_private_blocks = MagicMock(side_effect=lambda h: calls.append("mirror"))
    a._forward_public_blocks = MagicMock(side_effect=lambda *args, **kw: calls.append("forward"))
    a.strategy.update = MagicMock(side_effect=fake_update)
    a.bridge_rpc.get_info.return_value = {"height": 5, "top_block_hash": "t5"}
    heights = iter([{"height": 3}, {"height": 4}])   # before pull, after pull
    a.daemon_rpc.get_info.side_effect = lambda: next(heights)
    a.run_iteration()
    # pull victim blocks, mirror the merged chain out, THEN decide: the
    # strategy must see the post-pull height (4), not the pre-pull one (3).
    assert calls[0] == "pull" and calls[1] == "mirror"
    assert calls[2] == ("strategy", 5, 4)
    assert calls[3] == "forward"


def test_island_cash_out_fires_at_lead_and_commits():
    a, i1, i2 = _make_island_agent()
    a.strategy.fork = 10
    a._island_heights = [14, 12]          # max island height 14, pub 12 -> lead 2
    # chains agree through height 10 (fork == true ancestor), bridge adopts
    def blk(prefix):
        return lambda height: {"blob": f"{prefix}{height}",
                               "block_header": {"hash": f"{prefix}h{height}"}}
    a.daemon_rpc.get_block.side_effect = blk("m")
    a.bridge_rpc.get_block.side_effect = blk("m")
    a.bridge_rpc.get_info.return_value = {"height": 14}
    a._release_up_to = MagicMock()
    fired = a._island_cash_out(pub_height=12, priv_height=14)
    assert fired is True
    a._release_up_to.assert_called_once_with(11, 13)   # true ancestor (11), priv-1
    assert a.strategy.fork == 14                        # the win commits


def test_island_cash_out_holds_below_lead():
    a, _, _ = _make_island_agent()
    a.strategy.fork = 10
    a._island_heights = [13]             # lead 1 < 2
    a._release_up_to = MagicMock()
    assert a._island_cash_out(pub_height=12, priv_height=13) is False
    a._release_up_to.assert_not_called()
    assert a.strategy.fork == 10


def test_island_cash_out_noop_when_already_committed():
    a, _, _ = _make_island_agent()
    a.strategy.fork = 14                 # already at priv: nothing divergent
    a._island_heights = [16]
    a._release_up_to = MagicMock()
    assert a._island_cash_out(pub_height=12, priv_height=14) is False
    a._release_up_to.assert_not_called()


def test_island_cash_lead_attribute_default_and_override():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1"], ["islands", "i1"]])
    assert a.island_cash_lead == 2
    b = SelfishMinerAgent(agent_id="atk", attributes=[
        ["bridges", "b1"], ["islands", "i1"], ["island_cash_lead", "3"]])
    b.logger = MagicMock()
    assert b.island_cash_lead == 3


def test_pull_submits_divergent_branch_heads_below_miner_tip():
    # v5/v8 (count convention): a victim-led branch's FIRST block sits at an
    # index the miner already holds its own block at. The v4 rule skipped it
    # ("stale"), orphaning the whole branch; the divergence-aware rule submits
    # it so monerod can adopt the branch when it is longer.
    a, i1, _ = _make_island_agent()
    a.daemon_rpc.get_info.return_value = {"height": 3}   # miner indexes 0-2
    i1.get_info.return_value = {"height": 3}
    i1.get_block.side_effect = lambda height: {"blob": f"x{height}", "block_header": {"hash": f"h{height}"}}
    a._pull_island_blocks()
    # first tick primes seen (below-count submits are harmless already-haves)
    assert [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list] == ["x0", "x1", "x2"]
    # island wins a race at index 3 with a victim branch 3,4 while the miner
    # also has its own 3 (count 4): the divergent head MUST be submitted
    a.daemon_rpc.get_info.return_value = {"height": 4}
    a.daemon_rpc.submit_block.reset_mock()
    i1.get_info.return_value = {"height": 5}
    def blk_at(height):
        if height >= 3:                      # the victim branch diverges at 3
            return {"blob": f"v{height}", "block_header": {"hash": f"vh{height}"}}
        return {"blob": f"x{height}", "block_header": {"hash": f"h{height}"}}
    i1.get_block.side_effect = blk_at
    a._pull_island_blocks()
    assert [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list] == ["v3", "v4"]
    # steady state: the miner ADOPTED the branch (count now 5) — nothing new,
    # nothing above the tip, nothing resubmitted
    a.daemon_rpc.submit_block.reset_mock()
    a.daemon_rpc.get_info.return_value = {"height": 5}
    a._pull_island_blocks()
    assert a.daemon_rpc.submit_block.call_args_list == []


def test_pull_detects_island_reorg_via_tip_hash():
    # The island's main flips to a different branch (mirror won a reorg
    # there): the tip-hash change triggers a rescan and re-pull of the
    # changed suffix, parent-first.
    a, i1, _ = _make_island_agent()
    a.daemon_rpc.get_info.return_value = {"height": 0}
    chain = {0: "a0", 1: "a1", 2: "a2"}
    i1.get_info.return_value = {"height": 3, "top_block_hash": "a2"}
    i1.get_block.side_effect = lambda height: {"blob": f"b{height}.{chain[height]}",
                                               "block_header": {"hash": chain[height]}}
    a._pull_island_blocks()
    # island reorgs: index 1's hash changes, tip becomes c2
    chain[1] = "c1"
    chain[2] = "c2"
    a.daemon_rpc.submit_block.reset_mock()
    i1.get_info.return_value = {"height": 3, "top_block_hash": "c2"}
    a._pull_island_blocks()
    assert [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list] == ["b1.c1", "b2.c2"]


def test_mirror_is_extension_only_from_island_count():
    # v4/v8: never push an index the island already has (first-seen would
    # file it as an alt and silently lose the victim's block there), and
    # never SKIP the index the island needs next — a skip orphans every
    # later block (monerod answers orphaned submits with status OK).
    a, i1, _ = _make_island_agent()
    a.strategy.fork = 6                     # everything committed: gate transparent
    a._island_heights = [4]                        # island count 4: needs index 4
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a._mirror_private_blocks(priv_height=6)        # miner count 6: indexes 0-5
    assert [c.args[0] for c in i1.submit_block.call_args_list] == ["p4", "p5"]
    assert a._mirrored_index == 6


def test_mine_after_height_gates_native_start():
    # v6: an eclipsed victim must not mine before its daemon has synced the
    # island chain (any pre-sync block forks genesis and first-seen keeps
    # that fork forever). Default 0 = ungated (every existing miner).
    a = _make_agent()
    a.native_started = False
    a.wallet_address = "addr"
    a.daemon_rpc.get_info.return_value = {"height": 1}
    a.daemon_rpc.start_mining.return_value = {"status": "OK"}
    a.attributes["mine_after_height"] = "3"
    assert a._native_try_start() is False          # below the gate: no mining
    a.daemon_rpc.start_mining.assert_not_called()
    a.daemon_rpc.get_info.return_value = {"height": 3}
    assert a._native_try_start() is True           # synced: mine away
    a.daemon_rpc.start_mining.assert_called_once()
    b = _make_agent()
    b.native_started = False
    b.wallet_address = "addr"
    b.daemon_rpc.start_mining.return_value = {"status": "OK"}
    assert b._native_try_start() is True           # default: ungated


def test_cash_out_releases_from_hash_verified_ancestor():
    # v11: the miner may sit on a stale branch the strategy's fork no longer
    # describes; the release must start where the chains actually agree.
    a, i1, _ = _make_island_agent()
    a.strategy.fork = 25                       # bookkeeping says 25
    a._island_heights = [50]
    a._released_index = 40
    # chains actually agree only through height 5
    def mine_blk(height):
        return {"blob": f"m{height}", "block_header": {"hash": f"mh{height}" if height > 5 else f"sh{height}"}}
    def pub_blk(height):
        return {"blob": f"p{height}", "block_header": {"hash": f"ph{height}" if height > 5 else f"sh{height}"}}
    a.daemon_rpc.get_info.return_value = {"height": 48}
    a.daemon_rpc.get_block.side_effect = mine_blk
    a.bridge_rpc.get_block.side_effect = pub_blk
    a.daemon_rpc.get_info.side_effect = [{"height": 48}, {"height": 48}]
    a._release_up_to = MagicMock()
    a.bridge_rpc.get_info.return_value = {"height": 48}   # bridge adopts fully
    fired = a._island_cash_out(pub_height=30, priv_height=48)
    assert fired is True
    a._release_up_to.assert_called_once_with(5, 47)       # from the TRUE ancestor
    assert a._released_index == 5                         # watermark reset to retry
    assert a.strategy.fork == 48


def test_cash_out_does_not_commit_without_adoption():
    # v11: a submitted branch the network does not adopt leaves fork and the
    # release watermark alone — the next tick re-releases the same range.
    a, i1, _ = _make_island_agent()
    a.strategy.fork = 10
    a._island_heights = [40]
    a.daemon_rpc.get_info.side_effect = [{"height": 38}, {"height": 38}]
    a.daemon_rpc.get_block.side_effect = lambda height: {
        "blob": f"m{height}", "block_header": {"hash": f"mh{height}"}}
    a.bridge_rpc.get_block.side_effect = lambda height: {
        "blob": f"p{height}", "block_header": {"hash": f"ph{height}"}}
    a._release_up_to = MagicMock()
    a.bridge_rpc.get_info.return_value = {"height": 12}   # bridge did NOT adopt
    assert a._island_cash_out(pub_height=12, priv_height=38) is False
    a._release_up_to.assert_called_once_with(0, 37)       # still released (retry path)
    assert a.strategy.fork == 10                          # NOT committed


def test_mirror_is_gated_at_strategy_fork():
    # v12 rest window: the island gets the committed prefix + the private
    # suffix ONLY — never honest blocks the miner adopted above the fork
    # (that stream made the victim race 9 h/s and lose every fork: v11).
    a, i1, _ = _make_island_agent()
    a.strategy.fork = 5
    a._island_heights = [2]                 # island needs indexes 2..
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a._mirror_private_blocks(priv_height=12)   # miner main is 12 tall (incl. honest)
    # pushes only indexes 2..4 (up to the fork, exclusive) — the private
    # suffix 5..11 stays OFF the island so the victim owns that range
    assert [c.args[0] for c in i1.submit_block.call_args_list] == ["p2", "p3", "p4"]
    assert a._mirrored_index == 5


def test_mirror_pushes_nothing_when_island_at_fork():
    a, i1, _ = _make_island_agent()
    a.strategy.fork = 5
    a._island_heights = [5]                 # island already at the fork
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a._mirror_private_blocks(priv_height=9)
    assert i1.submit_block.call_args_list == []


def test_island_mode_caps_honest_feed_at_fork_while_withholding():
    # v13: with islands, honest forwards into the miner stop at the fork —
    # otherwise the miner's main compounds (honest adoptions + its own
    # blocks) and the victim's branch can never overtake it (v12's stall).
    # Without islands the feed is unchanged (base behavior byte-identical).
    a, i1, _ = _make_island_agent()
    a.strategy.fork = 5                      # withholding: committed through 5
    a.bridge_rpc.get_block.side_effect = lambda height: {"blob": f"h{height}"}
    a.bridge_rpc.get_info.return_value = {"height": 6, "top_block_hash": "t6"}
    a.daemon_rpc.get_info.return_value = {"height": 8}   # priv 8 vs pub 6: a=3,h=1 -> withhold
    a._pull_island_blocks = MagicMock()
    a._mirror_private_blocks = MagicMock()
    a._island_cash_out = MagicMock(return_value=False)
    a.run_iteration()
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    # cap at fork 5 (exclusive); index 0 (genesis) is common to every daemon
    # and, since the 2026-09-26 start sync, never (re-)forwarded.
    assert submitted == ["h1", "h2", "h3", "h4"]
    # concession path: fork = pub re-opens the feed fully
    a.daemon_rpc.submit_block.reset_mock()
    a.strategy.fork = 6
    a.bridge_rpc.get_info.return_value = {"height": 7, "top_block_hash": "t7"}
    a.run_iteration()
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert "h5" in submitted and "h6" in submitted       # past the old fork now


# --- first-tick synchronisation on a shared (chain-snapshot) chain, 2026-09-26 ---

def _chain_mocks(a, common: dict, pub_extra: dict, priv_extra: dict):
    """get_block(height) on both daemons: `common` heights share a hash,
    `pub_extra` / `priv_extra` diverge; unknown heights raise like monerod."""
    def pub(height):
        h = pub_extra.get(height, common.get(height))
        if h is None:
            raise RPCError("out of range")
        return {"blob": f"pub{height}", "block_header": {"hash": h}}

    def priv(height):
        h = priv_extra.get(height, common.get(height))
        if h is None:
            raise RPCError("out of range")
        return {"blob": f"priv{height}", "block_header": {"hash": h}}
    a.bridge_rpc.get_block.side_effect = pub
    a.daemon_rpc.get_block.side_effect = priv


def test_first_tick_on_shared_chain_syncs_fork_and_watermarks():
    """With chain_snapshot every daemon boots on the same 336-block chain.
    The pre-fix first tick saw fork=0, i.e. a 337-block private branch TIED
    with a 337-block honest branch: ~700 already-have submits, and if the
    attacker found the next block first it was released at once (lead 1
    over a phantom honest branch) instead of withheld. The fork must start
    at the hash-verified common tip."""
    a = _make_agent()
    common = {h: f"c{h}" for h in range(0, 337)}
    _chain_mocks(a, common, {}, {})
    a.bridge_rpc.get_info.return_value = {"height": 337, "top_block_hash": "c336"}
    a.daemon_rpc.get_info.return_value = {"height": 337, "top_block_hash": "c336"}
    a.run_iteration()
    assert a.strategy.fork == 337
    assert a._forwarded_index == 336 and a._released_index == 336
    a.bridge_rpc.submit_block.assert_not_called()
    a.daemon_rpc.submit_block.assert_not_called()
    # Attacker finds the next block: h == 0 -> withhold, fork unmoved.
    _chain_mocks(a, common, {}, {337: "p337"})
    a.daemon_rpc.get_info.return_value = {"height": 338, "top_block_hash": "p337"}
    a.run_iteration()
    a.bridge_rpc.submit_block.assert_not_called()
    assert a.strategy.fork == 337


def test_first_tick_honest_already_ahead_forwards_only_new_blocks():
    """If honest blocks landed before the attacker's first tick, adopt them
    and forward exactly those — not the whole grafted prefix."""
    a = _make_agent()
    common = {h: f"c{h}" for h in range(0, 337)}
    _chain_mocks(a, common, {337: "h337", 338: "h338"}, {})
    a.bridge_rpc.get_info.return_value = {"height": 339, "top_block_hash": "h338"}
    a.daemon_rpc.get_info.return_value = {"height": 337, "top_block_hash": "c336"}
    a.run_iteration()
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["pub337", "pub338"]
    assert a.strategy.fork == 339
    a.bridge_rpc.submit_block.assert_not_called()


def test_first_tick_attacker_already_ahead_withholds():
    """A private block found before the first tick is a real lead of 1 over
    an honest branch of 0: withhold (pre-fix: released as a tie-break)."""
    a = _make_agent()
    common = {h: f"c{h}" for h in range(0, 337)}
    _chain_mocks(a, common, {}, {337: "p337"})
    a.bridge_rpc.get_info.return_value = {"height": 337, "top_block_hash": "c336"}
    a.daemon_rpc.get_info.return_value = {"height": 338, "top_block_hash": "p337"}
    a.run_iteration()
    a.bridge_rpc.submit_block.assert_not_called()
    assert a.strategy.fork == 337
    assert a._released_index == 336


def test_pull_island_growth_is_not_reported_as_reorg():
    """Review 2026-09-26: the rescan's high bound was `pulled` (the NEXT index
    needed), which is never in `seen`, so every island growth logged
    'island N reorg at height <tip>' and rescanned the window for nothing."""
    a, i1, _ = _make_island_agent()
    a.daemon_rpc.get_info.return_value = {"height": 0}
    chain = {0: "a0", 1: "a1", 2: "a2"}
    i1.get_info.return_value = {"height": 3, "top_block_hash": "a2"}
    i1.get_block.side_effect = lambda height: {"blob": f"b{height}.{chain[height]}",
                                               "block_header": {"hash": chain[height]}}
    a._pull_island_blocks()
    a.logger.reset_mock()
    i1.get_block.reset_mock()
    a.daemon_rpc.submit_block.reset_mock()
    chain[3] = "a3"                                                  # island grew by one
    i1.get_info.return_value = {"height": 4, "top_block_hash": "a3"}
    a._pull_island_blocks()
    assert [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list] == ["b3.a3"]
    assert not any("reorg" in str(c) for c in a.logger.info.call_args_list)
    fetched = sorted(c.kwargs.get("height", c.args[0] if c.args else None) for c in i1.get_block.call_args_list)
    assert fetched == [1, 2, 3]      # rescan covers the held window 1..2 plus the new block; never a phantom idx 3 mismatch


# --- rejection-aware attacker (2026-09-28) ---
# The strategy assumes every reveal wins. A bridge running the countermeasure
# rejects a late reveal and never announces it, so the textbook attacker kept
# racing a dead branch for up to ~50 blocks (results doc §6). With
# `reject_aware` the agent checks adoption after a cash-out reveal and, if the
# bridge's tip is not the attacker's, pops its branch and mines on the public
# chain.

def _reject_aware_agent():
    a = SelfishMinerAgent(
        agent_id="attacker-miner",
        attributes=[["strategy", "eyal_sirer"], ["bridge_agent", "attacker-bridge"],
                    ["reject_aware", "true"]],
    )
    a.logger = MagicMock()
    a.daemon_rpc = MagicMock()
    a.bridge_rpc = MagicMock()
    a.bridge_rpcs = [a.bridge_rpc]
    a.native_started = True
    a._native_run_iteration = MagicMock(return_value=1.0)
    a._ensure_strategy(0)
    return a


def test_reject_aware_attribute_defaults_off_and_parses():
    assert _make_agent().reject_aware is False
    assert _reject_aware_agent().reject_aware is True


def _withhold_then_reveal(a, bridge_adopts: bool):
    """Shared chain c0..c9 (count 10). Tick 1: the attacker holds p10,p11
    (a=2, h=0) and withholds. Tick 2: honest h10 lands (a=2, h=1), so ES
    reveals p10,p11. The bridge adopts them or keeps h10."""
    common = {h: f"c{h}" for h in range(10)}
    _chain_mocks(a, common, {}, {10: "p10", 11: "p11"})
    a.bridge_rpc.get_info.return_value = {"height": 10, "top_block_hash": "c9"}
    a.daemon_rpc.get_info.return_value = {"height": 12, "top_block_hash": "p11"}
    a.run_iteration()
    assert a.strategy.fork == 10
    public = {10: "p10", 11: "p11"} if bridge_adopts else {10: "h10"}
    _chain_mocks(a, common, public, {10: "p10", 11: "p11"})
    a.bridge_rpc.get_info.return_value = {"height": 12 if bridge_adopts else 11,
                                          "top_block_hash": "p11" if bridge_adopts else "h10"}
    # tick 2 reads the pre-release public height (honest h10 just landed)
    a.bridge_rpc.get_info.side_effect = [{"height": 11, "top_block_hash": "h10"},
                                         a.bridge_rpc.get_info.return_value]
    a.daemon_rpc.submit_block.reset_mock()
    a.daemon_rpc.pop_blocks.reset_mock()
    a.run_iteration()


def test_reject_aware_withholding_does_not_feed_honest_blocks_past_the_fork():
    # Honest blocks above the fork would sit in the miner's alt DB, and after a
    # concession pop monerod would refuse them as already-have.
    a = _reject_aware_agent()
    common = {h: f"c{h}" for h in range(10)}
    _chain_mocks(a, common, {10: "h10"}, {10: "p10", 11: "p11", 12: "p12"})
    a.bridge_rpc.get_info.return_value = {"height": 11, "top_block_hash": "h10"}
    a.daemon_rpc.get_info.return_value = {"height": 13, "top_block_hash": "p12"}
    a.run_iteration()                          # a=3, h=1: withhold
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert "pub10" not in submitted


def test_rejected_reveal_pops_the_branch_and_mines_on_the_public_chain():
    a = _reject_aware_agent()
    _withhold_then_reveal(a, bridge_adopts=False)
    released = [c.args[0] for c in a.bridge_rpc.submit_block.call_args_list]
    assert released == ["priv10", "priv11"]    # the reveal still went out
    a.daemon_rpc.pop_blocks.assert_called_once_with(2)
    names = [c[0] for c in a.daemon_rpc.method_calls]
    subs = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert subs == ["pub10"]                   # honest h10 forwarded once, after the pop
    assert names.index("pop_blocks") < names.index("submit_block")
    assert a.strategy.fork == 11               # conceded to the public chain
    assert a._released_index == 10 and a._forwarded_index == 10


def test_adopted_reveal_keeps_the_branch():
    a = _reject_aware_agent()
    _withhold_then_reveal(a, bridge_adopts=True)
    a.daemon_rpc.pop_blocks.assert_not_called()
    assert a.strategy.fork == 12


def test_without_reject_aware_a_rejected_reveal_is_not_noticed():
    # Legacy behavior stays byte-identical: no adoption check, no pop.
    a = _make_agent()
    _withhold_then_reveal(a, bridge_adopts=False)
    a.daemon_rpc.pop_blocks.assert_not_called()
    assert a.strategy.fork == 12


def test_rejected_reveal_with_failed_pop_leaves_state_alone():
    # If the pop fails the miner is still on its branch; moving the fork would
    # desynchronize the bookkeeping from the daemon.
    a = _reject_aware_agent()
    a.daemon_rpc.pop_blocks.side_effect = RPCError("pop_blocks status: Failed")
    _withhold_then_reveal(a, bridge_adopts=False)
    assert a.strategy.fork == 12
    assert [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list] == []
