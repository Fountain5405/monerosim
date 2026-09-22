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

from datetime import datetime
from pathlib import Path

try:  # imported as scripts.run_sim_helpers (tests)
    from scripts import run_dirs
except ImportError:  # invoked as `python3 scripts/run_sim_helpers.py`
    import run_dirs  # type: ignore


# ============================================================
# Helpers: ramdisk math
# ============================================================

NA_VALUES = ("n/a", "na", "not_applicable")


def criterion_mark(value) -> str:
    """Render a tri-state criterion value as PASS / FAIL / N/A."""
    if isinstance(value, str) and value.strip().lower() in NA_VALUES:
        return "N/A"
    return "PASS" if value else "FAIL"


def applicable_criteria(sc: dict) -> dict:
    """Drop criteria marked not-applicable.

    IMPORTANT: "n/a" is a truthy string, so a bare all(sc.values()) would count
    a skipped criterion as a pass. Always filter through this first.
    """
    return {
        k: v for k, v in sc.items()
        if not (isinstance(v, str) and v.strip().lower() in NA_VALUES)
    }


def criteria_verdict(sc: dict) -> str:
    """Overall verdict line, honest about skipped criteria."""
    applicable = applicable_criteria(sc)
    if not applicable:
        return "NO APPLICABLE CHECKS"
    if not all(applicable.values()):
        return "SOME CHECKS FAILED"
    return "ALL CHECKS PASSED" if len(applicable) == len(sc) else "ALL APPLICABLE CHECKS PASSED"


CRITERIA_LABELS = {
    "blocks_created": "Blocks created",
    "nodes_funded": "Nodes funded",
    "actual_blocks_propagated": "Blocks propagated (actual)",
    "transactions_created_broadcast": "Transactions broadcast",
    "transactions_in_blocks": "Transactions in blocks",
    # Legacy only: reports archived before 2026-09-20 carry "blocks_propagated",
    # which measured funded nodes rather than propagation. Kept so old runs still
    # render, under its original label so existing parsers keep matching. The
    # current monitor never emits this key.
    "blocks_propagated": "Blocks propagated",
}

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


_STOP_TIME_RE = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*([hms]?)\s*$')


def parse_stop_time_hours(value) -> float:
    """'6h' -> 6.0, '90m' -> 1.5, '23400s' -> 6.5, bare number = seconds; else 0.0."""
    m = _STOP_TIME_RE.match(str(value if value is not None else ''))
    if not m:
        return 0.0
    n, unit = float(m.group(1)), m.group(2)
    if unit == 'h':
        return n
    if unit == 'm':
        return n / 60
    return n / 3600


def config_counts(config_path: str) -> dict:
    """Agent counts + Shadow parallelism + sim hours from a config YAML.

    Keys: total, miners, users, relays, fb_seeds, parallelism (0 = unset/auto),
    sim_hours (0.0 if stop_time is missing or unparseable).
    """
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}
    general = cfg.get('general', {}) or {}
    meta = cfg.get('metadata', {}) or {}
    agents_meta = meta.get('agents', {}) or {}
    agents = cfg.get('agents', {}) or {}
    miners = agents_meta.get(
        'miners',
        sum(1 for a in agents if a.startswith('miner-0') or a.startswith('miner-1')),
    )
    users = agents_meta.get('users', sum(1 for a in agents if a.startswith('user-')))
    total = agents_meta.get('total', len(agents))
    relays = sum(1 for a in agents if a.startswith('relay-'))
    fb_mode = (general.get('fallback_seeds') or 'auto').lower()
    custom_seeds = sum(1 for a in agents if a.startswith('monero-seed-'))
    if fb_mode == 'off':
        fb_seeds = 0
    elif fb_mode == 'custom':
        fb_seeds = custom_seeds
    else:
        fb_seeds = 6
    try:
        parallelism = int(general.get('parallelism') or 0)
    except (TypeError, ValueError):
        parallelism = 0
    return {
        'total': total, 'miners': miners, 'users': users, 'relays': relays,
        'fb_seeds': fb_seeds, 'parallelism': parallelism,
        'sim_hours': parse_stop_time_hours(general.get('stop_time', '')),
    }


