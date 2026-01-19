#!/usr/bin/env python3
"""
Benchmark script for testing AI config generator across different LLMs.

Usage:
    python -m scripts.ai_config.benchmark [--model MODEL] [--output results.json]

Run this script, then switch models and run again to compare.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .generator import ConfigGenerator, LLMProvider


# Test prompts organized by difficulty/type
BENCHMARK_PROMPTS = {
    # Tier 1: Basic - should all pass easily
    "basic_1": "5 miners and 20 users",
    "basic_2": "small test with 2 miners",
    "basic_3": "3 miners and 10 users for 6 hours",

    # Tier 2: Specific requirements
    "specific_1": "7 miners with hashrates favoring the first 3, and 100 users that start transacting after 3 hours",
    "specific_2": "simulation that runs for 24 hours with 50 users doing infrequent transactions every 5 minutes",
    "specific_3": "3 miners where one has 50% hashrate and the others split the rest equally",
    "specific_4": "10 miners all with equal hashrate and 200 users",

    # Tier 3: Scenario types
    "upgrade_1": "network upgrade where miners upgrade first, then users 30 minutes later",
    "upgrade_2": "upgrade scenario with 30 nodes transitioning from monerod-v1 to monerod-v2",
    "spy_1": "12 spy nodes watching a network of 4 miners and 30 users",
    "spy_2": "spy nodes that only monitor miners, not regular users",

    # Tier 4: Complex combinations
    "complex_1": "upgrade scenario with spy nodes monitoring the network before and after the upgrade",
    "complex_2": "large network with 15 miners, 200 users, and 20 spy nodes running for 48 hours",
    "complex_3": "stress test where users transact every 10 seconds after a long 8-hour bootstrap period",

    # Tier 5: Wishy-washy natural language (real user requests)
    "natural_1": "I want to run a 24 hour simulation where we have 5 miners and 100 users initially, and then halfway through the simulation a bunch of monerod-v2 nodes come online, and there are 10 miners in the new group that cause the network hashrate to double",
    "natural_2": "set up a test network with a few miners and maybe like 50 users, nothing fancy just want to see some transactions happening",
    "natural_3": "I need to test how the network behaves when there's a dominant miner, let's say one guy has most of the hashpower and everyone else is small",
    "natural_4": "can you make a config where we simulate a busy network? lots of users sending transactions frequently, running for a whole day",
    "natural_5": "spy node setup - I want to watch what's happening on a small test network, maybe 3 or 4 miners and some users",
    "natural_6": "testing an upgrade scenario where not everyone upgrades at the same time, some nodes are slow to update",
    "natural_7": "medium sized simulation, something reasonable for testing, with miners and users doing normal stuff",
}


def run_benchmark(model_name: str = None, output_file: str = None, prompts: list = None):
    """
    Run benchmark tests and collect results.

    Args:
        model_name: Name to identify this model in results
        output_file: Where to save results JSON
        prompts: List of prompt keys to run (default: all)
    """
    # Get model info from environment
    base_url = os.environ.get('OPENAI_BASE_URL', 'unknown')
    actual_model = os.environ.get('AI_CONFIG_MODEL', model_name or 'unknown')

    if not model_name:
        model_name = actual_model

    print(f"\n{'='*60}")
    print(f"AI Config Generator Benchmark")
    print(f"{'='*60}")
    print(f"Model: {model_name}")
    print(f"Base URL: {base_url}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Create provider and generator
    provider = LLMProvider(
        model=actual_model,
        base_url=base_url,
    )

    generator = ConfigGenerator(
        provider=provider,
        max_attempts=5,
        verbose=False  # Quiet mode for benchmarking
    )

    # Select prompts to run
    if prompts:
        test_prompts = {k: v for k, v in BENCHMARK_PROMPTS.items() if k in prompts}
    else:
        test_prompts = BENCHMARK_PROMPTS

    # Results storage
    results = {
        "model": model_name,
        "base_url": base_url,
        "timestamp": datetime.now().isoformat(),
        "tests": {},
        "summary": {
            "total": len(test_prompts),
            "passed": 0,
            "failed": 0,
            "total_time": 0,
            "total_attempts": 0,
        }
    }

    # Run each test
    for i, (test_id, prompt) in enumerate(test_prompts.items(), 1):
        print(f"\n[{i}/{len(test_prompts)}] Test: {test_id}")
        print(f"  Prompt: {prompt[:70]}{'...' if len(prompt) > 70 else ''}")

        start_time = time.time()

        try:
            # Generate config (don't save to file)
            result = generator.generate(
                user_request=prompt,
                output_file=f"/tmp/benchmark_{test_id}.yaml",
                save_scenario=None
            )

            elapsed = time.time() - start_time

            test_result = {
                "prompt": prompt,
                "success": result.success,
                "attempts": result.attempts,
                "time_seconds": round(elapsed, 2),
                "errors": result.errors if not result.success else [],
            }

            if result.success and result.validation_report:
                test_result["validation"] = {
                    "miners": result.validation_report.miner_count,
                    "users": result.validation_report.user_count,
                    "spy_nodes": result.validation_report.spy_count,
                    "warnings": len(result.validation_report.warnings),
                }
                print(f"  ✓ PASS ({result.attempts} attempts, {elapsed:.1f}s)")
                print(f"    → {result.validation_report.miner_count} miners, "
                      f"{result.validation_report.user_count} users, "
                      f"{result.validation_report.spy_count} spy nodes")
                results["summary"]["passed"] += 1
            else:
                print(f"  ✗ FAIL ({result.attempts} attempts, {elapsed:.1f}s)")
                if result.errors:
                    print(f"    → Error: {result.errors[-1][:80]}")
                results["summary"]["failed"] += 1

            results["summary"]["total_attempts"] += result.attempts
            results["summary"]["total_time"] += elapsed

        except Exception as e:
            elapsed = time.time() - start_time
            test_result = {
                "prompt": prompt,
                "success": False,
                "attempts": 0,
                "time_seconds": round(elapsed, 2),
                "errors": [str(e)],
                "exception": True,
            }
            print(f"  ✗ EXCEPTION: {e}")
            results["summary"]["failed"] += 1

        results["tests"][test_id] = test_result

    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: {model_name}")
    print(f"{'='*60}")
    print(f"  Passed: {results['summary']['passed']}/{results['summary']['total']}")
    print(f"  Failed: {results['summary']['failed']}/{results['summary']['total']}")
    print(f"  Total attempts: {results['summary']['total_attempts']}")
    print(f"  Total time: {results['summary']['total_time']:.1f}s")
    print(f"  Avg time per test: {results['summary']['total_time']/len(test_prompts):.1f}s")
    print(f"{'='*60}\n")

    # Save results
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = Path(f"benchmark_results_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {output_path}")

    return results


def compare_results(*result_files):
    """Compare results from multiple benchmark runs."""
    all_results = []
    for f in result_files:
        with open(f) as fp:
            all_results.append(json.load(fp))

    print(f"\n{'='*70}")
    print("COMPARISON")
    print(f"{'='*70}")

    # Header
    models = [r["model"] for r in all_results]
    print(f"{'Test':<20} " + " ".join(f"{m:<15}" for m in models))
    print("-" * 70)

    # Get all test IDs
    all_tests = set()
    for r in all_results:
        all_tests.update(r["tests"].keys())

    for test_id in sorted(all_tests):
        row = f"{test_id:<20} "
        for r in all_results:
            if test_id in r["tests"]:
                t = r["tests"][test_id]
                status = "✓" if t["success"] else "✗"
                row += f"{status} ({t['attempts']}att, {t['time_seconds']:.0f}s)  "
            else:
                row += f"{'N/A':<15} "
        print(row)

    print("-" * 70)

    # Summary row
    row = f"{'TOTAL':<20} "
    for r in all_results:
        s = r["summary"]
        row += f"{s['passed']}/{s['total']} ({s['total_time']:.0f}s)     "
    print(row)
    print(f"{'='*70}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark AI config generator")
    parser.add_argument("--model", "-m", help="Model name for labeling results")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--prompts", "-p", nargs="+", help="Specific prompt IDs to run")
    parser.add_argument("--compare", "-c", nargs="+", help="Compare result files")
    parser.add_argument("--list", "-l", action="store_true", help="List available prompts")

    args = parser.parse_args()

    if args.list:
        print("\nAvailable benchmark prompts:")
        print("-" * 40)
        for test_id, prompt in BENCHMARK_PROMPTS.items():
            print(f"  {test_id}: {prompt[:50]}...")
        return 0

    if args.compare:
        compare_results(*args.compare)
        return 0

    # Check for LLM config
    if not os.environ.get('OPENAI_BASE_URL'):
        print("Error: OPENAI_BASE_URL not set", file=sys.stderr)
        print("Set environment variables or run interactive mode first", file=sys.stderr)
        return 1

    run_benchmark(
        model_name=args.model,
        output_file=args.output,
        prompts=args.prompts
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
