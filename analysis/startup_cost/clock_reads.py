"""Count clock reads per process from Shadow strace files.

Needs a run with Shadow's `experimental.strace_logging_mode` on. The shim logs
every clock read it answers itself (clock_gettime, gettimeofday, time, getcpu;
rdtsc is emulated as a clock_gettime), with
the simulated time in ns; Shadow logs the syscalls it handles, `= <blocked>`
when one blocks. Shadow charges `unblocked_vdso_latency` (default 10 ns) per
clock read and `unblocked_syscall_latency` (1 us) per syscall it handles that
does not block.

    python3 clock_reads.py <run>/shadow.data/hosts --skip 120 [--glob 'monerod.*.strace']

Per process: clock reads per simulated second after the first --skip seconds
of its life (the start-up busy-wait is reported apart), charged syscalls per
second, and clock reads per busy period (a thread's lines from waking up to
its next blocking call): every read in a busy period delays that thread's next
action by the vDSO charge. --threshold also lists every run of more than that
many reads in a row over the process's whole life: with --bootfast's
threshold (10000), exactly the places where the busy charge applied.
"""
import argparse, collections, glob, json, os, re, sys
from multiprocessing import Pool

CLOCK = {'clock_gettime', 'gettimeofday', 'time', 'getcpu'}
LINE = re.compile(r'^(\S+) \[tid (\d+)\] ([a-z_0-9^]+)')


def parse_time(t):
    if len(t) > 2 and t[2] == ':':                # Shadow: HH:MM:SS.nnnnnnnnn
        h, m, s = t.split(':')
        sec, _, frac = s.partition('.')
        return (int(h) * 3600 + int(m) * 60 + int(sec)) * 10**9 + int(frac.ljust(9, '0'))
    return int(t)                                  # shim: ns, zero-padded


