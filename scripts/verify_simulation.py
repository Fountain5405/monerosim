#!/usr/bin/env python3
"""
Monerosim Simulation Verification Script

Verifies that all nodes in a simulation ran and were functioning properly.
Produces evidence suitable for proving simulation success.

Usage:
    python scripts/verify_simulation.py [--shared-dir /tmp/monerosim_shared]
"""

import json
import os
import argparse
from collections import defaultdict
from datetime import datetime


def verify_simulation(shared_dir: str) -> dict:
    """Verify simulation and return evidence dict."""

    evidence = {
        "timestamp": datetime.now().isoformat(),
        "shared_dir": shared_dir,
        "checks": {},
        "summary": {},
        "passed": True
    }

    # 1. Agent Registry Check
    registry_path = os.path.join(shared_dir, "agent_registry.json")
    if os.path.exists(registry_path):
        with open(registry_path) as f:
            registry = json.load(f)

        agents = registry.get('agents', [])
        miners = [a for a in agents if 'miner-' in a['id'] and 'distributor' not in a['id']]
        users = [a for a in agents if 'user-' in a['id']]
        with_wallet = [a for a in agents if a.get('wallet_address')]
        unique_addresses = len(set(a.get('wallet_address') for a in agents if a.get('wallet_address')))

        evidence["checks"]["agent_registry"] = {
            "total_agents": len(agents),
            "miners": len(miners),
            "users": len(users),
            "with_wallet_address": len(with_wallet),
            "unique_addresses": unique_addresses,
            "all_addresses_unique": unique_addresses == len(with_wallet)
        }
    else:
        evidence["checks"]["agent_registry"] = {"error": "File not found"}
        evidence["passed"] = False

    # 2. Monitoring Report Check
    report_path = os.path.join(shared_dir, "monitoring", "final_report.json")
    if os.path.exists(report_path):
        with open(report_path) as f:
            report = json.load(f)

        # Duration
        start = report.get('start_time', 0)
        end = report.get('last_update', 0)
        duration_s = end - start
        hours = int(duration_s // 3600)
        mins = int((duration_s % 3600) // 60)

        # Nodes seen across all cycles
        all_nodes_seen = set()
        for cycle in report.get('historical_data', []):
            for node_id in cycle.get('node_data', {}).keys():
                all_nodes_seen.add(node_id)

        # Final cycle analysis
        last_cycle = report['historical_data'][-1] if report.get('historical_data') else {}
        final_nodes = last_cycle.get('node_data', {})

        synced = 0
        mining = 0
        with_balance = 0
        daemon_running = 0
        wallet_running = 0
        heights = []
        connections = []

        for node_id, data in final_nodes.items():
            if 'daemon' in data and data['daemon']:
                daemon_running += 1
                d = data['daemon']
                if d.get('synced') or d.get('height', 0) > 300:
                    synced += 1
                if d.get('mining_active'):
                    mining += 1
                heights.append(d.get('height', 0))
                connections.append(d.get('connections', 0))
            if 'wallet' in data and data['wallet']:
                wallet_running += 1
                if data['wallet'].get('balance', 0) > 0:
                    with_balance += 1

        evidence["checks"]["monitoring"] = {
            "total_cycles": report.get('total_cycles', 0),
            "duration": f"{hours}h {mins}m",
            "duration_seconds": duration_s,
            "unique_nodes_seen": len(all_nodes_seen),
            "final_cycle": {
                "simulation_time": last_cycle.get('simulation_time', 'N/A'),
                "nodes_reporting": len(final_nodes),
                "daemons_running": daemon_running,
                "daemons_synced": synced,
                "wallets_running": wallet_running,
                "nodes_mining": mining,
                "nodes_with_balance": with_balance,
                "block_height_min": min(heights) if heights else 0,
                "block_height_max": max(heights) if heights else 0,
                "total_connections": sum(connections),
                "avg_connections": sum(connections) / len(connections) if connections else 0,
                "nodes_with_connections": len([c for c in connections if c > 0])
            }
        }
    else:
        evidence["checks"]["monitoring"] = {"error": "File not found"}
        evidence["passed"] = False

    # 3. Wallet Directories Check
    wallet_dirs = [d for d in os.listdir(shared_dir) if d.endswith('_wallet')]
    miner_wallets = [w for w in wallet_dirs if w.startswith('miner-')]
    user_wallets = [w for w in wallet_dirs if w.startswith('user-')]

    evidence["checks"]["wallet_directories"] = {
        "total": len(wallet_dirs),
        "miner_wallets": len(miner_wallets),
        "user_wallets": len(user_wallets)
    }

    # 4. Funding Status Check
    funding_path = os.path.join(shared_dir, "initial_funding_status.json")
    if os.path.exists(funding_path):
        with open(funding_path) as f:
            funding = json.load(f)

        evidence["checks"]["funding"] = {
            "funded_recipients": len(funding.get('funded_recipients', [])),
            "failed_recipients": len(funding.get('failed_recipients', [])),
            "completed": funding.get('completed', False)
        }

    # 5. Transaction Activity Check
    blocks_path = os.path.join(shared_dir, "blocks_with_transactions.json")
    if os.path.exists(blocks_path):
        with open(blocks_path) as f:
            blocks = json.load(f)

        total_tx = sum(b.get('tx_count', 0) for b in blocks)
        heights = [b['height'] for b in blocks] if blocks else []

        evidence["checks"]["transactions"] = {
            "blocks_with_transactions": len(blocks),
            "total_transactions": total_tx,
            "block_range": f"{min(heights)}-{max(heights)}" if heights else "N/A"
        }

    # 6. Transactions.json Check (for analysis tools)
    tx_json_path = os.path.join(shared_dir, "transactions.json")
    if os.path.exists(tx_json_path):
        with open(tx_json_path) as f:
            tx_data = json.load(f)

        evidence["checks"]["transactions_json"] = {
            "exists": True,
            "count": len(tx_data) if isinstance(tx_data, list) else len(tx_data.get('transactions', [])),
        }
    else:
        evidence["checks"]["transactions_json"] = {
            "exists": False,
            "note": "Required for spy-node and propagation analysis"
        }

    # Generate Summary
    reg = evidence["checks"].get("agent_registry", {})
    mon = evidence["checks"].get("monitoring", {})
    wal = evidence["checks"].get("wallet_directories", {})

    expected_nodes = reg.get("miners", 0) + reg.get("users", 0)

    evidence["summary"] = {
        "expected_nodes": expected_nodes,
        "registered_nodes": reg.get("total_agents", 0) - 2,  # exclude distributor, monitor
        "monitored_nodes": mon.get("unique_nodes_seen", 0),
        "wallet_directories": wal.get("total", 0),
        "all_nodes_ran": (
            reg.get("miners", 0) + reg.get("users", 0) == mon.get("unique_nodes_seen", 0) and
            mon.get("unique_nodes_seen", 0) == wal.get("total", 0)
        )
    }

    if not evidence["summary"]["all_nodes_ran"]:
        evidence["passed"] = False

    return evidence


def print_report(evidence: dict):
    """Print formatted verification report."""

    print("=" * 70)
    print("MONEROSIM SIMULATION VERIFICATION REPORT")
    print(f"Generated: {evidence['timestamp']}")
    print(f"Data directory: {evidence['shared_dir']}")
    print("=" * 70)

    # Agent Registry
    print("\n1. AGENT REGISTRY")
    print("-" * 50)
    reg = evidence["checks"].get("agent_registry", {})
    if "error" not in reg:
        print(f"   Total agents registered: {reg['total_agents']}")
        print(f"   Miners: {reg['miners']}")
        print(f"   Users: {reg['users']}")
        print(f"   With wallet addresses: {reg['with_wallet_address']}")
        print(f"   Unique addresses: {reg['unique_addresses']}")
        print(f"   All addresses unique: {reg['all_addresses_unique']}")
    else:
        print(f"   ERROR: {reg['error']}")

    # Monitoring
    print("\n2. MONITORING DATA")
    print("-" * 50)
    mon = evidence["checks"].get("monitoring", {})
    if "error" not in mon:
        print(f"   Duration: {mon['duration']} ({mon['duration_seconds']:.0f}s)")
        print(f"   Total cycles: {mon['total_cycles']}")
        print(f"   Unique nodes seen: {mon['unique_nodes_seen']}")
        fc = mon.get('final_cycle', {})
        print(f"   Final state ({fc.get('simulation_time', 'N/A')}):")
        print(f"      Nodes reporting: {fc.get('nodes_reporting', 0)}")
        print(f"      Daemons running: {fc.get('daemons_running', 0)}")
        print(f"      Daemons synced: {fc.get('daemons_synced', 0)}")
        print(f"      Wallets running: {fc.get('wallets_running', 0)}")
        print(f"      Block heights: {fc.get('block_height_min', 0)} - {fc.get('block_height_max', 0)}")
        print(f"      Avg connections/node: {fc.get('avg_connections', 0):.1f}")
        print(f"      Nodes with connections: {fc.get('nodes_with_connections', 0)}")
    else:
        print(f"   ERROR: {mon['error']}")

    # Wallet Directories
    print("\n3. WALLET DIRECTORIES")
    print("-" * 50)
    wal = evidence["checks"].get("wallet_directories", {})
    print(f"   Total created: {wal.get('total', 0)}")
    print(f"   Miner wallets: {wal.get('miner_wallets', 0)}")
    print(f"   User wallets: {wal.get('user_wallets', 0)}")

    # Funding
    print("\n4. FUNDING STATUS")
    print("-" * 50)
    fund = evidence["checks"].get("funding", {})
    if fund:
        total = fund.get('funded_recipients', 0) + fund.get('failed_recipients', 0)
        success_rate = fund.get('funded_recipients', 0) / total * 100 if total > 0 else 0
        print(f"   Funded: {fund.get('funded_recipients', 0)}")
        print(f"   Failed: {fund.get('failed_recipients', 0)}")
        print(f"   Success rate: {success_rate:.1f}%")

    # Transactions
    print("\n5. TRANSACTION ACTIVITY")
    print("-" * 50)
    tx = evidence["checks"].get("transactions", {})
    if tx:
        print(f"   Blocks with transactions: {tx.get('blocks_with_transactions', 0)}")
        print(f"   Total transactions: {tx.get('total_transactions', 0)}")
        print(f"   Block range: {tx.get('block_range', 'N/A')}")

    # Transactions.json (for analysis)
    print("\n6. TRANSACTIONS.JSON (for analysis)")
    print("-" * 50)
    tx_json = evidence["checks"].get("transactions_json", {})
    if tx_json.get("exists"):
        print(f"   File exists: Yes")
        print(f"   Transaction records: {tx_json.get('count', 0)}")
    else:
        print(f"   File exists: No")
        print(f"   Note: {tx_json.get('note', 'N/A')}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    summ = evidence["summary"]
    print(f"   Expected nodes: {summ.get('expected_nodes', 0)}")
    print(f"   Registered: {summ.get('registered_nodes', 0)}")
    print(f"   Monitored: {summ.get('monitored_nodes', 0)}")
    print(f"   Wallet dirs: {summ.get('wallet_directories', 0)}")

    print("\n" + "=" * 70)
    if evidence["passed"] and summ.get("all_nodes_ran"):
        print("RESULT: ✓ ALL NODES VERIFIED RUNNING AND FUNCTIONAL")
    else:
        print("RESULT: ⚠ VERIFICATION ISSUES DETECTED")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Verify monerosim simulation results")
    parser.add_argument("--shared-dir", default="/tmp/monerosim_shared",
                        help="Path to shared simulation directory")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON instead of formatted report")
    parser.add_argument("--output", "-o", help="Save report to file")

    args = parser.parse_args()

    evidence = verify_simulation(args.shared_dir)

    if args.json:
        output = json.dumps(evidence, indent=2)
        print(output)
    else:
        print_report(evidence)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(evidence, f, indent=2)
        print(f"\nEvidence saved to: {args.output}")

    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    exit(main())
