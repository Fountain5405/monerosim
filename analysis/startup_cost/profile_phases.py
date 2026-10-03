"""Split a perf profile of one daemon's main thread into start-up phases.

    perf record -e cpu-clock -F 199 --call-graph dwarf,16384 -t <tid> -o start.data -- sleep 25
    python3 profile_phases.py start.data

Frame-pointer stacks stop at the Shadow shim's signal frames; use DWARF.
"""
import sys, subprocess, collections, re
out = subprocess.run(['perf', 'script', '-i', sys.argv[1], '-F', 'time,ip,sym,dso'], capture_output=True, text=True).stdout
ph = collections.Counter(); first = {}; last = {}; total = 0; other = collections.Counter()
for block in out.strip().split('\n\n'):
    lines = block.split('\n')
    try: t = float(lines[0].strip().rstrip(':').split()[-1])
    except ValueError: continue
    syms = [re.sub(r'::h[0-9a-f]{16}', '', l.strip().split(' ', 1)[1]) if ' ' in l.strip() else '' for l in lines[1:]]
    s = '\n'.join(syms); total += 1
    if 'get_ticks_per_ns' in s: k = 'perf_timer static init (get_ticks_per_ns busy-wait)'
    elif 'create_rsa_ssl_certificate' in s or 'create_ec_ssl_certificate' in s: k = 'RPC SSL certificate generation'
    elif 'ssl' in s.lower(): k = 'other SSL'
    elif 'randomx' in s.lower() or 'rx_' in s or 'fill_block' in s or 'argon' in s.lower(): k = 'RandomX'
    elif 'mdb_' in s or 'lmdb' in s.lower(): k = 'LMDB'
    elif '_dl_' in s or 'ld-linux' in s or 'dl_main' in s: k = 'dynamic loader'
    else:
        k = 'other'
        u = [x for x in syms if x and 'shim' not in x and 'unknown' not in x]
        other[' <- '.join(x.split(' (')[0][:45] for x in u[:4])] += 1
    ph[k] += 1; first.setdefault(k, t); last[k] = t
t0 = min(first.values())
print(f'{total} samples (~{total/199:.1f} s of main-thread CPU at 199 Hz)')
for k, v in ph.most_common():
    print(f'{v:6d} {100*v/total:5.1f}%  {v/199:5.1f} s  [{first[k]-t0:5.1f}..{last[k]-t0:5.1f} s]  {k}')
print('top "other":')
for k, v in other.most_common(8): print(f'   {v:5d}  {k}')