# Options that only a patched monerod understands. Key = the daemon_options
# key a config sets; value = the string that must appear in `monerod --help`.
SIM_FLAG_OPTIONS = {
    'fakechain-hard-forks': 'fakechain-hard-forks',
    'peerlist-dump-file': 'peerlist-dump-file',
    'sim-relay-alt-blocks': 'sim-relay-alt-blocks',
    'sim-publish-or-perish': 'sim-publish-or-perish',
    'sim-pop-k': 'sim-pop-k',
    'sim-pop-delay-s': 'sim-pop-delay-s',
    'sim-pop-det-tie': 'sim-pop-det-tie',
    'sim-pop-uncles': 'sim-pop-uncles',
}
# general.mining.mode: native drives miners through the sim-mining patch.
NATIVE_MINING_FLAG = 'sim-hash-interval-ms'
# Shorthand names setup.sh installs; naming one means the config expects the
# patched build to exist even if it sets no patched option itself.
PATCHED_DAEMON_NAMES = ('monerod-sim', 'monerod-hf')
DEFAULT_BIN_DIR = '.monerosim/bin'


def _resolve_daemon(daemon: str) -> tuple[str, bool]:
    """Map a config `daemon:` value to (path, explicit).

    Mirrors src/utils/binary.rs: a bare name is shorthand for
    ~/.monerosim/bin/<name>; anything containing a separator is a path the
    user chose deliberately. `explicit` drives how strictly the version pin is
    enforced -- a researcher pointing at their own build (a countermeasure
    patch, say) should not be blocked by our pin.
    """
    daemon = os.path.expanduser(daemon.strip())
    if os.sep in daemon:
        return os.path.abspath(daemon), True
    return os.path.join(os.path.expanduser('~'), DEFAULT_BIN_DIR, daemon), False


def daemon_capabilities(config_path: str) -> list[dict]:
    """Which binaries this config uses, and which patched flags each needs.

    The check has to follow the config rather than assume ~/.monerosim/bin:
    a config may point any agent at its own monerod by path, and that binary
    is the one whose capabilities actually matter. Returns one entry per
    distinct binary, each {path, explicit, flags, agents}, sorted by path.
    Binaries needing nothing are omitted so ordinary runs stay ungated.
    """
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}
    general = cfg.get('general', {}) or {}
    defaults = general.get('daemon_defaults', {}) or {}
    mining = general.get('mining', {}) or {}
    native = str(mining.get('mode', '')).strip().lower() == 'native'

    found: dict[str, dict] = {}
    for name, spec in (cfg.get('agents', {}) or {}).items():
        if not isinstance(spec, dict):
            continue
        # Pure script agents run no daemon at all, so daemon_defaults never
        # reach them (src/agent/pure_scripts.rs: "a script but no daemon or
        # wallet"). Counting them made a monitor agent demand a patched build.
        if spec.get('script') and not spec.get('daemon') and not spec.get('wallet'):
            continue
        daemon = str(spec.get('daemon') or 'monerod')
        if 'cuprated' in os.path.basename(daemon):
            continue  # the cuprate pin gate owns those
        opts = dict(defaults)
        opts.update(spec.get('daemon_options', {}) or {})
        flags = {flag for key, flag in SIM_FLAG_OPTIONS.items() if key in opts}
        # Native mining REPLACES a miner's daemon with monerod-sim regardless of
        # what the config says (src/agent/user_agents.rs:1119-1146), so probe
        # that binary rather than the one the config names.
        is_miner = name.startswith('miner-') or 'hashrate' in spec
        if native and is_miner:
            flags.add(NATIVE_MINING_FLAG)
            daemon = 'monerod-sim'
        named_patched = os.path.basename(daemon) in PATCHED_DAEMON_NAMES
        if not flags and not named_patched:
            continue
        path, explicit = _resolve_daemon(daemon)
        entry = found.setdefault(
            path, {'path': path, 'explicit': explicit, 'flags': set(), 'agents': []})
        entry['flags'] |= flags
        entry['agents'].append(name)
    return [
        {'path': e['path'], 'explicit': e['explicit'],
         'flags': sorted(e['flags']), 'agents': sorted(e['agents'])}
        for e in sorted(found.values(), key=lambda e: e['path'])
    ]