def analyze(path, skip_s=120, bin_s=600, threshold=10000):
    start = None
    startup_reads = 0
    reads = collections.Counter()                  # kind -> count (steady state)
    charged = blocked = 0
    bins = collections.Counter()                   # bin index -> clock reads
    bins_charged = collections.Counter()
    per_tid = collections.Counter()
    cur = collections.Counter()                    # tid -> reads in current busy period
    cur_t0 = {}
    burst_hist = collections.Counter()             # log2 bucket -> busy periods
    bursts = 0
    top = []                                       # (reads, t, tid)
    run = collections.Counter()                    # tid -> consecutive reads with no other call
    max_run = (0, 0, 0)
    whole_run = collections.Counter()              # tid -> same, counted over the whole life
    whole_t0 = {}                                  # tid -> time the current whole-life run began
    over = []                                      # runs longer than threshold: (start s, length, tid)
    first = last = None
    with open(path, errors='replace') as f:
        for line in f:
            m = LINE.match(line)
            if not m:
                continue
            name = m.group(3)
            if name == '^^^':
                continue
            t = parse_time(m.group(1))
            tid = int(m.group(2))
            if start is None:
                start = t
            if first is None or t < first:
                first = t
            last = t if last is None or t > last else last
            steady = t >= start + skip_s * 10**9
            if name in CLOCK:
                if whole_run[tid] == 0:
                    whole_t0[tid] = t
                whole_run[tid] += 1
                if not steady:
                    startup_reads += 1
                    continue
                reads[name] += 1
                bins[(t - start) // (bin_s * 10**9)] += 1
                per_tid[tid] += 1
                cur[tid] += 1
                run[tid] += 1
                if run[tid] > max_run[0]:
                    max_run = (run[tid], t, tid)
                continue
            if name.startswith('shadow_'):
                # Shadow's own plumbing (e.g. the shim's shadow_yield when time
                # passes the runahead window), not a call by the program: it
                # neither ends a run of clock reads (the shim's count goes on)
                # nor a busy period.
                continue
            run[tid] = 0
            if whole_run[tid] > threshold:
                over.append(((whole_t0[tid] - start) / 1e9, whole_run[tid], tid))
            whole_run[tid] = 0
            if not steady:
                continue
            if line.rstrip().endswith('= <blocked>'):
                blocked += 1
                n = cur.pop(tid, 0)
                bursts += 1
                burst_hist[n.bit_length()] += 1    # 0 -> 0, 1 -> 1, 2-3 -> 2, 4-7 -> 3, ...
                if n:
                    top.append((n, t, tid))
                    if len(top) > 2000:
                        top.sort(reverse=True)
                        del top[50:]
            else:
                charged += 1
                bins_charged[(t - start) // (bin_s * 10**9)] += 1
    for tid, n in whole_run.items():
        if n > threshold:
            over.append(((whole_t0[tid] - start) / 1e9, n, tid))
    top.sort(reverse=True)
    dur = max(0, (last - start) / 1e9 - skip_s) if start is not None else 0
    return {
        'file': path, 'start_s': (start or 0) / 1e9, 'end_s': (last or 0) / 1e9, 'steady_s': dur,
        'startup_reads': startup_reads, 'reads': dict(reads), 'charged': charged, 'blocked': blocked,
        'bins': {int(k): v for k, v in bins.items()}, 'bins_charged': {int(k): v for k, v in bins_charged.items()},
        'per_tid': dict(per_tid.most_common(8)), 'bursts': bursts,
        'burst_hist': {int(k): v for k, v in burst_hist.items()},
        'top_bursts': [(n, t / 1e9, tid) for n, t, tid in top[:5]],
        'max_run': (max_run[0], max_run[1] / 1e9, max_run[2]),
        'over_threshold': sorted(over),
    }


def pct(hist, total, q):
    acc = 0
    for b in sorted(hist):
        acc += hist[b]
        if acc >= q * total:
            return 0 if b == 0 else 2 ** (b - 1), 2 ** b - 1
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hosts_dir')
    ap.add_argument('--glob', default='monerod.*.strace')
    ap.add_argument('--skip', type=float, default=120)
    ap.add_argument('--bin', type=float, default=600)
    ap.add_argument('--threshold', type=int, default=10000,
                    help='also list runs of more than this many reads in a row (whole life)')
    ap.add_argument('--json')
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.hosts_dir, '*', a.glob)))
    with Pool(min(12, len(files) or 1)) as p:
        res = p.starmap(analyze, [(f, a.skip, a.bin, a.threshold) for f in files])
    if a.json:
        json.dump(res, open(a.json, 'w'), indent=1)
    print(f"{'host':18} {'steady s':>8} {'reads/s':>9} {'charged/s':>9} {'busy prds':>9} "
          f"{'reads/prd p50':>13} {'p99':>9} {'p99.9':>11} {'max':>6} {'max run':>7} {'startup reads':>13} "
          f"runs over threshold (s into life: length)")
    for r in res:
        host = r['file'].split('/')[-2]
        n = sum(r['reads'].values())
        s = r['steady_s'] or 1
        h = collections.Counter({int(k): v for k, v in r['burst_hist'].items()})
        fmt = lambda x: '-' if x is None else (f'{x[0]}' if x[0] == x[1] else f'{x[0]}-{x[1]}')
        mx = r['top_bursts'][0][0] if r['top_bursts'] else 0
        print(f"{host:18} {r['steady_s']:8.0f} {n / s:9.1f} {r['charged'] / s:9.1f} {r['bursts']:9d} "
              f"{fmt(pct(h, r['bursts'], .5)):>13} {fmt(pct(h, r['bursts'], .99)):>9} "
              f"{fmt(pct(h, r['bursts'], .999)):>11} {mx:6d} {r['max_run'][0]:7d} {r['startup_reads']:13d} "
              + (', '.join(f'{t:.1f}: {n}' for t, n, _ in r['over_threshold'][:4]) or '-')
              + (f" (+{len(r['over_threshold']) - 4} more)" if len(r['over_threshold']) > 4 else ''))


if __name__ == '__main__':
    main()
