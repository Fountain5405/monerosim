#!/usr/bin/env python3
"""
Compare two determinism fingerprints to verify simulation reproducibility.

Usage:
    python scripts/compare_determinism.py fingerprint1.json fingerprint2.json

Exit codes:
    0 - Fingerprints match (simulations are deterministic)
    1 - Fingerprints differ (simulations are NOT deterministic)
    2 - Error (file not found, invalid format, etc.)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any


def load_fingerprint(filepath: str) -> Dict:
    """Load a determinism fingerprint from a JSON file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fingerprint file not found: {filepath}")

    with open(path, 'r') as f:
        data = json.load(f)

    if 'version' not in data:
        raise ValueError(f"Invalid fingerprint format (missing version): {filepath}")

    return data


def compare_values(path: str, val1: Any, val2: Any) -> List[str]:
    """
    Recursively compare two values and return list of differences.
    """
    differences = []

    if type(val1) != type(val2):
        differences.append(f"{path}: type mismatch ({type(val1).__name__} vs {type(val2).__name__})")
        return differences

    if isinstance(val1, dict):
        all_keys = set(val1.keys()) | set(val2.keys())
        for key in sorted(all_keys):
            subpath = f"{path}.{key}" if path else key
            if key not in val1:
                differences.append(f"{subpath}: missing in first fingerprint")
            elif key not in val2:
                differences.append(f"{subpath}: missing in second fingerprint")
            else:
                differences.extend(compare_values(subpath, val1[key], val2[key]))

    elif isinstance(val1, list):
        if len(val1) != len(val2):
            differences.append(f"{path}: list length differs ({len(val1)} vs {len(val2)})")
            # Still compare what we can
            min_len = min(len(val1), len(val2))
            for i in range(min_len):
                differences.extend(compare_values(f"{path}[{i}]", val1[i], val2[i]))
        else:
            for i in range(len(val1)):
                differences.extend(compare_values(f"{path}[{i}]", val1[i], val2[i]))

    else:
        # Primitive value comparison
        if val1 != val2:
            differences.append(f"{path}: {val1} != {val2}")

    return differences


def compare_fingerprints(fp1: Dict, fp2: Dict) -> Tuple[bool, List[str]]:
    """
    Compare two fingerprints and return (match, differences).
    """
    # Check version compatibility
    if fp1.get('version') != fp2.get('version'):
        return False, [f"Version mismatch: {fp1.get('version')} vs {fp2.get('version')}"]

    differences = compare_values("", fp1, fp2)

    return len(differences) == 0, differences


def format_report(fp1_path: str, fp2_path: str, match: bool, differences: List[str]) -> str:
    """Format a comparison report."""
    lines = []
    lines.append("=" * 60)
    lines.append("DETERMINISM COMPARISON REPORT")
    lines.append("=" * 60)
    lines.append(f"Fingerprint 1: {fp1_path}")
    lines.append(f"Fingerprint 2: {fp2_path}")
    lines.append("")

    if match:
        lines.append("RESULT: MATCH - Simulations appear to be deterministic")
        lines.append("")
        lines.append("All structural properties match between the two runs:")
        lines.append("  - Same number of blocks mined")
        lines.append("  - Same block heights achieved")
        lines.append("  - Same per-node event counts")
        lines.append("  - Same propagation patterns")
    else:
        lines.append("RESULT: MISMATCH - Simulations are NOT deterministic")
        lines.append("")
        lines.append(f"Found {len(differences)} difference(s):")
        lines.append("")

        # Group differences by category for readability
        summary_diffs = []
        block_diffs = []
        node_diffs = []
        other_diffs = []

        for diff in differences:
            if diff.startswith("summary"):
                summary_diffs.append(diff)
            elif diff.startswith("block_heights") or diff.startswith("per_node_counts"):
                if "per_node_counts" in diff:
                    node_diffs.append(diff)
                else:
                    block_diffs.append(diff)
            else:
                other_diffs.append(diff)

        if summary_diffs:
            lines.append("Summary differences:")
            for diff in summary_diffs[:10]:  # Limit output
                lines.append(f"  - {diff}")
            if len(summary_diffs) > 10:
                lines.append(f"  ... and {len(summary_diffs) - 10} more")
            lines.append("")

        if block_diffs:
            lines.append("Block height differences:")
            for diff in block_diffs[:10]:
                lines.append(f"  - {diff}")
            if len(block_diffs) > 10:
                lines.append(f"  ... and {len(block_diffs) - 10} more")
            lines.append("")

        if node_diffs:
            lines.append("Per-node differences:")
            for diff in node_diffs[:20]:
                lines.append(f"  - {diff}")
            if len(node_diffs) > 20:
                lines.append(f"  ... and {len(node_diffs) - 20} more")
            lines.append("")

        if other_diffs:
            lines.append("Other differences:")
            for diff in other_diffs[:10]:
                lines.append(f"  - {diff}")
            if len(other_diffs) > 10:
                lines.append(f"  ... and {len(other_diffs) - 10} more")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_determinism.py <fingerprint1.json> <fingerprint2.json>")
        print("")
        print("Compare two determinism fingerprints to verify simulation reproducibility.")
        print("")
        print("Example workflow:")
        print("  1. Run simulation: ./run_sim.sh config.yaml")
        print("  2. Analyze: python scripts/analyze_success_criteria.py --fingerprint-file run1.json")
        print("  3. Run simulation again: ./run_sim.sh config.yaml")
        print("  4. Analyze: python scripts/analyze_success_criteria.py --fingerprint-file run2.json")
        print("  5. Compare: python scripts/compare_determinism.py run1.json run2.json")
        sys.exit(2)

    fp1_path = sys.argv[1]
    fp2_path = sys.argv[2]

    try:
        fp1 = load_fingerprint(fp1_path)
        fp2 = load_fingerprint(fp2_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"Error loading fingerprints: {e}")
        sys.exit(2)

    match, differences = compare_fingerprints(fp1, fp2)

    report = format_report(fp1_path, fp2_path, match, differences)
    print(report)

    # Exit with appropriate code
    sys.exit(0 if match else 1)


if __name__ == "__main__":
    main()
