"""
Funding-cycle helpers for MinerDistributorAgent.

Most of the funding orchestration (initial funding state machine, batch
processing, retry/failover) stays as methods on MinerDistributorAgent
because it mutates several pieces of agent state in lockstep. This module
holds the genuinely free-standing pieces: pre-tx balance fitting and batch
partitioning.
"""

import logging
from typing import Any, Dict, List

from ..monero_rpc import WalletRPC
from ..shared_utils import atomic_to_xmr


def fit_batch_to_unlocked_balance(
    miner: Dict[str, Any],
    batch_agents: List[Dict[str, Any]],
    out_per_tx: int,
    output_amount: float,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """
    Trim ``batch_agents`` so the resulting funding tx fits in the miner's
    unlocked balance. Returns the (possibly empty, possibly shorter) list.

    Background: a funding cycle batch is ``len(batch_agents) *
    md_out_per_tx * md_output_amount`` XMR. If the miner has only one or
    two unlocked coinbase outputs (~35 XMR each in this sim), an 80 XMR
    request fails with "Insufficient unlocked funds" and that miner is
    excluded for the cycle. With a few unlucky Poisson draws, a miner
    (e.g. miner-002 under simulation_seed=12345) can stay in this state
    for the entire run and emit zero txs. Shrinking the batch to fit
    what's actually unlocked lets the miner contribute partial funding
    rather than nothing.

    On RPC error we conservatively return the original batch unchanged
    — let _send_batch_transaction's existing error path handle it.
    """
    try:
        miner_rpc = WalletRPC(host=miner['ip_addr'], port=miner['wallet_rpc_port'])
        balance_info = miner_rpc.get_balance()
        unlocked_atomic = (balance_info or {}).get('unlocked_balance', 0)
        unlocked_xmr = atomic_to_xmr(unlocked_atomic)
    except Exception as e:
        logger.debug(
            f"Could not query unlocked balance for {miner.get('agent_id')} "
            f"before funding cycle: {e}; sending full batch"
        )
        return batch_agents

    per_recipient = out_per_tx * output_amount
    if per_recipient <= 0:
        return batch_agents

    # 5% headroom for tx fees; we don't know the exact fee in advance.
    usable_xmr = unlocked_xmr / 1.05
    max_fit = int(usable_xmr // per_recipient)
    if max_fit >= len(batch_agents):
        return batch_agents

    if max_fit <= 0:
        logger.info(
            f"Miner {miner.get('agent_id')} has {unlocked_xmr:.6f} XMR unlocked, "
            f"insufficient for any recipient ({per_recipient} XMR each); "
            f"will fail over"
        )
        return []

    logger.info(
        f"Miner {miner.get('agent_id')} has {unlocked_xmr:.6f} XMR unlocked; "
        f"shrinking batch from {len(batch_agents)} to {max_fit} recipients to fit"
    )
    return batch_agents[:max_fit]