def cmd_daemon_capabilities(args: argparse.Namespace) -> int:
    """Emit one TAB-separated line per binary for run_sim.sh's gate.

        <explicit 0|1>\t<path>\t<comma-separated flags>\t<example agent>

    Flags may be empty: the config named a patched binary without setting a
    patched option, so only its existence is checked.
    """
    for e in daemon_capabilities(args.config):
        print("%d\t%s\t%s\t%s" % (
            1 if e['explicit'] else 0, e['path'], ",".join(e['flags']),
            e['agents'][0] if e['agents'] else ''))
    return 0


def cmd_config_summary(args: argparse.Namespace) -> int:
    """Print agent counts as a single space-separated line.

    Format (consumed by run_sim.sh:
    `read -r CFG_TOTAL CFG_MINERS CFG_USERS CFG_RELAYS CFG_FALLBACK_SEEDS CFG_PARALLELISM`):
        <total> <miners> <users> <relays> <fb_seeds> <parallelism>
    """
    c = config_counts(args.config)
    print(f"{c['total']} {c['miners']} {c['users']} {c['relays']} {c['fb_seeds']} {c['parallelism']}")
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


def estimate_disk_mb(archive_dir: str, num_miners: int, num_users: int,
                     num_relays: int, num_hosts: int, sim_hours: float) -> tuple[float, dict, str]:
    """Estimate disk usage (MB) for a run; returns (estimate_mb, rates, source).

    Learns per-host-type MB/hour rates from the most recent COMPLETE archive
    under `archive_dir` (one that has summary.txt — live and crashed runs
    are never samples), aggregating shadow.data/hosts, daemon_logs and the
    sampled blockchain snapshots. Falls back to conservative defaults.
    """
    defaults = {'miner': 4.0, 'user': 2.0, 'relay': 1.25, 'other': 0.5}
    learned: dict[str, float] = {}
    listing: Iterable[str] = (
        sorted(os.listdir(archive_dir), reverse=True) if os.path.isdir(archive_dir) else []
    )
    for run_name in listing:
        run_path = os.path.join(archive_dir, run_name)
        hosts_dir = os.path.join(run_path, 'shadow.data', 'hosts')
        daemon_logs_dir = os.path.join(run_path, 'daemon_logs')
        blockchain_dir = os.path.join(run_path, 'blockchain')
        cfg_path = os.path.join(run_path, 'input_config.yaml')
        if not os.path.isfile(os.path.join(run_path, 'summary.txt')):
            continue  # live or crashed run: partial footprint would skew the rate
        if not os.path.isdir(hosts_dir) or not os.path.isfile(cfg_path):
            continue
        try:
            import yaml
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            h = parse_stop_time_hours((cfg.get('general', {}) or {}).get('stop_time', ''))
            if h <= 0:
                continue
        except Exception:
            continue
        by_type_log: dict[str, list[float]] = {}
        by_type_chain: dict[str, list[float]] = {}
        for host in os.listdir(hosts_dir):
            host_path = os.path.join(hosts_dir, host)
            if not os.path.isdir(host_path):
                continue
            size_kb = _disk_kb(host_path)
            log_path = os.path.join(daemon_logs_dir, 'monero-' + host)
            if os.path.isdir(log_path):
                size_kb += _disk_kb(log_path)
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
            chain_sizes = by_type_chain.get(t, [])
            if chain_sizes:
                avg_mb += (sum(chain_sizes) / len(chain_sizes)) / 1024
            rate = avg_mb / h
            if t not in learned or len(sizes) > 10:
                learned[t] = rate
        break  # most recent complete run only

    rates = {**defaults, **learned}
    source = 'learned from previous run' if learned else 'default estimates'
    others = max(0, num_hosts - num_miners - num_users - num_relays)
    est = (
        num_miners * rates['miner'] + num_users * rates['user']
        + num_relays * rates['relay'] + others * rates['other']
    ) * sim_hours * 1.2
    return est, rates, source


