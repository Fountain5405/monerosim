# Runbook: why simulation startup takes hours (RPC SSL hypothesis)

**Written:** 2026-10-03, on the 256-thread box, for an agent on a smaller box. Everything
below the "Steps" heading is to be done on the smaller box; the big box is busy with a
colleague's run and must not be used for experiments.

## Problem statement

Monerosim simulations spend most of their wall-clock time starting up, and more CPU does not
help. In a 2,232-host eclipse run the first ~1.1 simulated hours take ~6 wall-hours; a
~240-host run spends ~40 of its ~75 wall-minutes on its first ~6.6 simulated minutes, with 16,
32 or 64 Shadow workers alike. During that phase the simulation waits on one daemon at a
time: each newly started monerod holds everything up for ~17 wall-seconds, and the
start-time stagger (which must stay, because starting daemons together causes a RAM storm)
puts those startups strictly in a row.

This investigation must answer:
1. Where do the ~17 wall-seconds of a daemon start go inside Shadow?
2. Does disabling RPC SSL (`--rpc-ssl disabled` on monerod; `--rpc-ssl disabled
   --daemon-ssl disabled` on monero-wallet-rpc), which skips the RSA-4096 certificate
   generated at every start, cut the per-start time, and by how much?
3. If it does, make it monerosim's default. If not, find the real cost.

Done when: seconds per daemon start are measured with and without SSL on the same box, a
profile of one start names the dominant cost, and either the default is changed (committed,
smoke test passing) or the real cause is identified with evidence.

## What is already known

**Symptom.** A run's startup phase dominates its wall time and does not speed up with more
Shadow workers.
- ~240-host 1/10-scale eclipse config: the first ~6.6 sim-minutes take ~40 wall-minutes; the
  remaining ~290 sim-minutes take ~35. Total Shadow wall time 75-77 min with 16, 32 or 64
  workers (commit 817d662f, docs/CONFIGURATION.md).
- A colleague's 2232-host eclipse run: the first ~1.1 sim-hours took ~6 wall-hours.

