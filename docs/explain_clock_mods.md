# How `--bootfast` and `--allfast` work

A plain-language explanation of the two clock flags of `run_sim.sh`. The
measurements behind it are in
[`20261003_startup_cost.md`](20261003_startup_cost.md); the knobs and their
trade-offs are summarized in
[`PERFORMANCE_AND_SCALE.md`](PERFORMANCE_AND_SCALE.md#start-up-cost).

## Short version

Every Monero program waits for 0.1 s of clock time when it starts. Under
Shadow that wait cost ~16 real seconds per program start, and starts happen
one after another, so large runs spent hours on it. `--bootfast` and
`--allfast` both cut a start to under half a second. `--bootfast` does it
without changing anything else in the simulation, so prefer it.

```bash
./run_sim.sh --config my.yaml --bootfast
```

## How to use it

**1. Install Shadow v0.2.5 or later** (shadowformonero). Check with
`~/.monerosim/bin/shadow --version`; if it says v0.2.4 or older, run
`./update.sh --shadow --rebuild` (or `./setup.sh`). An older Shadow refuses a
config that has the setting: `unknown field 'unblocked_vdso_busy_threshold'`.

**2. Turn it on, any one of these ways.** All produce exactly the same
simulation.

- For every run of a config: add this block at the top level of the config
  (next to `general:`), so nobody has to remember the flag. It works in a
  compact `.scenario.yaml` (`generate_config.py --from` copies it into the
  expanded config) and in an expanded config:

  ```yaml
  performance:
    unblocked_vdso_busy_threshold: 10000   # what --bootfast sets
    unblocked_vdso_busy_latency: 1 us
  ```
- For one run: `./run_sim.sh --config my.yaml --bootfast`.
- Generating by hand: `monerosim --config my.yaml --bootfast --output dir`.

`run_sim.sh` and `monerosim` read only expanded configs; expand a compact
`.scenario.yaml` first (`scripts/generate_config.py --from x.scenario.yaml -o
x.yaml`). A flag overrides the config's `performance:` values.

**3. Check a run has it:** its `shadow_output/shadow_agents.yaml` contains
`unblocked_vdso_busy_threshold: 10000` under `experimental:`.

### Where the setting goes

`--bootfast` is a `run_sim.sh` option only because `run_sim.sh` is the usual
way to start a run. It is really a Shadow setting:

```
run_sim.sh --bootfast
  -> monerosim --bootfast              (the config generator)
     -> performance: block, as above   (same as writing it in your YAML)
        -> experimental:               (in the run's shadow_agents.yaml)
             unblocked_vdso_busy_threshold: 10000
             unblocked_vdso_busy_latency: 1 us
           -> read by Shadow when it loads that file
```

The `shadow` process is not started with a `--bootfast` flag; it reads the
setting from its config file like every other Shadow option. If you run
Shadow by hand on a generated config, the setting is already in the file.
Shadow v0.2.5 also takes it on its own command line, as
`--unblocked-vdso-busy-threshold 10000 --unblocked-vdso-busy-latency 1us`.
`run_sim.sh` checks the installed Shadow's version only when `--bootfast` is
given; with the YAML block, an older Shadow stops at launch with the error
above.

## How time works in Shadow

Programs inside Shadow do not see a real clock; they see a simulated one.
That clock does not move on its own while a program is busy. Each time a
program asks "what time is it?", Shadow counts the question itself as having
taken a tiny amount of time: 10 nanoseconds. So it is like a clock that only
ticks when you look at it, a tiny step per look.

## The problem

Every Monero program (monerod and monero-wallet-rpc) does a small check when
it starts: "keep looking at the clock until 0.1 seconds have passed". On a
real computer that takes 0.1 seconds. In Shadow each look moves the clock
only 10 ns, so the program has to look **10 million times**. Each look costs
the real computer about 1.6 µs of work, so every start took about 16 real
seconds. Starts are staggered, one after another, so they add up: the
2,232-host eclipse run has 1,214 monero processes and spent its first 7.6 of
~22 wall-hours starting them.

## `--allfast`

Every look at the clock counts as 1 µs instead of 10 ns. The start-up check
then needs about 100,000 looks and is done in a fraction of a second.

The catch: this applies to every look by every program for the whole run.
Programs look at the clock 100-180 times a second during normal work, so
they appear very slightly slower than before: a block reaches each next node
up to about 0.1 ms later. Small, but it is a change.

## `--bootfast`

Shadow keeps a running count for each thread of each program:

- Every time the thread looks at the clock, Shadow adds 1 to the count, then
  prices **that one look**: 10 ns if the count is 10,000 or less, 1 µs if it
  is above 10,000.
- Whenever the thread does anything else (sends a message, writes a log
  line, sleeps), the count goes back to 0.

Nothing is charged after the fact: looks already charged 10 ns stay at 10 ns.
Only the looks after the 10,000th in a row cost more.

A program doing normal work looks at the clock now and then:

| What the program does | Count | That step is charged |
|---|---|---|
| looks at the clock | 1 | 10 ns |
| looks at the clock | 2 | 10 ns |
| writes a log line | back to 0 | as usual |
| looks at the clock | 1 | 10 ns |

Its count never gets anywhere near 10,000, so it is charged exactly as
without the flag.

The start-up check does nothing but look at the clock until 0.1 s has
passed:

| Looks | Count | Each look is charged | Simulated time so far |
|---|---|---|---|
| 1st to 10,000th | 1 to 10,000 | 10 ns | 0.1 ms |
| 10,001st onward | above 10,000 | 1 µs | 0.1 s after ~100,000 more looks, so the check ends |

So the check ends after about 110,000 looks instead of 10 million.

Why the count tells us anything: a program doing real work does something
else between clock looks. Looking at the clock 10,000 times in a row with
nothing in between only happens when a program is waiting for time to pass.
Charging more per look then just gets it to the time it is waiting for in
fewer looks; it still waits until the same simulated moment.

## Why the 10,000 line is safe

For every program in three kinds of simulation (the quickstart, an eclipse
attack, selfish mining), we counted the longest streak of clock looks with
nothing else in between:

| Program | Longest streak during normal work |
|---|---|
| monerod (and `monerod-sim` with native mining) | 371 |
| monero-wallet-rpc | 14 |
| Python agents, DNS server | 31 |
| the start-up check of any Monero program | 10,000,000 |

10,000 sits far above anything normal and far below the start-up check. In
those three simulations only the start-up check of each Monero program ever
went past 10,000 looks in a row, so that is the only place the higher charge
applies. Not yet checked:
cuprated, runs with thousands of hosts, and transaction loads heavier than
the quickstart's.

## The two flags side by side

| | During normal work | During the start-up check | Daemon start | 70-node test run |
|---|---|---|---|---|
| no flag | 10 ns per look | 10 ns per look | ~16 s | ~18 min |
| `--allfast` | 1 µs per look | 1 µs per look | ~0.4 s | ~1.5 min |
| `--bootfast` | 10 ns per look | 10 ns for the first 10,000 looks, then 1 µs | ~0.4 s | ~1.5 min |

Notes:

- `--bootfast` needs shadowformonero v0.2.5 or later (it adds the running
  count to Shadow's shim); `run_sim.sh` refuses `--bootfast` if the installed
  Shadow lacks it. `--allfast` works with any Shadow.
- The two flags cannot be combined.
- They also help daemons that restart in the middle of a run (turnover,
  upgrade phases), which pay the start-up cost again on every restart.
- Separately, turning the RPC SSL certificate off saves about another second
  per start, but it is not the default: with SSL off, wallets stop syncing once
  transactions flow (`docs/20261009_rpc_ssl_off_wallet_stall.md`).
- In config files, the same settings are `performance:` knobs:
  `unblocked_vdso_busy_threshold` and `unblocked_vdso_busy_latency` for
  `--bootfast`, `unblocked_vdso_latency` for `--allfast`.