def cmd_estimate_disk_mb(args: argparse.Namespace) -> int:
    """Print estimated MB to stdout; `RATES:<json>|SOURCE:<text>` to stderr."""
    est, rates, source = estimate_disk_mb(
        args.archive_dir, args.num_miners, args.num_users, args.num_relays,
        args.num_hosts, args.sim_hours,
    )
    print(f'{est:.0f}')
    print(f'RATES:{json.dumps(rates)}|SOURCE:{source}', file=sys.stderr)
    return 0


def cmd_live_runs(args: argparse.Namespace) -> int:
    """One TSV line per live run_sim.sh run on this box other than --exclude-pid.

    run_id  pid  elapsed_s  daemons  used_kb  est_total_kb|-  remaining_kb|-  source  parallelism|-

    Consumed by check_disk_space() in run_sim.sh to reserve the other runs'
    projected growth before comparing free space with this run's estimate.
    Numeric columns are whole KB (run_sim.sh does integer arithmetic on them).
    """
    runs = run_dirs.list_live_runs(
        Path(args.archive_base), tmp_root=Path(args.tmp_root), exclude_pid=args.exclude_pid,
    )
    now = datetime.now()

    def fmt(v):
        return '-' if v is None else f'{v:.0f}'

    for r in runs:
        elapsed = int((now - r.started).total_seconds()) if r.started else -1
        daemons = len(list(r.tmp_dir.glob('monero-*'))) if r.tmp_dir else 0
        used_kb = 0.0
        if r.run_dir:
            used_kb += _disk_kb(str(r.run_dir))
        if r.tmp_dir:
            used_kb += _disk_kb(str(r.tmp_dir))
        est_kb = rem_kb = par = None
        cfg_path = r.run_dir / 'input_config.yaml' if r.run_dir else None
        if cfg_path and cfg_path.is_file():
            try:
                c = config_counts(str(cfg_path))
                hosts = c['total'] + c['fb_seeds']
                est_mb, _, _ = estimate_disk_mb(
                    args.archive_base, c['miners'], c['users'], c['relays'], hosts,
                    max(1.0, c['sim_hours']),
                )
                est_kb = est_mb * 1024
                rem_kb = max(0.0, est_kb - used_kb)
                par = c['parallelism']
            except Exception:
                est_kb = rem_kb = par = None
        print('\t'.join([
            r.run_id, str(r.pid), str(elapsed), str(daemons), f'{used_kb:.0f}',
            fmt(est_kb), fmt(rem_kb), r.source, '-' if par is None else str(par),
        ]))
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
HIST_RECENT_N = 30   # sliding window for the "last N blocks" row


