"""Bridge node for the selfish-mining apparatus.

A do-nothing agent whose only job is to run on the attacker's bridge daemon
host so BaseAgent.setup() registers the bridge's RPC endpoint (ip_addr,
daemon_rpc_port) in agent_registry.json. The SelfishMinerAgent looks the
bridge up there. The bridge daemon itself is a stock, fully-connected relay;
this agent issues no blockchain RPCs.
"""
import logging

from agents.base_agent import BaseAgent

BRIDGE_IDLE_INTERVAL_S = 60.0


class SelfishBridgeAgent(BaseAgent):
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)

    def _setup_agent(self):
        # No agent-specific setup; BaseAgent.setup() -> _register_self()
        # publishing this host's RPC endpoint is the entire point of this
        # agent. Required override: BaseAgent._setup_agent is abstract.
        pass

    def run_iteration(self) -> float:
        # Registered in setup(); nothing to do but stay alive.
        return BRIDGE_IDLE_INTERVAL_S


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
