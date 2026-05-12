"""
run_sim_helpers.py - Python helpers extracted from run_sim.sh.

run_sim.sh used to embed a dozen non-trivial `python3 -c "..."` heredocs for
YAML parsing, JSON parsing, math, and stats. Each was a separate subprocess
with implicit dependencies on PyYAML, json, statistics, etc., and none were
testable in isolation. This module collects the substantial heredocs behind
a single argparse subcommand CLI.

Each subcommand prints to stdout exactly what the original heredoc printed,
because run_sim.sh consumes the output via `$(...)` command substitution and
is sensitive to whitespace/format.

Usage (from run_sim.sh):
    python3 scripts/run_sim_helpers.py <subcommand> <args...>

Trivial heredocs (single-line `print(f'...')` formatters, simple max/min
arithmetic) are intentionally left inline in run_sim.sh — extracting them
adds subprocess and import overhead without a readability or testability
benefit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterable


# ============================================================
# Helpers: ramdisk math
# ============================================================
def cmd_estimate_ramdisk_mb(args: argparse.Namespace) -> int:
    """Estimate ramdisk size (MB) needed for monerod LMDBs over the sim duration.

    Per-host: 100 MB base + 10 MB per simulated hour. Min 2 GB total.
    Replaces the heredoc in `estimate_ramdisk_mb()` of run_sim.sh.
    """
    total = args.total_monerods
    hours = args.sim_hours
    per_host = 100 + (10 * hours)
    est = max(2048, total * per_host)
    print(int(est))
    return 0


# ============================================================
# Helpers: YAML config parsing
# ============================================================
def cmd_rewrite_daemon_data_dir(args: argparse.Namespace) -> int:
    """Read a config YAML, set general.daemon_data_dir, write to dest.

    Replaces the heredoc in `setup_ramdisk()` of run_sim.sh.
    """
    import yaml  # imported lazily so help text works without PyYAML
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault('general', {})['daemon_data_dir'] = args.daemon_data_dir
    with open(args.dest, 'w') as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
    return 0


def cmd_extract_stop_time(args: argparse.Namespace) -> int:
    """Print the raw `general.stop_time` value from a config YAML.

    Replaces the heredoc in `preflight_checks()` (STOP_TIME_RAW lookup).
    """
    import yaml
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    st = cfg.get('general', {}).get('stop_time', '')
    print(st)
    return 0


def cmd_config_summary(args: argparse.Namespace) -> int:
    """Print agent counts as a single space-separated line.

    Format (consumed by `read -r CFG_TOTAL CFG_MINERS CFG_USERS CFG_RELAYS CFG_FALLBACK_SEEDS`):
        <total> <miners> <users> <relays> <fb_seeds>

    Replaces the heredoc in `preflight_checks()` (CONFIG_SUMMARY lookup).
    """
    import yaml
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    meta = cfg.get('metadata', {})
    agents_meta = meta.get('agents', {})
    agents = cfg.get('agents', {})
    miners = agents_meta.get(
        'miners',
        sum(1 for a in agents if a.startswith('miner-0') or a.startswith('miner-1')),
    )
    users = agents_meta.get('users', sum(1 for a in agents if a.startswith('user-')))
    total = agents_meta.get('total', len(agents))
    relays = sum(1 for a in agents if a.startswith('relay-'))
    fb_mode = (cfg.get('general', {}).get('fallback_seeds') or 'auto').lower()
    custom_seeds = sum(1 for a in agents if a.startswith('monero-seed-'))
    if fb_mode == 'off':
        fb_seeds = 0
    elif fb_mode == 'custom':
        fb_seeds = custom_seeds
    else:
        fb_seeds = 6
    print(f'{total} {miners} {users} {relays} {fb_seeds}')
    return 0


# ============================================================
# Helpers: disk usage estimator (preflight_checks)
# ============================================================
def _disk_kb(path: str) -> float:
    """Sum st_blocks * 512 for every file under `path`, return KB.

    Use `st_blocks * 512` (actual disk allocation) instead of `st_size` so
    sparse LMDB files (1 GB apparent / few MB allocated) are sized correctly.
    """
    total = 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            try:
                total += os.stat(os.path.join(dp, fn)).st_blocks * 512
            except (OSError, FileNotFoundError):
                pass
    return total / 1024


def cmd_estimate_disk_mb(args: argparse.Namespace) -> int:
    """Estimate disk usage (MB) for the upcoming run.

    Walks `archive_dir` to learn per-host-type rates from the most recent
    completed run. Falls back to conservative defaults if no history exists.

    Prints estimated MB to stdout (consumed by run_sim.sh as `$(...)`).
    Prints `RATES:<json>|SOURCE:<text>` to stderr for the log message.

    Replaces the heredoc in `check_disk_space()` of run_sim.sh.
    """
    # Default rates (MB/host/hr) — conservative estimates that include logs +
    # blockchain. monerod at log-level=monitor on a 1k-node net writes ~10-30 MB
    # of bitmonero.log per host-day; LMDB grows ~50 MB/host-day at chain tip.
    defaults = {'miner': 4.0, 'user': 2.0, 'relay': 1.25, 'other': 0.5}

    # Try to learn rates from previous runs. We aggregate per-host disk usage
    # across THREE archive subdirs:
    #   1. shadow.data/hosts/<host>/             (shadow shim/stderr/stdout)
    #   2. daemon_logs/monero-<host>/            (bitmonero.log — usually dominant)
    #   3. blockchain/monero-<host>/             (LMDB snapshot — sampled hosts only)
    # Without (2) and (3) the estimate is ~5-10x too low.
    archive_dir = args.archive_dir
    learned: dict[str, float] = {}
    sample_hours = 0
    listing: Iterable[str] = (
        sorted(os.listdir(archive_dir), reverse=True)
        if os.path.isdir(archive_dir)
        else []
    )
    for run_name in listing:
        run_path = os.path.join(archive_dir, run_name)
        hosts_dir = os.path.join(run_path, 'shadow.data', 'hosts')
        daemon_logs_dir = os.path.join(run_path, 'daemon_logs')
        blockchain_dir = os.path.join(run_path, 'blockchain')
        cfg_path = os.path.join(run_path, 'input_config.yaml')
        if not os.path.isdir(hosts_dir) or not os.path.isfile(cfg_path):
            continue
        # Get sim duration from config
        try:
            import yaml
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            st = cfg.get('general', {}).get('stop_time', '')
            # Parse duration
            h = 0
            m = re.match(r'(\d+)h', str(st))
            if m:
                h = int(m.group(1))
            m2 = re.match(r'(\d+)$', str(st))
            if m2:
                h = int(m2.group(1)) / 3600
            if h <= 0:
                continue
        except Exception:
            continue
        # Measure per-type rates. shadow.data + daemon_logs are always per-host;
        # blockchain is sampled (only a few hosts archived per --archive-blockchain),
        # so we average separately and add a per-host blockchain rate by type.
        by_type_log: dict[str, list[float]] = {}
        by_type_chain: dict[str, list[float]] = {}
        for host in os.listdir(hosts_dir):
            host_path = os.path.join(hosts_dir, host)
            if not os.path.isdir(host_path):
                continue
            size_kb = _disk_kb(host_path)
            # bitmonero.log lives under daemon_logs/monero-<host>/ post-archive
            log_path = os.path.join(daemon_logs_dir, 'monero-' + host)
            if os.path.isdir(log_path):
                size_kb += _disk_kb(log_path)
            # LMDB only archived for sampled hosts
            chain_path = os.path.join(blockchain_dir, 'monero-' + host)
            chain_kb = _disk_kb(chain_path) if os.path.isdir(chain_path) else None

            if host.startswith('miner-'):
                t = 'miner'
            elif host.startswith('user-'):
                t = 'user'
            elif host.startswith('relay-'):
                t = 'relay'
            else:
                t = 'other'
            by_type_log.setdefault(t, []).append(size_kb)
            if chain_kb is not None:
                by_type_chain.setdefault(t, []).append(chain_kb)

        for t, sizes in by_type_log.items():
            avg_mb = (sum(sizes) / len(sizes)) / 1024
            # Add per-type blockchain average if we have any sampled hosts of this type
            chain_sizes = by_type_chain.get(t, [])
            if chain_sizes:
                avg_mb += (sum(chain_sizes) / len(chain_sizes)) / 1024
            rate = avg_mb / h
            if t not in learned or len(sizes) > 10:  # prefer runs with more samples
                learned[t] = rate
        sample_hours = h
        break  # use most recent run

    rates = {**defaults, **learned}
    source = 'learned from previous run' if learned else 'default estimates'

    miners = args.num_miners
    users = args.num_users
    relays = args.num_relays
    others = max(0, args.num_hosts - miners - users - relays)
    hours = args.sim_hours
    margin = 1.2

    est = (
        miners * rates['miner']
        + users * rates['user']
        + relays * rates['relay']
        + others * rates['other']
    ) * hours * margin
    print(f'{est:.0f}')

    # Print breakdown to stderr for the log message
    print(f'RATES:{json.dumps(rates)}|SOURCE:{source}', file=sys.stderr)
    return 0


# ============================================================
# Helpers: live progress monitor
# ============================================================
def cmd_hms_to_seconds(args: argparse.Namespace) -> int:
    """Convert "HH:MM:SS" timestamp to total seconds.

    Replaces the heredoc that parses Shadow's `simulated: HH:MM:SS` log line.
    """
    parts = args.timestamp.split(':')
    print(int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
    return 0


# Compact histogram dimensions. 4 columns per sim-minute, so each cell
# is a 15-second bucket. 17 hex-style minute labels (0..g) sit at every
# 4th column with '-' fillers between them — the axis row and the data
# row are exactly the same width and line up 1:1.
SUBCOLS_PER_MIN = 4
HIST_MAX_MIN = 16    # last column = "16+ min" implicit overflow
HIST_WIDTH = HIST_MAX_MIN * SUBCOLS_PER_MIN + 1   # 65 cols total
HIST_AXIS_CHARS = '0123456789abcdefg'             # 17 minute labels


def _count_char(c: int) -> str:
    """Render a bucket count to a single character: '.' 1-9 a-g ^."""
    if c <= 0:
        return '.'
    if c <= 9:
        return str(c)
    if c <= 16:
        return chr(ord('a') + c - 10)
    return '^'


def _histogram_bucket(interval_sec: float) -> int:
    """Map a block-interval (sec) to a histogram column.

    Cells are 60/SUBCOLS_PER_MIN seconds wide (15s at SUBCOLS_PER_MIN=4).
    The final column is the overflow for any interval >= HIST_MAX_MIN min.
    """
    if interval_sec < 0:
        return 0
    sec_per_col = 60.0 / SUBCOLS_PER_MIN
    col = int(interval_sec // sec_per_col)
    if col >= HIST_WIDTH:
        return HIST_WIDTH - 1
    return col


def _histogram_axis_label() -> str:
    """Axis row: minute labels at every Nth column with '-' fillers.

    Example (SUBCOLS_PER_MIN=4):
      "0---1---2---3---4---5---6---7---8---9---a---b---c---d---e---f---g"
    """
    chars = ['-'] * HIST_WIDTH
    for i, label_char in enumerate(HIST_AXIS_CHARS):
        pos = i * SUBCOLS_PER_MIN
        if pos < HIST_WIDTH:
            chars[pos] = label_char
    return ''.join(chars)


def cmd_block_rate(args: argparse.Namespace) -> int:
    """Emit live block-rate stats parsed from a monerod bitmonero.log tail.

    Reads only the tail of the log (extending up to 32 MB if no events are
    found in the initial window) and emits shell-friendly KEY=VALUE lines
    the live monitor loop in run_sim.sh consumes.

    With --state-file, the helper also maintains a small JSON state file
    that accumulates a per-bucket histogram of every block interval seen
    across the entire run. Each call processes only NEW blocks (height >
    last seen) so the histogram grows monotonically. The state file lives
    inside shadow.data/ by convention and is archived with the run.

    Outputs nothing (exit 0) when the log is missing, empty, or has no
    block events in the tail — callers should just skip the section.
    """
    import json
    import re
    from datetime import datetime
    from pathlib import Path

    log_path = Path(args.log)
    try:
        size = log_path.stat().st_size
    except (OSError, FileNotFoundError):
        return 0
    if size == 0:
        return 0

    # Read a sliding tail. Block events are sparse in a busy log (lots of
    # per-block churn after each one), so start at 2 MB and grow if we
    # don't see at least 2 events. Cap at 32 MB to bound the worst case.
    ts_re = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)')
    height_re = re.compile(r'HEIGHT (\d+), difficulty:')

    def parse_tail(window: int) -> list[tuple[datetime, int]]:
        with log_path.open('rb') as f:
            f.seek(max(0, size - window))
            tail_bytes = f.read()
        out: list[tuple[datetime, int]] = []
        pending: datetime | None = None
        for line in tail_bytes.decode('utf-8', errors='ignore').split('\n'):
            if 'BLOCK SUCCESSFULLY ADDED' in line:
                m = ts_re.match(line)
                if m:
                    try:
                        pending = datetime.strptime(m.group(1)[:23],
                                                    "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        pending = None
            elif pending and 'HEIGHT' in line and 'difficulty:' in line:
                mh = height_re.search(line)
                if mh:
                    out.append((pending, int(mh.group(1))))
                    pending = None
        return out

    window = 2_000_000
    events: list[tuple[datetime, int]] = parse_tail(window)
    while len(events) < 2 and window < 32_000_000 and window < size:
        window *= 4
        events = parse_tail(window)

    if not events:
        return 0
    tail_bytes_used = min(window, size)
    # We need the "now sim time" line scan too; redo a small tail just for that.
    with log_path.open('rb') as f:
        f.seek(max(0, size - 100_000))
        tail_for_now = f.read().decode('utf-8', errors='ignore')

    last_ts, last_h = events[-1]

    # "Now" in sim time = the most recent timestamp anywhere in the tail.
    now_sim = last_ts
    for line in reversed(tail_for_now.split('\n')):
        m = ts_re.match(line)
        if m:
            try:
                now_sim = datetime.strptime(m.group(1)[:23],
                                            "%Y-%m-%d %H:%M:%S.%f")
                break
            except ValueError:
                continue

    time_since_last_block = (now_sim - last_ts).total_seconds()
    print(f'LAST_HEIGHT={last_h}')
    print(f'LAST_BLOCK_AGO_SEC={int(max(time_since_last_block, 0))}')

    if len(events) >= 2:
        oldest_ts, oldest_h = events[0]
        span_sec = (last_ts - oldest_ts).total_seconds()
        grew = last_h - oldest_h
        if span_sec >= 60 and grew >= 1:
            rate_per_min = grew / (span_sec / 60.0)
            min_per_block = (span_sec / 60.0) / grew
            print(f'RECENT_RATE_PER_MIN={rate_per_min:.2f}')
            print(f'RECENT_MIN_PER_BLOCK={min_per_block:.2f}')
            print(f'RECENT_RATE_WINDOW_SEC={int(span_sec)}')
            print(f'RECENT_RATE_BLOCKS={grew}')

    # Stateful histogram: load → process new blocks since last call → save.
    # No state file means we just emit live stats above with no histogram.
    if args.state_file:
        state_path = Path(args.state_file)
        state = {
            'last_seen_height': -1,
            'last_seen_block_time_iso': None,
            'bucket_counts': [0] * HIST_WIDTH,
        }
        if state_path.is_file():
            try:
                with state_path.open() as f:
                    loaded = json.load(f)
                # Defensive: only accept state with the expected shape and
                # width — otherwise reset rather than crashing or producing
                # garbage if the bucket count was tuned mid-run.
                if (isinstance(loaded, dict)
                        and 'bucket_counts' in loaded
                        and len(loaded['bucket_counts']) == HIST_WIDTH):
                    state = loaded
            except (json.JSONDecodeError, OSError):
                pass

        # Process new blocks (height > last_seen_height), in height order.
        new_events = sorted(
            [(t, h) for (t, h) in events if h > state['last_seen_height']],
            key=lambda e: e[1],
        )
        prev_ts: datetime | None = None
        if state['last_seen_block_time_iso']:
            try:
                prev_ts = datetime.fromisoformat(state['last_seen_block_time_iso'])
            except ValueError:
                prev_ts = None
        for ts, h in new_events:
            if prev_ts is not None:
                interval_sec = (ts - prev_ts).total_seconds()
                bucket = _histogram_bucket(interval_sec)
                state['bucket_counts'][bucket] += 1
            prev_ts = ts
            state['last_seen_height'] = h
            state['last_seen_block_time_iso'] = ts.isoformat()

        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with state_path.open('w') as f:
                json.dump(state, f)
        except OSError:
            pass

        hist_str = ''.join(_count_char(c) for c in state['bucket_counts'])
        axis_str = _histogram_axis_label()
        # Quote values that contain spaces so a shell `eval $(...)` works
        # correctly (HISTOGRAM_AXIS has lots of internal whitespace).
        print(f'HISTOGRAM="{hist_str}"')
        print(f'HISTOGRAM_AXIS="{axis_str}"')
        print(f'HISTOGRAM_TOTAL={sum(state["bucket_counts"])}')
    return 0


def cmd_chain_growth_stats(args: argparse.Namespace) -> int:
    """Print "max X mean Y median Z min W" for a list of byte deltas.

    Replaces the heredoc in `live_progress_monitor()` that summarizes
    LMDB growth across all monitored nodes.
    """
    deltas = sorted(args.deltas)
    n = len(deltas)
    if n == 0:
        return 0
    mx = max(deltas)
    mn = min(deltas)
    mean = sum(deltas) / n
    median = deltas[n // 2] if n % 2 else (deltas[n // 2 - 1] + deltas[n // 2]) / 2

    def fmt(b: float) -> str:
        if b >= 1048576:
            return f'{b / 1048576:.1f}M'
        if b >= 1024:
            return f'{b / 1024:.0f}K'
        return f'{b}B'

    print(f'max {fmt(mx)}  mean {fmt(mean)}  median {fmt(median)}  min {fmt(mn)}')
    return 0


# ============================================================
# Helpers: post-run summary text + KEY=VALUE printout
# ============================================================
def cmd_write_summary_report(args: argparse.Namespace) -> int:
    """Render the simulation summary text file.

    Reads the monitor's final_report.json and writes a formatted text
    summary to `--out`. Replaces the heredoc in `generate_summary_report()`.
    """
    with open(args.report) as f:
        d = json.load(f)

    s = d.get('summary', {})
    ts = d.get('transaction_stats', {})
    sc = s.get('success_criteria', {})
    hist = d.get('historical_data', [])

    lines: list[str] = []
    lines.append('=' * 60)
    lines.append('MONEROSIM SIMULATION SUMMARY')
    lines.append('=' * 60)
    lines.append('')

    # Run info
    lines.append(f'Run:            {args.run_name}')
    lines.append(f'Wall time:      {args.wall_time}')
    lines.append(f'Exit code:      {args.exit_code}')
    lines.append('')

    # Success criteria
    all_pass = all(sc.values()) if sc else False
    lines.append('SUCCESS CRITERIA')
    lines.append('-' * 40)
    labels = {
        'blocks_created': 'Blocks created',
        'blocks_propagated': 'Blocks propagated',
        'transactions_created_broadcast': 'Transactions broadcast',
        'transactions_in_blocks': 'Transactions in blocks',
    }
    for key, label in labels.items():
        status = 'PASS' if sc.get(key, False) else 'FAIL'
        lines.append(f'  {label:30s} {status}')
    lines.append('')
    lines.append(
        f'  Result: {"ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED"}'
    )
    lines.append('')

    # Network
    lines.append('NETWORK')
    lines.append('-' * 40)
    lines.append(f'  Nodes online:     {s.get("total_nodes", "?")}')
    lines.append(f'  Sync:             {s.get("avg_sync_percentage", 0):.0f}%')
    lines.append(f'  Block height:     {s.get("max_height", 0)}')
    lines.append(f'  Blocks mined:     {s.get("total_blocks_mined", 0)}')
    lines.append(f'  Alerts:           {s.get("alert_count", 0)}')
    lines.append('')

    # Transactions
    lines.append('TRANSACTIONS')
    lines.append('-' * 40)
    lines.append(f'  Created:          {s.get("total_transactions_created", 0)}')
    lines.append(f'  In blocks:        {s.get("total_transactions_in_blocks", 0)}')
    created_by = ts.get('tx_created_by_node', {})
    if created_by:
        lines.append('')
        lines.append('  Created by:')
        for node, count in sorted(created_by.items()):
            lines.append(f'    {node:20s} {count:>4} txs')
    lines.append('')

    # Per-node status from last monitoring cycle
    if hist:
        last = hist[-1]
        node_data = last.get('node_data', {})
        if node_data:
            lines.append('NODE STATUS (final)')
            lines.append('-' * 40)
            lines.append(
                f'  {"Node":20s} {"Height":>7} {"Balance":>12} {"Conns":>6} {"Pool TXs":>9}'
            )
            for nid in sorted(node_data.keys()):
                ndata = node_data[nid]
                daemon = ndata.get('daemon', {})
                wallet = ndata.get('wallet', {})
                height = daemon.get('height', '-')
                conns = daemon.get('connections', '-')
                pool = wallet.get('pool_size', '-')
                bal = wallet.get('balance', 0)
                if isinstance(bal, (int, float)) and bal > 0:
                    bal_str = f'{bal / 1e12:.2f} XMR'
                else:
                    bal_str = '-'
                lines.append(
                    f'  {nid:20s} {str(height):>7} {bal_str:>12} {str(conns):>6} {str(pool):>9}'
                )
            lines.append('')

    lines.append('=' * 60)

    with open(args.out, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    return 0


def cmd_print_summary_kv(args: argparse.Namespace) -> int:
    """Extract simulation results from final_report.json as KEY=VALUE lines.

    Output format (consumed by `grep '^KEY=' | cut -d= -f2` in run_sim.sh):
        NODES=<int>
        SYNC=<float, 0 dp>
        HEIGHT=<int>
        BLOCKS=<int>
        TX_CREATED=<int>
        TX_IN_BLOCKS=<int>
        WALLETS_FUNDED=<int>
        ALERTS=<int>
        ALL_PASS=yes|no
        CRITERIA=<label>: PASS|FAIL    (one line per success criterion)

    Replaces the heredoc in `print_summary()`.
    """
    try:
        with open(args.report) as f:
            d = json.load(f)
        s = d.get('summary', {})
        ts = d.get('transaction_stats', {})
        sc = s.get('success_criteria', {})

        nodes = s.get('total_nodes', '?')
        sync = s.get('avg_sync_percentage', 0)
        height = s.get('max_height', 0)
        blocks = s.get('total_blocks_mined', 0)
        tx_created = s.get('total_transactions_created', 0)
        tx_in_blocks = s.get('total_transactions_in_blocks', 0)
        alerts = s.get('alert_count', 0)

        # Success criteria
        all_pass = all(sc.values()) if sc else False
        criteria_lines = []
        labels = {
            'blocks_created': 'Blocks created',
            'blocks_propagated': 'Blocks propagated',
            'transactions_created_broadcast': 'Transactions broadcast',
            'transactions_in_blocks': 'Transactions in blocks',
        }
        for key, label in labels.items():
            passed = sc.get(key, False)
            mark = 'PASS' if passed else 'FAIL'
            criteria_lines.append(f'{label}: {mark}')

        # Count wallets that received funds (balance > 0) from last monitoring cycle
        wallets_funded = 0
        hist = d.get('historical_data', [])
        if hist:
            last_cycle = hist[-1]
            for ndata in last_cycle.get('node_data', {}).values():
                w = ndata.get('wallet', {})
                if w and w.get('balance', 0) > 0:
                    wallets_funded += 1

        print(f'NODES={nodes}')
        print(f'SYNC={sync:.0f}')
        print(f'HEIGHT={height}')
        print(f'BLOCKS={blocks}')
        print(f'TX_CREATED={tx_created}')
        print(f'TX_IN_BLOCKS={tx_in_blocks}')
        print(f'WALLETS_FUNDED={wallets_funded}')
        print(f'ALERTS={alerts}')
        print(f'ALL_PASS={"yes" if all_pass else "no"}')
        for line in criteria_lines:
            print(f'CRITERIA={line}')
    except Exception as e:
        print(f'ERROR={e}', file=sys.stderr)
    return 0


# ============================================================
# Argparse plumbing
# ============================================================
def _parse_int_csv(s: str) -> list[int]:
    """Argparse type: comma-separated list of ints. Empty string -> []."""
    s = s.strip()
    if not s:
        return []
    return [int(x) for x in s.split(',')]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='run_sim_helpers',
        description='Python helpers extracted from run_sim.sh.',
    )
    sub = p.add_subparsers(dest='cmd', required=True, metavar='<subcommand>')

    # estimate-ramdisk-mb
    p_ram = sub.add_parser(
        'estimate-ramdisk-mb',
        help='Print MB needed for monerod LMDB ramdisk (max(2048, total*per_host)).',
    )
    p_ram.add_argument('--total-monerods', type=int, required=True)
    # Accept float because run_sim.sh passes Python true-division output
    # (e.g. "6.0" from `21600 / 3600`); the original heredoc used it as a
    # plain numeric in `per_host = 100 + (10 * hours)` and `total * per_host`.
    p_ram.add_argument('--sim-hours', type=float, required=True)
    p_ram.set_defaults(func=cmd_estimate_ramdisk_mb)

    # rewrite-daemon-data-dir
    p_rd = sub.add_parser(
        'rewrite-daemon-data-dir',
        help='Read config YAML, override general.daemon_data_dir, write to dest.',
    )
    p_rd.add_argument('--config', required=True)
    p_rd.add_argument('--daemon-data-dir', required=True)
    p_rd.add_argument('--dest', required=True)
    p_rd.set_defaults(func=cmd_rewrite_daemon_data_dir)

    # extract-stop-time
    p_st = sub.add_parser(
        'extract-stop-time',
        help='Print general.stop_time from a config YAML.',
    )
    p_st.add_argument('config')
    p_st.set_defaults(func=cmd_extract_stop_time)

    # config-summary
    p_cs = sub.add_parser(
        'config-summary',
        help='Print "<total> <miners> <users> <relays> <fb_seeds>" from config YAML.',
    )
    p_cs.add_argument('config')
    p_cs.set_defaults(func=cmd_config_summary)

    # estimate-disk-mb
    p_disk = sub.add_parser(
        'estimate-disk-mb',
        help='Estimate disk usage (MB) for the upcoming run.',
    )
    p_disk.add_argument('--archive-dir', required=True)
    p_disk.add_argument('--num-miners', type=int, required=True)
    p_disk.add_argument('--num-users', type=int, required=True)
    p_disk.add_argument('--num-relays', type=int, required=True)
    p_disk.add_argument('--num-hosts', type=int, required=True)
    # See estimate-ramdisk-mb: sim-hours can be a float ("6.0").
    p_disk.add_argument('--sim-hours', type=float, required=True)
    p_disk.set_defaults(func=cmd_estimate_disk_mb)

    # hms-to-seconds
    p_hms = sub.add_parser(
        'hms-to-seconds',
        help='Convert HH:MM:SS to total seconds.',
    )
    p_hms.add_argument('timestamp')
    p_hms.set_defaults(func=cmd_hms_to_seconds)

    # chain-growth-stats
    p_cg = sub.add_parser(
        'chain-growth-stats',
        help='Compute "max X mean Y median Z min W" stats over byte deltas.',
    )
    p_cg.add_argument(
        '--deltas',
        type=_parse_int_csv,
        required=True,
        help='Comma-separated list of byte deltas.',
    )
    p_cg.set_defaults(func=cmd_chain_growth_stats)

    # block-rate
    p_br = sub.add_parser(
        'block-rate',
        help='Emit KEY=VALUE block-rate stats from a bitmonero.log tail.',
    )
    p_br.add_argument(
        '--log',
        required=True,
        help='Path to a live monerod bitmonero.log file.',
    )
    p_br.add_argument(
        '--state-file',
        default=None,
        help='Optional JSON file used to accumulate the run-wide block-interval '
             'histogram across ticks. Created on first call. Without this flag '
             'the helper only emits the live rate stats and skips the histogram.',
    )
    p_br.set_defaults(func=cmd_block_rate)

    # write-summary-report
    p_sr = sub.add_parser(
        'write-summary-report',
        help='Render simulation summary text from final_report.json.',
    )
    p_sr.add_argument('--report', required=True)
    p_sr.add_argument('--out', required=True)
    p_sr.add_argument('--run-name', required=True)
    p_sr.add_argument('--wall-time', required=True, help='Pre-formatted human duration.')
    p_sr.add_argument('--exit-code', required=True)
    p_sr.set_defaults(func=cmd_write_summary_report)

    # print-summary-kv
    p_kv = sub.add_parser(
        'print-summary-kv',
        help='Print KEY=VALUE simulation summary lines from final_report.json.',
    )
    p_kv.add_argument('--report', required=True)
    p_kv.set_defaults(func=cmd_print_summary_kv)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == '__main__':
    sys.exit(main())