def _count_char(c: int) -> str:
    """Render a bucket count to a single character: 0-9 a-g ^.

    Uses literal '0' for empty cells so the data row's column widths
    visually match the axis row's labels (which include '0' at the
    leftmost minute). In monospace fonts '.' and '0' are the same
    width, but '0' reads as a number in context.
    """
    if c <= 0:
        return '0'
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
        state: dict = {
            'last_seen_height': -1,
            'last_seen_block_time_iso': None,
            'bucket_counts': [0] * HIST_WIDTH,
            'recent_intervals': [],  # rolling window of last N interval seconds
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
                    state.setdefault('recent_intervals', [])
            except (json.JSONDecodeError, OSError):
                pass

        # Process new blocks (height > last_seen_height) deduped by height.
        #
        # The same HEIGHT can appear in the log multiple times — once for the
        # original add, and again every time the daemon replays
        # handle_block_to_main_chain() during a reorg. We want the EARLIEST
        # timestamp for each height (the moment the chain first reached it),
        # so sort by (height, timestamp) ascending and keep the first seen
        # per height.
        candidates = sorted(
            [(t, h) for (t, h) in events if h > state['last_seen_height']],
            key=lambda e: (e[1], e[0]),
        )
        new_events: list[tuple[datetime, int]] = []
        seen_heights: set[int] = set()
        for ts, h in candidates:
            if h in seen_heights:
                continue
            seen_heights.add(h)
            new_events.append((ts, h))
        prev_ts: datetime | None = None
        if state['last_seen_block_time_iso']:
            try:
                prev_ts = datetime.fromisoformat(state['last_seen_block_time_iso'])
            except ValueError:
                prev_ts = None
        for ts, h in new_events:
            if prev_ts is not None:
                interval_sec = (ts - prev_ts).total_seconds()
                state['bucket_counts'][_histogram_bucket(interval_sec)] += 1
                state['recent_intervals'].append(interval_sec)
            prev_ts = ts
            state['last_seen_height'] = h
            state['last_seen_block_time_iso'] = ts.isoformat()

        # Trim the recent-intervals window to the last N blocks.
        if len(state['recent_intervals']) > HIST_RECENT_N:
            state['recent_intervals'] = state['recent_intervals'][-HIST_RECENT_N:]

        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with state_path.open('w') as f:
                json.dump(state, f)
        except OSError:
            pass

        axis_str = _histogram_axis_label()
        hist_str = ''.join(_count_char(c) for c in state['bucket_counts'])

        # Build the "last N blocks" histogram fresh from the rolling window.
        recent_counts = [0] * HIST_WIDTH
        for sec in state['recent_intervals']:
            recent_counts[_histogram_bucket(sec)] += 1
        hist_recent_str = ''.join(_count_char(c) for c in recent_counts)
        n_recent = len(state['recent_intervals'])

        # Quote values that contain spaces (HISTOGRAM_AXIS has '-' fillers
        # but no whitespace; quoting just for safety / shell-eval clarity).
        print(f'HISTOGRAM="{hist_str}"')
        print(f'HISTOGRAM_AXIS="{axis_str}"')
        print(f'HISTOGRAM_TOTAL={sum(state["bucket_counts"])}')
        print(f'HISTOGRAM_RECENT="{hist_recent_str}"')
        print(f'HISTOGRAM_RECENT_N={n_recent}')
        print(f'HISTOGRAM_RECENT_WINDOW={HIST_RECENT_N}')
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

    # Success criteria (tri-state: PASS / FAIL / N/A)
    lines.append('SUCCESS CRITERIA')
    lines.append('-' * 40)
    for key, label in CRITERIA_LABELS.items():
        if key not in sc:
            continue
        lines.append(f'  {label:30s} {criterion_mark(sc[key])}')
    lines.append('')
    lines.append(f'  Result: {criteria_verdict(sc) if sc else "SOME CHECKS FAILED"}')
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

        # Success criteria (tri-state: PASS / FAIL / N/A)
        all_pass = bool(applicable_criteria(sc)) and all(applicable_criteria(sc).values())
        criteria_lines = []
        for key, label in CRITERIA_LABELS.items():
            if key not in sc:
                continue
            criteria_lines.append(f'{label}: {criterion_mark(sc[key])}')

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
        help='Print "<total> <miners> <users> <relays> <fb_seeds> <parallelism>" from config YAML.',
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

    # live-runs
    p_lr = sub.add_parser(
        'live-runs',
        help='TSV of other live run_sim.sh runs on this box (for the concurrency-aware preflight).',
    )
    p_lr.add_argument('--archive-base', required=True)
    p_lr.add_argument('--exclude-pid', type=int, default=None)
    p_lr.add_argument('--tmp-root', default='/tmp')
    p_lr.set_defaults(func=cmd_live_runs)

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

    p_dc = sub.add_parser(
        'daemon-capabilities',
        help='Per-binary patched-flag requirements implied by a config.',
    )
    p_dc.add_argument('--config', required=True)
    p_dc.set_defaults(func=cmd_daemon_capabilities)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == '__main__':
    sys.exit(main())
