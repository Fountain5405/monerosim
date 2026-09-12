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
    agent.daemon_rpc.get_block_header_by_height.side_effect = lambda h: {"hash": f"h{h}"}
    written = {}
    agent.write_shared_state = lambda name, data: written.__setitem__(name, data)
    agent._cleanup_agent()
    assert written["canonical_chain.json"]["chain"] == [
        {"height": 1, "hash": "h1"},
        {"height": 2, "hash": "h2"},
    ]
    assert written["canonical_chain.json"]["observer"] == "attacker-bridge"
