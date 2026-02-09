#!/usr/bin/env python3
"""
log_processor.py - Intelligent log processing pipeline with fuzzy matching

This script processes log files using intelligent fuzzy matching to group similar entries,
providing a more meaningful summary of log content than simple deduplication.
"""

import os
import sys
import argparse
import re
import json
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Set
from pathlib import Path
import hashlib
import random
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Import error handling from existing module
from error_handling import log_info, log_warning, log_error, log_critical

# ===== PERFORMANCE OPTIMIZATIONS =====

# Simple rolling hash function for quick similarity pre-filtering
def rolling_hash(s: str, window_size: int = 10) -> Set[int]:
    """Calculate rolling hash values for string."""
    if len(s) < window_size:
        return {zlib.adler32(s.encode())}

    hashes = set()
    for i in range(len(s) - window_size + 1):
        window = s[i:i + window_size]
        hashes.add(zlib.adler32(window.encode()))
    return hashes

# Cache for normalized line patterns to avoid repeated work
_normalization_cache = {}

# ===== CONFIGURATION =====

# Default configuration values
DEFAULT_BASE_LOG_DIR = "/home/lever65/monerosim_dev/monerosim/shadow.data/hosts"
DEFAULT_PROCESSED_EXTENSION = ".processed_log"
DEFAULT_SIMILARITY_THRESHOLD = 0.90
DEFAULT_MIN_OCCURRENCES = 3
DEFAULT_CONTEXT_LINES = 10
DEFAULT_SAMPLE_STRATEGY = "smart"

# ===== NORMALIZATION PATTERNS =====

