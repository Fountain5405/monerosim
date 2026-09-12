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
