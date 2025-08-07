#!/usr/bin/env python3
"""
Regular User Agent for Monerosim

This agent simulates regular users in the Monero network who perform transactions.
Currently a placeholder implementation that will be extended in future tasks.
"""

import logging
import time
from typing import Optional
from pathlib import Path

from .base_agent import BaseAgent


class RegularUserAgent(BaseAgent):
    """Agent that simulates regular user behavior in the Monero network"""
    
    def __init__(self, agent_id: str, tx_frequency: Optional[int] = None, hash_rate: Optional[int] = None, **kwargs):
        """
        Initialize the RegularUserAgent.
        
        Args:
            agent_id: Unique identifier for this agent
            tx_frequency: Transaction frequency in seconds
            hash_rate: Hash rate for mining (if applicable)
            **kwargs: Additional arguments passed to BaseAgent
        """
        # Call parent constructor
        super().__init__(agent_id=agent_id, tx_frequency=tx_frequency, hash_rate=hash_rate, **kwargs)
        
    def _setup_agent(self):
        """Agent-specific setup logic"""
        self.logger.info("RegularUserAgent initialized")
        # TODO: Implement actual setup logic for regular user agent
        
    def run_iteration(self) -> Optional[float]:
        """
        Single iteration of agent behavior.
        
        Returns:
            float: The recommended time to sleep (in seconds) before the next iteration.
        """
        self.logger.info("RegularUserAgent iteration")
        # TODO: Implement actual transaction logic here
        # Use tx_frequency if set, otherwise fall back to default
        sleep_duration = self.tx_frequency if self.tx_frequency is not None else 10.0
        return sleep_duration
        
    def _cleanup_agent(self):
        """Agent-specific cleanup logic"""
        self.logger.info("Cleaning up RegularUserAgent")


def main():
    """Main entry point for regular user agent"""
    parser = RegularUserAgent.create_argument_parser("Regular User Agent for Monerosim")
    
    # Add any agent-specific arguments here if needed
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent
    agent = RegularUserAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        rpc_host=args.rpc_host,
        agent_rpc_port=args.agent_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        log_level=args.log_level,
        attributes=args.attributes,
        tx_frequency=args.tx_frequency,
        hash_rate=args.hash_rate
    )
    
    agent.run()


if __name__ == "__main__":
    main()