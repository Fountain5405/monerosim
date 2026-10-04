"""Every second, name the simulated process that used >= half a core.

From docs/20261003_startup_ssl_runbook.md. Start it once Shadow runs:
    python3 busy_tracker.py > tracker.txt
Prints each change of busy process, then per-process busy seconds.
"""
import collections, os, subprocess, sys, time
HZ = os.sysconf('SC_CLK_TCK')
shadow = int(subprocess.check_output(['pgrep', '-u', str(os.getuid()), '-x', 'shadow']).split()[0])
def kids():
    out = []
    for p in os.listdir('/proc'):
        if p.isdigit():
            try:
                s = open(f'/proc/{p}/stat').read()
                if int(s[s.rfind(')') + 2:].split()[1]) == shadow: out.append(p)
            except OSError: pass
    return out
def name(p):
    try: args = open(f'/proc/{p}/cmdline').read().split('\0')
    except OSError: return '?'
    for a in args:
        if a.startswith(('--data-dir=', '--wallet-dir=')): return a.rstrip('/').split('/')[-1]
    return next((a for a in args if a.startswith('agents.')), args[0].split('/')[-1])
def snap():
    d = collections.Counter()
    for p in kids():
        try:
            for t in os.listdir(f'/proc/{p}/task'):
                s = open(f'/proc/{p}/task/{t}/stat').read(); f = s[s.rfind(')') + 2:].split()
                d[p] += int(f[11]) + int(f[12])
        except OSError: pass
    return d
busy, names, last, prev = collections.Counter(), {}, None, snap()
while os.path.exists(f'/proc/{shadow}'):
    time.sleep(1); cur = snap()
    p, ticks = max(((p, cur[p] - prev.get(p, cur[p])) for p in cur), key=lambda x: x[1], default=(None, 0))
    prev = cur
    if p and ticks / HZ >= 0.5:                # one process used >= half a core this second
        names.setdefault(p, name(p)); busy[p] += 1
        if p != last: print(time.strftime('%H:%M:%S'), 'busy:', names[p], flush=True); last = p
secs = sorted(busy.values())
print(f'{len(secs)} processes had busy stretches; median {secs[len(secs)//2] if secs else 0} s, '
      f'total {sum(secs)} s')
for p, s in busy.most_common(): print(f'  {s:4d} s  {names[p]}')
