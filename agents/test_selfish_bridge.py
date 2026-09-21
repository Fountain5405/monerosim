from unittest.mock import MagicMock

from agents.selfish_bridge import SelfishBridgeAgent


def test_run_iteration_returns_long_idle_and_does_no_rpc():
    agent = SelfishBridgeAgent(agent_id="attacker-bridge")
    # A bare instance must not touch RPC in run_iteration.
    interval = agent.run_iteration()
    assert isinstance(interval, float)
    assert interval >= 30.0


def test_is_base_agent_subclass_so_it_registers():
    from agents.base_agent import BaseAgent
    assert issubclass(SelfishBridgeAgent, BaseAgent)
    # setup() -> _register_self is inherited, not overridden away.
    assert SelfishBridgeAgent.setup is BaseAgent.setup


def test_cleanup_agent_dumps_canonical_chain():
    agent = SelfishBridgeAgent(agent_id="attacker-bridge")
    agent.logger = MagicMock()
    agent.daemon_rpc = MagicMock()
    agent.daemon_rpc.get_info.return_value = {"height": 3}   # top index 2 -> heights 1,2
    agent.daemon_rpc.get_block_header_by_height.side_effect = lambda h: {"hash": f"h{h}", "timestamp": 1000 + h}
    written = {}
    agent.write_shared_state = lambda name, data: written.__setitem__(name, data)
    agent._cleanup_agent()
    # Per-agent filename (review C3): each bridge writes its own, no clobber.
    # Each entry carries the block timestamp for join-free time bucketing.
    assert written["canonical_chain_attacker-bridge.json"]["chain"] == [
        {"height": 1, "hash": "h1", "timestamp": 1001},
        {"height": 2, "hash": "h2", "timestamp": 1002},
    ]
    assert written["canonical_chain_attacker-bridge.json"]["observer"] == "attacker-bridge"


def test_plain_bridge_stays_idle():
    a = SelfishBridgeAgent(agent_id="attacker-bridge")
    a.logger = MagicMock()
    assert a.victim_agent_ids == []
    assert a.run_iteration() == 60.0


def test_island_relay_pushes_and_pulls(monkeypatch):
    a = SelfishBridgeAgent(agent_id="attacker-island",
                           attributes=[["victims", "victim-001"]])
    a.logger = MagicMock()
    a.daemon_rpc = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "victim-001", "ip_addr": "10.0.0.5", "daemon_rpc_port": 18081}]})
    a.daemon_rpc.get_info.return_value = {"height": 2}   # island count: indexes 0,1
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"i{height}"}
    v = MagicMock()
    v.get_info.side_effect = [{"height": 0}, {"height": 1}, {"height": 1}]
    a.victim_rpcs = [v]                  # injected: never a real HTTP client
    a._victim_connected = {"victim-001"}
    v.get_block.side_effect = lambda height: {"blob": f"v{height}"}
    a.run_iteration()                     # pushes island indexes 0,1; victim empty
    pushed = [c.args[0] for c in v.submit_block.call_args_list]
    assert pushed == ["i0", "i1"]
    assert a.daemon_rpc.submit_block.call_args_list == []   # nothing to pull yet
    assert a.run_iteration() == 1.0       # relay cadence; victim now count 1
    island_got = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert island_got == ["v0"]           # victim's block pulled into the island
    # steady state: nothing new either way
    v.submit_block.reset_mock()
    a.daemon_rpc.submit_block.reset_mock()
    a.run_iteration()
    assert v.submit_block.call_args_list == []
    assert a.daemon_rpc.submit_block.call_args_list == []


def test_island_relay_resets_watermarks_on_reorg():
    a = SelfishBridgeAgent(agent_id="attacker-island",
                           attributes=[["victims", "victim-001"]])
    a.logger = MagicMock()
    a.daemon_rpc = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "victim-001", "ip_addr": "10.0.0.5", "daemon_rpc_port": 18081}]})
    a._pushed_index = 5
    a.daemon_rpc.get_info.return_value = {"height": 4}    # island chain shrank: count 4
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"r{height}"}
    v = MagicMock()
    v.get_info.return_value = {"height": 0}
    a.victim_rpcs = [v]
    a._victim_connected = {"victim-001"}
    a.run_iteration()
    # re-pushes indexes 0..3 from genesis after the shrink
    assert [c.args[0] for c in v.submit_block.call_args_list] == ["r0", "r1", "r2", "r3"]
