"""Wall time per monerod start: from the process appearing in /proc to
"core RPC server started ok" in its bitmonero.log (0.1 s polling).

    python3 start_watcher.py /tmp/monerosim-<run_id> <file holding Shadow's start epoch>

Exits when Shadow exits; prints one line per daemon (spawn time after Shadow
start, start duration, name) and a relay summary.
"""
import os, sys, time, subprocess, statistics
tmp, t0 = sys.argv[1], float(open(sys.argv[2]).read())
shadow = int(subprocess.check_output(['pgrep', '-u', str(os.getuid()), '-x', 'shadow']).split()[0])
MARK = b'core RPC server started ok'
spawn, ready, off, seen = {}, {}, {}, set()
while os.path.exists(f'/proc/{shadow}'):
    now = time.time()
    for p in os.listdir('/proc'):
        if not p.isdigit() or p in seen: continue
        try: args = open(f'/proc/{p}/cmdline', 'rb').read().split(b'\0')
        except OSError: continue
        if not args or not args[0].endswith(b'monerod'): continue
        d = next((a[11:].decode() for a in args if a.startswith(b'--data-dir=')), None)
        seen.add(p)
        if d and d.startswith(tmp) and d not in spawn: spawn[d] = now
    for d in list(spawn):
        if d in ready: continue
        f = f'{d}/bitmonero.log'
        try:
            with open(f, 'rb') as fh:
                fh.seek(off.get(d, 0)); chunk = fh.read(); off[d] = max(0, fh.tell() - len(MARK))
            if MARK in chunk: ready[d] = time.time()
        except OSError: pass
    time.sleep(0.1)
rows = sorted((spawn[d] - t0, ready[d] - spawn[d], os.path.basename(d)) for d in ready)
for s, dur, n in rows: print(f'{s:8.1f} {dur:6.2f}  {n}')
rel = [dur for s, dur, n in rows if 'relay' in n]
allr = [ready[d] - t0 for d in ready if 'relay' in d]
print(f'daemons ready: {len(rows)}; relays {len(rel)}; relay start median {statistics.median(rel):.2f} s, '
      f'mean {statistics.mean(rel):.2f} s, max {max(rel):.2f} s; last relay ready at {max(allr):.0f} s after Shadow start')
