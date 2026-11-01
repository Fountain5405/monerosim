> Status: design record of 2026-08-02, kept as history; it may not match the current code. Current docs: docs/README.md.

# Cuprate 0.1.0-preview: upstream merge, and a 300-node validation of canonical cuprate

**Date:** 2026-08-02
**Status:** Complete (one result unconfirmed — see §3)
**Upstream PR:** [Cuprate/cuprate#663](https://github.com/Cuprate/cuprate/pull/663) — merged as `e3a869d`
**Run:** `archived_runs/20260801_141334_cuprate_exp_cuprate_pr663` (partial, salvaged — see §4)
**Companion:** [Cuprate at scale](20260724_cuprate_scale_experiment.md), [Connection matrix](20260725_cuprate_connection_matrix.md)

## TL;DR

- Cuprate released **`cuprated-0.1.0-preview "Kesterite"`**. For monerosim it changes **essentially nothing**: all 17 mappable changelog PRs were already ancestors of the commit we had been running.
- **Our `seed_nodes` patch is now upstream.** PR #663 was merged within ~3 hours, including a `--seed-node` CLI argument added during review. **monerosim no longer needs a cuprate fork.**
- The merged code was validated on the 300-node network: **306/306 nodes reached full propagation**, block latency unchanged, and transaction propagation **2.46× faster than an all-monerod network**.
- **Unconfirmed:** a uniform **~7% transaction-propagation slowdown** versus cuprate 0.0.9. Systematic-looking but n=1; blocks are unaffected. Needs a second seed before anyone acts on it.
- The run **froze at 81%** because another user on the shared box consumed 854 GB of RAM. Not our code — our whole 307-process simulation was 95.7 GB. Data was salvaged and the comparison re-cut to a matched window.

## Question

Cuprate cut its first preview release. Three things needed answering:

1. Does the release change anything that affects the simulator?
2. Can we stop maintaining a fork?
3. Does the released code still behave equivalently at 300-node scale?

## What the release actually changed

The 0.1.0-preview changelog is written against 0.0.9 and reads like a major drop — "initial wallet support", regtest/fakechain, graceful shutdown, Tor improvements. Almost none of it was new *to us*, because we tracked `main` closely.

Verified mechanically with `git merge-base --is-ancestor`, not by reading the changelog: **all 17 changelog PRs that map to a commit were already ancestors of our base `d57d59d`** — including regtest (#607) and the entire wallet-RPC series (#624, #631, #634, #636, #637, #641, #647, #653, #654). The wallet-RPC support the release announces is the same code we runtime-proved on 2026-07-24, a week before the tag existed.

Genuinely new to us, in the 8 commits between our base and the tag:

| Change | Effect on monerosim |
|---|---|
| Offline mode (#656) | None — new config field with a default; we don't set it |
| Custom allocators (#658) | None — `mimalloc`/`jemalloc` are **opt-in** cargo features, not default. A default global-allocator swap under Shadow would have been a real risk |
| Docker/Alpine/BSD support (#659) | None |
| `tapes` DB-format bump (#660) | Requires fresh data dirs; we wipe per run |
| Alt-block missing-tx storage fix (#599) | Correctness fix in a tx path — a suspect for §3 |
| `SyncerHandle` → `BlockchainInterface` (#626) | Internal rename plus syncer changes |
| **RPC router narrowed** `.all()` → explicit allowlist + `.fallback()` (404) | **None in practice** — see below |
| P2P defaults | **Unchanged** (32 outbound / 8 extra / 128 inbound) |

The RPC narrowing was the one change that looked dangerous. It is harmless here: all 10 `bin_*` endpoints survive, so wallet sync is untouched, and of the dropped `other_*` routes monerosim only ever *calls* `start_mining` and `generateblocks` — both miner-only, and miners are monerod-only (`can_mine: false`). `get_peer_list`, `get_transaction_pool`, `sync_info` and `mining_status` exist in `agents/monero_rpc.py` but are never invoked. Confirmed empirically: **zero HTTP 404s** across the smoke test.

P2P defaults being unchanged matters — it means the 2.4× degree gap and the ~80/20 cadence-vs-fan-out split from the companion documents carry over unmodified.

## The fork is gone

Canonical cuprate could not previously run an isolated network: `clear_net_seed_nodes()` returns `[]` for `Network::FakeChain`, with no config field and no CLI flag to supply peers, so a node panics with *"No seed nodes available to get peers from"*. That was the entire reason for the fork.

The patch was submitted as [#663](https://github.com/Cuprate/cuprate/pull/663) and **merged the same day** by Boog900. Review from SyntheticBird45 asked for three changes (drop a redundant comment; use `extend_from_slice` in two places), all applied. The PR grew a second commit during review adding a repeatable CLI argument:

```console
$ cuprated --regtest --seed-node 127.0.0.1:18080
```

so a multi-node regtest now needs no config file at all. That commit removes the `const` qualifier from `Args::apply_args`, since extending a `Vec` is not a const operation — called out explicitly in the PR for reviewers.

**The merged upstream source is byte-for-byte identical to the tree this experiment's binary was built from.** monerosim is now wired to canonical `Cuprate/cuprate`; the fork (`Fountain5405/cuprateformonerosim`, branch `feat/config-seed-nodes-0.1.0`) is retained for instant revert but carries nothing upstream lacks.

## Experimental design

Single-variable A/B. `test_configs/cuprate_exp_cuprate_300_8h.yaml`, seed `20260723`, 302 agents → 306 daemons (**180 cuprate / 126 monerod**), 8 simulated hours. The only thing that differs between arms is the `cuprated` binary; config, seed, topology and monerosim build are identical (the one monerosim commit in between is comment-only).

| Arm | cuprated | Archive |
|---|---|---|
| **pr663** | 0.1.0-preview + merged #663 (`438a3c5`, ≡ upstream `e3a869d`) | `20260801_141334_cuprate_exp_cuprate_pr663` |
| **0.0.9** | 0.0.9 + our fork patch (`d57d59d` base) | `20260726_150824_cuprate_exp_cuprate32_reassigned` |
| **baseline** | none — 306 monerod | `20260723_212123_cuprate_exp_baseline` |

Because the pr663 arm was cut short at 6h27m (§4), **all three arms are truncated to a common 0 → 6h00m window** before comparison. `prop_delta.py` has no windowing option, so events were dumped with `--csv` and re-cut identically: a hash is included only if first seen inside the window, and only observations inside the window count. The 6h cut leaves margin below the 6h27m truncation so no transaction is counted mid-propagation.

## Results

### 1. The truncation did not bias the comparison

The pr663 arm produced 921 transactions over 6h27m against the reference's 2189 over 8h — superficially half the rate, which would have suggested a resource-starved and therefore untrustworthy run.

It is an artifact of when transactions are generated. Within the matched window the arms are near-identical:

| arm | 0-1h | 1-2h | 2-3h | 3-4h | 4-5h | 5-6h |
|---|---|---|---|---|---|---|
| pr663 | 0 | 0 | 0 | 6 | 224 | 591 |
| 0.0.9 | 0 | 0 | 0 | 6 | 225 | 595 |
| baseline | 0 | 0 | 0 | 6 | 208 | 533 |

**821 vs 826 transaction hashes** in the window. Transaction generation ramps sharply after hour 4, so the missing 1268 transactions all belong to hours 6–8 that our run never reached. The run was not degraded — consistent with Shadow being a discrete-event simulator whose results do not depend on wall-clock or host load.

### 2. Network health and propagation reach — equivalent

**Reach is 306.0 at median, p90 and max in all three arms.** Every block and every transaction reached every node, including all 180 cuprate nodes. 118 blocks in each arm within the window.

Block propagation is unchanged by the version bump:

| arm | block median | monerod-only | cuprate-only |
|---|---|---|---|
| pr663 | **0.100 s** | 0.109 | 0.075 |
| 0.0.9 | **0.099 s** | 0.107 | 0.073 |
| baseline | **0.137 s** | 0.137 | — |

### 3. Transaction propagation — 2.46× faster than all-monerod, but ~7% slower than 0.0.9

| arm | tx hashes | median | p90 | monerod-only | cuprate-only |
|---|---|---|---|---|---|
| **pr663** | 821 | **2.051 s** | 3.536 | 2.361 | 1.803 |
| **0.0.9** | 826 | **1.911 s** | 3.292 | 2.217 | 1.687 |
| **baseline** | 747 | **5.050 s** | 6.029 | 5.050 | — |

The headline finding from the scale experiment **holds on canonical upstream code**: a half-cuprate network propagates transactions **2.46×** faster than all-monerod (2.64× for the 0.0.9 arm).

Against 0.0.9, however, the merged code is **consistently slower**:

| metric | 0.0.9 | pr663 | Δ |
|---|---|---|---|
| median | 1.911 | 2.051 | **+7.3%** |
| p90 | 3.292 | 3.536 | **+7.4%** |
| monerod-only | 2.217 | 2.361 | **+6.5%** |
| cuprate-only | 1.687 | 1.803 | **+6.9%** |

Two things make this look systematic rather than noise:

- **The shift is uniform across quantiles and both implementations.** Run-to-run variance typically appears in a tail, not as a flat offset. (Monerod-only latency moving is expected in a mixed network — monerod's observed latency depends on the cuprate peers relaying to it.)
- **Blocks are unaffected** (0.100 vs 0.099). If the host's memory pressure had contaminated timing, block latency would have moved too. It did not, so whatever this is, it is specific to transaction handling.

**This is not a confirmed result.** It is n=1 per arm with no variance estimate and no identified mechanism. The plausible suspects from the release diff are the `tapes` DB-format bump and the alt-block missing-tx storage fix (#599) — both touch transaction storage, neither touches block relay, which fits the block/transaction split. That is a hypothesis, not a finding. **A confirmation run at a different seed is required before reporting anything upstream.**

### 4. The run froze at 81% — external cause

The simulation stopped advancing at **6h27m59s of 8h (80.8%)** and stayed frozen for **17h 46m** of wall time before being killed.

Cause: box-wide memory exhaustion, from another user's workload.

| | RSS |
|---|---|
| `user1` — 96 `monero-wallet-rpc` | **854.6 GB** |
| `user1` — 111 R processes | 17.5 GB |
| **our entire simulation (307 procs)** | **95.7 GB** |

With 2 GB free of 1007 GB and swap exhausted, the machine thrashed; Shadow kept spinning (60 cores) without advancing simulated time. Our own resident memory was being progressively reclaimed, so recovery became less likely over time, not more.

A useful datum falls out of the incident diagnosis: **`cuprated` averages 323 MB RSS against `monerod`'s 312 MB** (n=180 and 126, median 323 / 311, max 328 / 331). Near-identical, tight distribution — the 0.1.0-preview binary has no memory regression, and the `tapes` DB bump did not inflate footprint.

Salvage: `shadow.data` and the 13 GB of live daemon data under the per-run `/tmp` namespace were preserved into the archive, and `daemon_logs/` was reconstructed by hand (`run_sim.sh` never reached its archiving step). Both implementations' logs survived intact and end at the same simulated instant, which is what makes a matched-window comparison valid.

## Caveats & limitations

- **The ~7% regression is unconfirmed** — single seed, single run per arm, no mechanism identified. Do not act on it without a repeat.
- **The pr663 arm covers 6h of 8h.** All comparisons are re-cut to that window, including the two complete arms, so the comparison is matched — but it excludes hours 6–8, where over half of all transactions occur.
- **The `--seed-node` CLI argument is not covered by this experiment.** monerosim writes a `Cuprated.toml` and never passes the flag, so only the config-field path is exercised here. The flag was verified to compile, pass clippy at `-D warnings`, and appear correctly in `--help`, but has no runtime evidence from this work.
- **Wallet paths are only partially exercised** — sync and send are proven, but rescan-from-height, multisig and cold signing are not.
- The 306-node network is 59% cuprate, not 50%: `cuprated: 0.61` maps onto an eligible pool that commit `b0d6a064` widened. Both arms share it, so the A/B is unaffected.

## Conclusion

Canonical cuprate is now sufficient for monerosim. The fork existed solely to supply seed nodes to an isolated FakeChain network, and that capability is upstream as of `e3a869d`.

The released code sustains a 306-node mixed network with full block and transaction propagation to every node, unchanged block latency, and transaction propagation 2.46× faster than an equivalent all-monerod network. The one open question is a ~7% transaction-propagation regression against 0.0.9 that is consistent enough to take seriously and too thinly evidenced to report.

## Reproducibility

```bash
# canonical cuprate (no fork required as of e3a869d)
git -C ../cuprate checkout canonical          # tracks upstream/main
git -C ../cuprate pull --ff-only
nice -n10 cargo build --release -p cuprated --manifest-path ../cuprate/Cargo.toml
cp ../cuprate/target/release/cuprated ~/.monerosim/bin/cuprated
cuprated --version                            # expect commit e3a869d or later

# the run
./run_sim.sh --config test_configs/cuprate_exp_cuprate_300_8h.yaml --name <name>

# matched-window comparison: dump events, then re-cut all arms identically
python3 analysis/prop_delta.py <run>/daemon_logs --csv /tmp/ev.csv
```

`prop_delta.py` has **no** time-window flag; the windowing above was done over its `--csv` output. `conn_matrix.py` does have `--window=<ERE>` (e.g. `--window='^2000-01-01[ T]04:0[0-4]:'`).

To revert to the fork: `git -C ../cuprate checkout feat/config-seed-nodes-0.1.0`, rebuild, and update `cuprate.pin`.

## Follow-ups

- **Confirm or dismiss the ~7% regression** at a second seed. Only then is it worth raising with Cuprate.
- **Runtime evidence for `--seed-node`** — a small Shadow run with peers supplied purely on the command line and no seeds in config.
- **`simulation_monitor` is blind to cuprate nodes** (`agents/simulation_monitor/agent.py:233` hardcodes `bitmonero.log`), so `summary.txt` "Nodes online" and "Sync %" undercount on mixed runs — it reported 126/306 throughout this run while all 306 daemons were live. Needs a cuprate log parser, not just a wider glob.
- Cuprate mining remains the last capability gate (`GenerateBlocks` is a stub upstream), so miners stay monerod-only.