# Patterns for dynamic content that should be normalized
NORMALIZATION_PATTERNS = [
    # Transaction IDs (hexadecimal strings, 64 characters)
    (r'<[0-9a-f]{64}>', '<TRANSACTION_ID>'),
    # Block hashes (hexadecimal strings, 64 characters)
    (r'[0-9a-f]{64}', '<BLOCK_HASH>'),
    # IP addresses (IPv4)
    (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '<IP_ADDRESS>'),
    # Port numbers (common range)
    (r':[0-9]{2,5}', ':<PORT>'),
    # UUIDs
    (r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<UUID>'),
    # Timestamps (various formats)
    (r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?', '<TIMESTAMP>'),
    # Block heights (numbers after HEIGHT)
    (r'HEIGHT \d+', 'HEIGHT <BLOCK_HEIGHT>'),
    # Difficulty values (numbers after difficulty:)
    (r'difficulty:\s*\d+', 'difficulty: <DIFFICULTY>'),
    # Memory addresses
    (r'0x[0-9a-fA-F]+', '<MEMORY_ADDRESS>'),
    # Thread IDs
    (r'thread \d+', 'thread <THREAD_ID>'),
    # Connection IDs
    (r'INC\]|\bOUT\]', '<DIRECTION>'),
    # HTTP status codes
    (r'HTTP [0-9]+\.[0-9]+ [0-9]{3}', 'HTTP <VERSION> <STATUS_CODE>'),
    # RPC method calls
    (r'Calling RPC method [a-zA-Z_]+', 'Calling RPC method <METHOD_NAME>'),
    # File paths
    (r'/[a-zA-Z0-9/_.-]+(?:\.[a-zA-Z0-9]+)', '<FILE_PATH>'),
    # Numbers in general contexts (as last resort)
    (r'\b\d+\b', '<NUMBER>'),
]

# ===== CORE PROCESSING FUNCTIONS =====

def normalize_line(line: str) -> str:
    """
    Normalize a log line by removing/replacing dynamic content.

    Args:
        line: Raw log line

    Returns:
        Normalized log line
    """
    # Check cache first
    if line in _normalization_cache:
        return _normalization_cache[line]

    normalized = line

    # Remove timestamp at the beginning if present
    normalized = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?\s*', '', normalized)

    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    # Apply all normalization patterns
    for pattern, replacement in NORMALIZATION_PATTERNS:
        normalized = re.sub(pattern, replacement, normalized)

    # Cache the result
    _normalization_cache[line] = normalized
    return normalized

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Levenshtein distance
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def calculate_similarity_levenshtein(line1: str, line2: str) -> float:
    """
    Calculate similarity using Levenshtein distance.

    Args:
        line1: First string
        line2: Second string

    Returns:
        Similarity score between 0.0 and 1.0
    """
    # Normalize both lines first
    norm1 = normalize_line(line1)
    norm2 = normalize_line(line2)

    # If they're exactly the same after normalization, 100% similar
    if norm1 == norm2:
        return 1.0

    # If either is empty, 0% similar
    if len(norm1) == 0 or len(norm2) == 0:
        return 0.0

    # Calculate Levenshtein distance
    distance = levenshtein_distance(norm1, norm2)
    max_len = max(len(norm1), len(norm2))

    # Convert distance to similarity (0.0 - 1.0)
    similarity = 1.0 - (distance / max_len)
    return similarity

def smart_sample_lines(lines: List[str], chunk_size: int = 500, num_middle_chunks: int = 3) -> List[str]:
    """
    Smart sampling of lines from a large file with configurable chunking.

    Args:
        lines: List of all lines in the file
        chunk_size: Size of chunks to sample
        num_middle_chunks: Number of random chunks to sample from the middle

    Returns:
        Sampled lines
    """
    total_lines = len(lines)

    if total_lines <= 1000:
        # For small files, return all lines
        return lines

    # Take first and last chunks
    first_chunk = lines[:chunk_size]
    last_chunk = lines[-chunk_size:]

    # Generate random chunks from the middle
    middle_lines = lines[chunk_size:-chunk_size]
    middle_size = len(middle_lines)

    if middle_size > 0:
        # Sample specified number of random chunks from the middle
        num_chunks = min(num_middle_chunks, max(1, middle_size // chunk_size))
        sampled_middle = []

        for _ in range(num_chunks):
            if middle_size > chunk_size:
                start = random.randint(0, middle_size - chunk_size)
                sampled_middle.extend(middle_lines[start:start + chunk_size])
            else:
                sampled_middle.extend(middle_lines)

        # Combine all chunks
        result = first_chunk + last_chunk + sampled_middle
    else:
        # If no middle section, just use first and last
        result = first_chunk + last_chunk

    # Remove duplicates while preserving order
    seen = set()
    unique_result = []
    for line in result:
        if line not in seen:
            seen.add(line)
            unique_result.append(line)

    return unique_result

def fuzzy_group_lines(lines: List[str], similarity_threshold: float = 0.90) -> Dict[str, List[Tuple[int, str]]]:
    """
    Group similar lines using fuzzy matching.

    Args:
        lines: List of log lines
        similarity_threshold: Threshold for considering lines similar (0.0-1.0)

    Returns:
        Dictionary mapping normalized patterns to list of (index, original_line) tuples
    """
    # Normalize all lines
    normalized_lines = [(i, line, normalize_line(line)) for i, line in enumerate(lines)]

    # Precompute rolling hashes for quick filtering
    line_hashes = [(i, original_line, normalized_line, rolling_hash(normalized_line))
                  for i, original_line, normalized_line in normalized_lines]

    # Group similar lines using fuzzy matching
    groups = defaultdict(list)
    pattern_to_representative = {}  # Map patterns to their representative normalized line
    pattern_to_hash = {}  # Map patterns to their representative hash

    for i, original_line, normalized_line, line_hash in line_hashes:
        # Find the best matching group using hash similarity as a pre-filter
        best_group = None
        best_similarity = 0.0

        # Compare with representatives of existing groups using hash overlap as pre-filter
        for pattern, representative_hash in pattern_to_hash.items():
            # Quick hash overlap check to pre-filter candidates
            hash_overlap = len(line_hash.intersection(representative_hash)) / max(len(line_hash), 1)

            # Only do expensive Levenshtein calculation if hash overlap is promising
            if hash_overlap > 0.5:  # At least 50% hash overlap
                representative = pattern_to_representative[pattern]
                similarity = calculate_similarity_levenshtein(normalized_line, representative)
                if similarity >= similarity_threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_group = pattern

        # If we found a matching group, add to it
        if best_group is not None:
            groups[best_group].append((i, original_line))
        else:
            # Create a new group with this line as representative
            # Use the normalized line as the pattern key
            groups[normalized_line].append((i, original_line))
            pattern_to_representative[normalized_line] = normalized_line
            pattern_to_hash[normalized_line] = line_hash

    return groups

def process_log_content(lines: List[str], similarity_threshold: float = 0.90,
                       min_occurrences: int = 3, context_lines: int = 10) -> str:
    """
    Process log content with intelligent fuzzy matching.

    Args:
        lines: List of log lines
        similarity_threshold: Threshold for considering lines similar (0.0-1.0)
        min_occurrences: Minimum occurrences to consider a pattern significant
        context_lines: Number of context lines to preserve at start/end

    Returns:
        Processed log content as string
    """
    if not lines:
        return ""

    # Preserve first and last context lines verbatim
    total_lines = len(lines)
    preserved_start = lines[:context_lines] if total_lines > context_lines else lines
    preserved_end = lines[-context_lines:] if total_lines > context_lines and total_lines > 2 * context_lines else []

    # Process middle content with fuzzy matching
    if total_lines > 2 * context_lines:
        middle_lines = lines[context_lines:-context_lines]
    else:
        middle_lines = []

    # Group similar lines
    line_groups = fuzzy_group_lines(middle_lines, similarity_threshold)

    # Count pattern occurrences
    pattern_counts = Counter()
    for pattern, entries in line_groups.items():
        pattern_counts[pattern] = len(entries)

    # Identify significant patterns
    significant_patterns = {
        pattern for pattern, count in pattern_counts.items()
        if count >= min_occurrences
    }

    # Build output
    output_lines = []

    # Add preserved start lines
    output_lines.extend(preserved_start)

    # Add header for grouped patterns if we have any
    if significant_patterns:
        output_lines.append("")
        output_lines.append("=" * 60)
        output_lines.append("GROUPED SIMILAR LOG ENTRIES (with counts)")
        output_lines.append("=" * 60)
        output_lines.append("")

    # Process significant patterns
    processed_patterns = set()
    rare_lines = []

    # Sort patterns by count (descending) for consistent output
    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)

    for pattern, count in sorted_patterns:
        if pattern in significant_patterns and pattern not in processed_patterns:
            # Add pattern header with count
            output_lines.append(f"[COUNT: {count:4d}] Pattern: {pattern}")

            # Add some example lines (max 3)
            examples = line_groups[pattern][:3]
            for _, line in examples:
                # Only add non-empty lines
                if line.strip():
                    output_lines.append(f"    Example: {line.strip()}")

            output_lines.append("")
            processed_patterns.add(pattern)
        elif pattern not in processed_patterns:
            # Collect rare lines for separate section
            for _, line in line_groups[pattern]:
                if line.strip():
                    rare_lines.append(line)

    # Add rare/unique lines section
    if rare_lines:
        output_lines.append("=" * 60)
        output_lines.append("RARE/UNIQUE LOG ENTRIES (verbatim)")
        output_lines.append("=" * 60)
        output_lines.append("")

        # Preserve all rare lines verbatim
        output_lines.extend(rare_lines)

    # Add preserved end lines
    if preserved_end:
        output_lines.append("")
        output_lines.append("=" * 60)
        output_lines.append("END OF LOG (CONTEXT PRESERVED)")
        output_lines.append("=" * 60)
        output_lines.append("")
        output_lines.extend(preserved_end)

    return "\n".join(output_lines)

def process_single_log_file(file_path: str, similarity_threshold: float = 0.90,
                           min_occurrences: int = 3, context_lines: int = 10,
                           chunk_params: tuple = None) -> str:
    """
    Process a single log file.

    Args:
        file_path: Path to the log file
        similarity_threshold: Threshold for considering lines similar
        min_occurrences: Minimum occurrences for pattern significance
        context_lines: Number of context lines to preserve
        chunk_params: Tuple of (num_middle_chunks, chunk_size) for sampling, or None to process all lines

    Returns:
        Processed content as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line.rstrip('\n') for line in f.readlines()]
    except Exception as e:
        log_error("LOG_PROCESSOR", f"Failed to read file {file_path}: {e}")
        return ""

    if not lines:
        return ""

    # Apply chunking if specified, otherwise process all lines
    if chunk_params:
        num_middle_chunks, chunk_size = chunk_params
        sampled_lines = smart_sample_lines(lines, chunk_size, num_middle_chunks)
    else:
        sampled_lines = lines  # Process all lines

    # Process the content
    processed_content = process_log_content(
        sampled_lines,
        similarity_threshold,
        min_occurrences,
        context_lines
    )

    return processed_content

def find_log_files(base_dir: str, processed_extension: str) -> List[str]:
    """
    Find all log files that need processing.

    Scans per host directory so we can parallelize per-host work.
    """
    log_files = []

    try:
        # Enumerate host directories one level below base_dir
        if not os.path.isdir(base_dir):
            return log_files

        for host in sorted(os.listdir(base_dir)):
            host_dir = os.path.join(base_dir, host)
            if not os.path.isdir(host_dir):
                continue

            for root, _, files in os.walk(host_dir):
                for file in files:
                    # Skip already processed files
                    if file.endswith(processed_extension):
                        continue
                    # Include common log file types
                    if any(file.endswith(ext) for ext in ('.stdout', '.stderr', '.log', '.txt')):
                        log_files.append(os.path.join(root, file))
    except Exception as e:
        log_error("LOG_PROCESSOR", f"Error scanning for log files: {e}")

    return log_files

def _process_and_write(file_path: str,
                       processed_extension: str,
                       similarity_threshold: float,
                       min_occurrences: int,
                       context_lines: int,
                       dry_run: bool,
                       chunk_params: tuple = None) -> Tuple[str, bool, str]:
    """
    Worker-safe function: process a file and write its processed counterpart.
    Returns (file_path, success, message).
    """
    try:
        processed_content = process_single_log_file(
            file_path,
            similarity_threshold,
            min_occurrences,
            context_lines,
            chunk_params
        )

        if not processed_content:
            return file_path, False, "No processed content"

        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        new_filename = f"{filename}{processed_extension}"
        new_file_path = os.path.join(directory, new_filename)

        if dry_run:
            preview = processed_content[:500].replace("\n", "\\n")
            return file_path, True, f"DRY RUN to {new_file_path}; preview: {preview}..."
        else:
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            return file_path, True, f"Wrote {new_file_path}"
    except Exception as e:
        return file_path, False, f"Exception: {e}"


def _group_files_by_host(log_files: List[str], base_dir: str) -> Dict[str, List[str]]:
    """
    Group file paths by their immediate host directory under base_dir.
    """
    groups: Dict[str, List[str]] = defaultdict(list)
    base_dir = os.path.abspath(base_dir)

    for path in log_files:
        ap = os.path.abspath(path)
        # Expect path like .../shadow.data/hosts/<host>/...
        try:
            rel = os.path.relpath(ap, base_dir)
            parts = rel.split(os.sep)
            host = parts[0] if parts and parts[0] != ".." else "unknown"
        except Exception:
            host = "unknown"
        groups[host].append(path)

    return groups


def main():
    """Main entry point for the log processor."""
    parser = argparse.ArgumentParser(description="Intelligent Log Processing Pipeline with Fuzzy Matching")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_LOG_DIR,
                        help="Base directory containing log files")
    parser.add_argument("--processed-extension", default=DEFAULT_PROCESSED_EXTENSION,
                        help="Extension for processed files")
    parser.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD,
                        help="Similarity threshold for grouping (0.0-1.0)")
    parser.add_argument("--min-occurrences", type=int, default=DEFAULT_MIN_OCCURRENCES,
                        help="Minimum occurrences for pattern significance")
    parser.add_argument("--context-lines", type=int, default=DEFAULT_CONTEXT_LINES,
                        help="Number of context lines to preserve at start/end")
    parser.add_argument("--sample-strategy", default=DEFAULT_SAMPLE_STRATEGY,
                        choices=["smart", "all", "first_last"],
                        help="Sampling strategy for large files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without actually writing files")
    parser.add_argument("--max-workers", type=int, default=max(1, multiprocessing.cpu_count() // 2),
                        help="Maximum number of parallel workers (default: half of CPUs)")
    parser.add_argument("--per-host-parallelism", type=int, default=0,
                        help="If >0, also parallelize inside each host group up to this limit")
    parser.add_argument("--chunk", help="Enable chunking with format 'num_middle_chunks,chunk_size' (e.g., '3,500'). If not specified, processes entire file.")

    args = parser.parse_args()

    # Parse chunk parameters if provided
    chunk_params = None
    if args.chunk:
        try:
            num_middle_chunks, chunk_size = map(int, args.chunk.split(','))
            chunk_params = (num_middle_chunks, chunk_size)
        except ValueError:
            log_error("LOG_PROCESSOR", "Invalid --chunk format. Use 'num_middle_chunks,chunk_size'")
            return

    log_info("LOG_PROCESSOR", f"Starting log processing in: {args.base_dir}")
    chunk_info = f"chunking={chunk_params}" if chunk_params else "chunking=disabled (full processing)"
    log_info("LOG_PROCESSOR", f"Configuration: similarity_threshold={args.similarity_threshold}, "
                              f"min_occurrences={args.min_occurrences}, context_lines={args.context_lines}, "
                              f"max_workers={args.max_workers}, per_host_parallelism={args.per_host_parallelism}, {chunk_info}")

    # Find log files to process
    log_files = find_log_files(args.base_dir, args.processed_extension)

    if not log_files:
        log_warning("LOG_PROCESSOR", "No log files found to process")
        return

    log_info("LOG_PROCESSOR", f"Found {len(log_files)} log files to process")

    # Group by host to fan out per host
    groups = _group_files_by_host(log_files, args.base_dir)
    log_info("LOG_PROCESSOR", f"Discovered {len(groups)} host groups")

    processed_count = 0
    failed_count = 0

    # Strategy:
    # 1) Build a list of tasks as (file_path)
    # 2) Submit them to a process pool with bounded workers
    #    Optionally throttle per host if per_host_parallelism > 0

    # Optional: if per_host_parallelism is set, we chunk per host to limit intra-host concurrency
    tasks: List[str] = []
    if args.per_host_parallelism and args.per_host_parallelism > 0:
        for host, files in groups.items():
            for i in range(0, len(files), args.per_host_parallelism):
                tasks.extend(files[i:i + args.per_host_parallelism])
    else:
        for files in groups.values():
            tasks.extend(files)

    # Deduplicate tasks preserving order
    tasks = list(dict.fromkeys(tasks))

    log_info("LOG_PROCESSOR", f"Submitting {len(tasks)} processing tasks to pool")

    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {
            executor.submit(
                _process_and_write,
                file_path,
                args.processed_extension,
                args.similarity_threshold,
                args.min_occurrences,
                args.context_lines,
                args.dry_run,
                chunk_params
            ): file_path for file_path in tasks
        }

        for future in as_completed(future_map):
            file_path = future_map[future]
            try:
                fp, ok, msg = future.result()
                if ok:
                    log_info("LOG_PROCESSOR", f"Processed: {fp} -> {msg}")
                    processed_count += 1
                else:
                    log_warning("LOG_PROCESSOR", f"Skipped/empty: {fp} -> {msg}")
            except Exception as e:
                log_error("LOG_PROCESSOR", f"Failed to process {file_path}: {e}")
                failed_count += 1

    log_info("LOG_PROCESSOR", f"Log file processing complete. Processed {processed_count} files. Failures: {failed_count}.")


if __name__ == "__main__":
    main()