**Mechanism (measured read-only on the colleague's live run, 128 workers).**
- During startup exactly ONE thread in the whole simulation uses CPU: the main thread of the
  monerod that just started (0.98-1.23 cores). The other ~8,900 threads are idle, all Shadow
  workers spin, and the ~430 simulated processes together make only ~740 context switches/s.
- Each new daemon holds the simulation for ~17 wall-seconds (relays 2377, 2378, 2379, 2380
  were busy one after another, ~17-18 s each).
- Relays start 4-5 sim-seconds apart, so the startups run strictly in sequence: with 2,220
  relays that is ~10 wall-hours.

**Staggering must stay.** Starting daemons together causes a RAM storm: a 1,146-node attempt
with a 1 s stagger was OOM-killed by the concurrent-startup memory spike
(docs/eclipse_reproduction.md, "Caveats"). Every stagger mode in docs/SCENARIO_FORMAT.md
(relay default 5 s; `auto`/`batched` = 5 s within each batch) starts daemons one at a time.
So the lever is a cheaper start, not parallel starts.

**Suspect: the RPC SSL certificate.** `contrib/epee/src/net_ssl.cpp` always generates an
RSA-4096 key and self-signed certificate when a daemon's RPC server starts with `--rpc-ssl`
at its default (`autodetect`); the cheap EC key is only an extra under `USE_EXTRA_EC_CERT`.
monero-wallet-rpc logs five `Generating SSL certificate` lines per start
(docs/20260724_cuprate_wallet_rpc.md) and probes TLS to its daemon before falling back to
plaintext. Native measurements on the big box (outside Shadow, monerod v0.18.5.1, OpenSSL
3.0.13):

| | Time |
|---|---|
| monerod start to "core RPC server initialized OK", default | 0.93, 1.33, 2.27 s (cert generation starts at 0.20 s) |
| same with `--rpc-ssl disabled` | 0.16, 0.16, 0.18 s |
| `openssl genrsa 4096` | 0.77 - 4.87 s (6 runs) |
| `openssl ecparam -name secp256k1 -genkey` | 0.011 s |

**Open puzzle: the 17 s may not be the certificate.** Inside Shadow the daemon's log shows
only ~1 ms of simulated time between `Generating SSL certificate` and `core RPC server
initialized OK`. With `native_preemption` on (defaults: preempt after 100 ms of CPU, advance
10 ms of sim time), 17 s of CPU there should show up as ~1.7 sim-seconds. So part or all of
the 17 s may be spent elsewhere, e.g. before the first log line. The profile in step 3
settles this.

History: nobody measured this before. Commit 339e9431 (2026-04-29) says monerod's startup is
"CPU-bound" (it freezes sims at 0 with `model_unblocked_syscall_latency: false`) but gives no
measurements; treat that explanation as unproven.

## Rules for the smaller box

- Check that nothing else heavy runs there (`pgrep -a -x shadow`, `uptime`).
- Run the arms one after another, never at the same time: the metric is wall time.
- Do not run large configs without a stagger (RAM storm).

## Steps

### 0. Setup

```bash
cd monerosim && git pull            # main at or after the commit that added this file
./setup.sh                          # only on a fresh box (~30-60 min); see README
~/.monerosim/bin/monerod --version  # expect v0.18.5.1
~/.monerosim/bin/monerod --help | grep -A1 -- '--rpc-ssl '
```

### 1. Native baseline on this box (2 minutes)

Reproduce the table above on this machine (its CPU differs). Default vs `--rpc-ssl disabled`,
three runs each:

```python
import os, shutil, subprocess, time
M = os.path.expanduser('~/.monerosim/bin/monerod')
def once(d, extra):
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d); log = f'{d}/m.log'
    p = subprocess.Popen([M, '--regtest', '--offline', '--no-igd', '--no-zmq', '--non-interactive',
        '--data-dir', d, '--log-file', log, '--log-level', '1', '--db-sync-mode', 'fastest',
        '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '47123',
        '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '47124'] + extra,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    try:
        while time.time() - t0 < 120:
            time.sleep(0.02)
            if os.path.exists(log) and 'core RPC server initialized OK' in open(log).read():
                return time.time() - t0
    finally:
        p.terminate(); p.wait()
for tag, extra in (('default', []), ('disabled', ['--rpc-ssl', 'disabled'])):
    print(tag, [round(once(f'/tmp/ssltest_{tag}_{i}', extra), 2) for i in range(3)])
```

Do the same for `~/.monerosim/bin/monero-wallet-rpc` (e.g. `--offline --wallet-dir <dir>
--rpc-bind-port <port> --disable-rpc-login --log-file <file> --log-level 1`): count the
`Generating SSL certificate` lines and time until the RPC port accepts connections, with and
without `--rpc-ssl disabled`.

### 2. Shadow A/B: seconds per daemon start

Arm A, `startup_ssl_default.scenario.yaml`: 3 miners (each with a wallet) + 60 daemon-only
relays started 5 s apart. It expands to 70 hosts (6 seeds and the DNS server are added).

```yaml
general:
  stop_time: 10m
  simulation_seed: 12345
  bootstrap_end_time: 5m
  enable_dns_server: true
  shadow_log_level: warning
  progress: true
  runahead: 100ms
  process_threads: 2
  native_preemption: true
  daemon_defaults:
    log-level: 1
    max-log-file-size: 0
    db-sync-mode: fastest
    no-zmq: true
    non-interactive: true
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  miner-{001..003}:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    start_time_stagger: 1s
    hashrate: [34, 33, 33]
  relay-{001..060}:
    daemon: monerod
    start_time: 30s
    start_time_stagger: 5s
```

Arm B, `startup_ssl_disabled.scenario.yaml`: identical, plus these lines under `general:`
(append to `daemon_defaults`, and add `wallet_defaults`). They render as
`--rpc-ssl=disabled` on all 69 monerods and the 3 wallets, and `--daemon-ssl=disabled` on
the wallets (checked on the big box):

```yaml
    rpc-ssl: disabled        # (inside daemon_defaults)
  wallet_defaults:
    rpc-ssl: disabled
    daemon-ssl: disabled
```

Run each arm, one after the other:

```bash
python3 scripts/generate_config.py --from startup_ssl_default.scenario.yaml -o startup_ssl_default.yaml
./run_sim.sh --config startup_ssl_default.yaml --name startup_ssl_default
# repeat with startup_ssl_disabled
```

While each arm runs, record which process keeps the simulation busy, from a second shell.
Save this as `busy_tracker.py` and run `python3 busy_tracker.py > tracker_<arm>.txt` once
Shadow has started:

```python
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
for p, s in busy.most_common(15): print(f'  {s:4d} s  {names[p]}')
```

Collect per arm:
1. Wall seconds until all relays have started: in `archived_runs/<run>/memory_samples.csv`,
   the wall time (`epoch` minus the first row's) when `sim_s` first reaches 330 (relays start
   at 30-325 s).
2. Median busy seconds per daemon from the tracker. On the big box arm A would be ~17 s.
3. Total Shadow wall time (`summary.txt`).

### 3. Profile one daemon start (where do the seconds go?)

During arm A, when the tracker prints a `busy: monero-relay-NNN`, get its PID
(`pgrep -f 'monero-relay-NNN'`) and sample it for ~10 s:

```bash
sudo perf record -F 499 -g -p <pid> -- sleep 10
sudo perf report --stdio --no-children | head -80
```

Or, without perf: `sudo gdb -p <pid> -batch -ex 'thread apply all bt 25'`, repeated a few
times. ptrace_scope may require sudo, as for the Shadow flock-hang diagnosis.

Read the profile like this:
- libcrypto (`BN_*`, `RSA_*`, `ossl_bn_*`): RSA keygen, so the hypothesis holds.
- libshadow_shim, ld-linux, signal handling: Shadow overhead around process start or
  preemption.
- randomx / argon2: RandomX cache init. lmdb / mdb: database setup.

If the profile points at preemption or the shim, add an arm C with `native_preemption: false`.

### 4. Decide and implement

**If arm B starts daemons several times faster**, make it monerosim's default:
- monerod: default `rpc-ssl` to `disabled` unless the user set it, the same way
  `src/agent/user_agents.rs` (~line 870) applies the `max-connections-per-ip` floor
  (`.entry(...)` so an explicit setting wins).
- monero-wallet-rpc (`src/process/wallet.rs`, which already pushes
  `--daemon-ssl-allow-any-cert` at ~line 60): add `--rpc-ssl=disabled` and
  `--daemon-ssl=disabled` unless `wallet_defaults` or `wallet_options` set them.
- Check that Python agents talk plain HTTP to daemons and wallets (`grep -rn "https"
  agents/`); with SSL disabled, an `https://` URL would break.
- The golden files in `tests/golden/*.yaml` will change: review the diff, then update them.
  Note that `cargo test` must run without a global `MONEROSIM_SKIP_SIM_BINARY_CHECK`.
- Docs: `docs/CONFIGURATION.md`, `docs/PERFORMANCE_AND_SCALE.md` (correct the 339e9431
  "CPU-bound startup" explanation with the measurement), and `CHANGELOG.md`. Side effect
  worth one line: with RPC SSL off, monerod and cuprate RPC both answer in plaintext, so the
  fingerprint in docs/20260724_cuprate_wallet_rpc.md no longer shows inside simulations.
- Validate: `scripts/smoke_test.sh quickstart`, then time the startup of a ~240-host config
  before and after (expect ~40 wall-min to a few minutes if the hypothesis holds).

RPC SSL has no effect on the P2P behaviour monerosim studies.

**If arm B is not much faster**, follow the profile. The cost is somewhere else in daemon
start (pre-main, the shim, RandomX, LMDB).

## Report back

- Native table (step 1) for this box, monerod and wallet-rpc.
- Per arm: wall seconds until all 60 relays started, median busy seconds per daemon, total
  Shadow wall time, run IDs.
- Profile: top frames of one busy daemon start.
- Decision and, if implemented, commit hashes and the smoke test result.
