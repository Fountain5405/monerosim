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
    i1, i2 = MagicMock(), MagicMock()
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
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a._mirror_private_blocks(priv_height=2)
    assert [c.args[0] for c in i1.submit_block.call_args_list] == ["p1", "p2"]
    assert [c.args[0] for c in i2.submit_block.call_args_list] == ["p1", "p2"]
    assert a._mirrored_index == 2
    # Watermark: no re-push of already-mirrored heights
    i1.submit_block.reset_mock()
    a._mirror_private_blocks(priv_height=2)
    assert i1.submit_block.call_args_list == []


def test_mirror_resets_watermark_on_own_reorg():
    a, i1, _ = _make_island_agent()
    a._mirrored_index = 3
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a._mirror_private_blocks(priv_height=2)      # own chain shrank
    assert a._mirrored_index == 2
    assert [c.args[0] for c in i1.submit_block.call_args_list] == ["p1", "p2"]


def test_pull_submits_island_main_chain_into_miner():
    a, i1, i2 = _make_island_agent()
    i1.get_info.return_value = {"height": 2}
    i2.get_info.return_value = {"height": 1}
    i1.get_block.side_effect = lambda height: {"blob": f"v{height}"}
    i2.get_block.side_effect = lambda height: {"blob": f"w{height}"}
    a._pull_island_blocks()
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["v1", "v2", "w1"]
    assert a._island_pulled == [2, 1]
    # Next tick: only NEW heights are pulled
    a.daemon_rpc.submit_block.reset_mock()
    i1.get_info.return_value = {"height": 3}
    i1.get_block.side_effect = lambda height: {"blob": f"v{height}"}
    a._pull_island_blocks()
    assert [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list] == ["v3"]


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
