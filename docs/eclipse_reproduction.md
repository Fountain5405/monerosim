# Reproducing the Monero unreachable-node eclipse attack (Nyx / Moros)

This documents a reproduction, with monerosim, of the eclipse attack from
**"Are Unreachable Nodes Truly Safe? Fully Eclipsing Monero's P2P Network!"**
(Shi, Zeng, Lan, Zhang, Han, Luo, Jin, Du, Wang — ACM CCS 2026; arXiv:2609.10260).

Because monerosim runs the real `monerod` daemon inside Shadow, the exact code
the attack targets — the 1,000-slot whitelist, 5,000-slot graylist, 12 outbound
slots, ~101 s `update_sync_search` connection refresh, and 60 s timed sync — is
genuine, not modelled. All work was done on an isolated git worktree at tag
**v0.3.1** running the pinned `monerod` v0.18.5.1 (paper used v0.18.4.3, the
prior patch). Everything here is simulation only; no live Monero node was attacked.

## The attack, in one paragraph

The victim is behind NAT/firewall: it makes outbound connections but accepts
none, so it depends entirely on its outbound peers for discovery. The attacker
never contacts it. It (N-I) poisons reachable nodes' whitelists with
attacker-controlled records; (N-II) those nodes relay the records into the
victim's graylist during ordinary timed sync — the only path to a NAT'd node;
(N-III) the victim's own `update_sync_search` drops ~one outbound peer every
101 s and refills it graylist-first, from the now attacker-dominated pool. Over
time all 12 outbound slots become attacker-controlled.

## What this reproduction shows

| Run | Nodes | Attacker endpoints | Final CTR | Honest whitelist OR | Victim graylist |
|-----|------:|-------------------:|-----------|--------------------:|-----------------|
| Control (no attackers)     |  36 |   0 | 0/12  | 0%     | —              |
| Injector (16 endpoints)    |  39 |  16 | 5/12  | ~53%   | benign → 0     |
| Injector (40 endpoints)    |  66 |  40 | 8/12  | ~69%   | benign → 0     |
| Real-node attack           | 134 | 120 | 11/12 | 88%    | 100% attacker  |
| Large-scale (Nyx)          | 585 | 550 | 9/12* | ~100%  | 97.8% attacker |
| Real-node Nyx, full scale  | 2,211 | ~1,000 | 7/12 | — | ~45% attacker |
| **Fake-peer Nyx (port diversity)** | 2,211 | 1,000 | **12/12** | — | graylist at 5,000 cap |
| **Fake-peer Nyx, onboard-first**   | 2,220 | 1,020 | **12/12** | — | graylist at 5,000 cap |
| Eclipse-at-birth (Moros)   | 126 | 120 | **12/12** | 100% | 93% attacker  |
| Eclipse-at-birth · paper scale | 963 | 951 | **12/12** | 96% | 100% attacker |

CTR = connection-takeover rate (attacker outbound peers, of 12). OR = peerlist
occupation rate (attacker fraction). \*The 585-node CTR was still climbing when
the 3 h sim ended (see "Findings").

**Full 12/12 eclipse is reached** against a newborn victim (eclipse-at-birth),
with a time-to-eclipse of 30.8 min (paper: ~27) in the 126-node run. Against an
established victim, takeover reaches 11/12, the last slot clinging to an honest
hardcoded seed. Scaled to the paper's size — a **963-node** run with **951 attacker
endpoints** — the newborn victim was *born fully eclipsed*: on its first successful
poll it already held all 12 outbound slots on attacker nodes (zero honest peers,
zero inbound), and held a solid **12/12** across the entire 35-min observation
window with no oscillation (measured; run `20260914_100749_eclipse_birth_paperscale`,
0 processes failed).

### Full eclipse of an *established* unreachable node (the paper's Nyx)

The rows above marked 12/12 at 2,200+ hosts are the paper's actual threat model:
not a newborn, but an **established** unreachable victim that has already built a
healthy benign peerlist and is then taken over. Reaching it needed two things the
smaller runs lacked — the regenerated 5,000-node CAIDA GML
(`gml_processing/5000_nodes_caida_with_loops.gml`; AS >= 1200 previously mapped to
loopback/CGNAT octets Shadow's DNS rejects), and a **port-diversity fake-peer**
attacker rather than real monerod attackers.

That second point is the load-bearing one. Real-node Nyx at the same scale
plateaued at **7/12** with the graylist only ~45% attacker: 1,000 single-port /24s
simply cannot out-number 1,199 benign /24s. Presenting several ports per /24 puts
~5,000 connectable (IP,port) records against the victim's 5,000-slot graylist cap,
which flips graylist domination and completes the eclipse.

The strongest run is `20260916_215526_nyx_onboardfirst` (2,220 hosts): seeds and
miners displaced by 146 min, first 12/12 at **633 min**, ending at
`out_attacker 12, out_benign 0, out_other 0`. It is a full eclipse but **not a hard
lock** — across the 204 polls after first 12/12 the attacker held a mean of
**11.45/12**, hitting exactly 12/12 in 46% of polls, with a trickle of benign peers
(mean 0.56) briefly reclaiming isolated slots as 1,199 honest nodes keep
re-advertising against the ~101 s `update_sync_search` rotation. Per-poll metrics
and the full caveats are in
`analysis/eclipse/results/20260916_215526_nyx_onboardfirst/`.

## Findings

1. **Core claim holds.** An unreachable node is eclipsed with no inbound access,
   driven entirely by the protocol's own timed-sync + `update_sync_search`.
2. **Eclipse completeness scales with distinct-/24 *connectable* endpoints**, not
   with how many records are injected. A captured outbound slot requires a
   *successful* connection to a real attacker endpoint, and Monero's /24 filter
   forces the 12 outbound peers into 12 distinct /24s. Injecting unreachable
   "trash" evicts honest entries but cannot become connections, so it *lowers*
   takeover. Dose-response of final CTR vs endpoints: 0→0, 16→5, 40→8, 120→11, 951→12 —
   the curve reaches its 12/12 ceiling at ~950 endpoints, measured directly.
   This independently confirms the paper's load-bearing assumption of ~1,000 /24
   subnets (also flagged by the manuscript reviewer).
3. **At scale, takeover is convergence-rate-limited.** The 585-node run poisoned
   as hard as the paper (graylist 97.8% attacker) but reached only 9/12 in 3 h
   because `update_sync_search` replaces ~one peer per 101 s while always-reachable
   seeds re-inject a trickle of honest records. Bigger networks propagate the
   takeover more slowly; full 12/12 needs a longer run.
4. **The clean 12/12 comes via eclipse-at-birth (Moros).** A newborn victim
   joining the poisoned network never establishes honest connections to displace,
   so its first 12 outbound are attacker-controlled from the start. At paper scale
   (951 attacker endpoints) this is even sharper than at 126 nodes: the victim is
   born at 12/12 (no ramp) and never oscillates, because the honest peer pool it
   could fall back to is vanishingly small.

## How to reproduce

From the worktree root, with the venv active (`source venv/bin/activate`) and the
pinned binaries installed in `~/.monerosim/bin` (`monerod` v0.18.5.1, Shadow fork
v0.2.4 — `setup.sh` installs these). The Nyx scenarios that record the target's
full peer list (`eclipse_nyx_*`, `eclipse_socketbuf_verify`) run their dumping
nodes on `monerod-hf`, which `./setup.sh --sim-binary` installs (`--hardfork` is
accepted as a synonym).

**What that binary is.** `--sim-binary` builds ONE daemon, `monerod-sim`: vanilla
monerod at `monero.pin` plus every patch under `patches/`, each flag-gated and
off by default — `fakechain-hard-forks`, `sim-hash-interval-ms` /
`sim-rx-full-dataset`, `sim-relay-alt-blocks` and `peerlist-dump-file`. It then
installs `monerod-hf` as a **symlink alias** to it, so scenarios naming either
work. Carrying the other three patches does not affect these runs: with their
flags absent the code is dormant and the daemon behaves as stock monerod (the
reasoning is in `docs/PEERLIST_DUMP_PATCH.md` §4). The primary
`~/.monerosim/bin/monerod` stays byte-for-byte vanilla, and every other node in
these scenarios runs it. `run_sim.sh` preflight fails the run if a config asks
for `--peerlist-dump-file` but the installed binary lacks the patch, so a missing
build is a loud error rather than silently absent dumps. The dump analyser is
`analysis/eclipse/analyze_peerlist_dumps.py`.

**What the large runs cost.** The paper-scale and full-scale Nyx scenarios are
not laptop-sized. Measured: ~0.28 GB of *available* memory per relay, which puts
the 2,211-host runs at **~620 GB** (`test_configs/eclipse_nyx_full.scenario.yaml`;
the per-host figure comes from the 963-host run in
`gml_processing/AS_IP_ALLOCATION_NOTE.md`), and **~13 h of wall clock for a 12 h
sim** (commit `a6d2f261`, the 2,211-host run). A run at this scale monopolises the
machine.

The 126-node `eclipse_birth` scenario is the right starting point: it is the run
that reproduces the paper's time-to-eclipse figure (30.8 min vs the paper's ~27).
Its memory requirement has never been measured — extrapolating the same per-relay
figure suggests roughly 35 GB, but treat that as an estimate rather than a
documented number.

```bash
# 1. Expand a scenario (run_sim.sh does NOT auto-expand .scenario.yaml here)
python -m scripts.scenario_parser test_configs/eclipse_birth.scenario.yaml \
    -o test_configs/eclipse_birth.expanded.yaml

# 2. Run it (one at a time; the box is shared). With archiving on (the
#    default) the sidecars land in archived_runs/<run_id>/: eclipse_metrics.jsonl
#    at the run root, eclipse_probe's raw_probe/ under shared/. The older
#    --no-clean --no-archive recipe still works and keeps them in the per-run
#    /tmp shared dir instead (--no-archive without --no-clean deletes them).
./run_sim.sh --config test_configs/eclipse_birth.expanded.yaml \
    --no-build --no-monitor

# 3. Analyse (finds the run's metrics from the run_sim stdout log, prints the
#    paper-comparison table, writes CSV + SVG under analysis/eclipse/results/)
python analysis/eclipse/analyze_run.py <path-to-run_sim-stdout.log>
```

Shadow is deterministic in virtual time and every scenario pins
`simulation_seed: 12345`, so re-running the same config reproduces the same
metrics exactly.

### Peer-list dumps (B and OR)

Scenarios that set `peerlist-dump-file` write per-entry peer lists that the
`eclipse_metrics.jsonl` sidecar does not carry; B and OR are computed from
those dumps, not from the sidecar. Where they land depends on the flags:

| Invocation | Dumps end up in |
|---|---|
| default (archiving on) | `archived_runs/<run_id>/daemon_logs/<node>/peerlist_dump.jsonl` |
| `--no-clean --no-archive` (the recipe above) | `$DAEMON_DATA_BASE/monero-<node>/fake/` — analyse in place |
| `--no-archive` **without** `--no-clean` | **deleted** with the daemon data dirs |

```bash
python analysis/eclipse/analyze_peerlist_dumps.py archived_runs/<run_id>
# ...or, for a raw/preserved tree:
python analysis/eclipse/analyze_peerlist_dumps.py /tmp/monerosim-<run_id>
```

Archiving of the dumps was added 2026-09-20; runs archived before then kept
only `bitmonero.log`, so their dumps exist only in preserved raw-data trees.

## Scenarios (`test_configs/eclipse_*.scenario.yaml`)

| Scenario | Purpose |
|----------|---------|
| `eclipse_smoke`         | Tiny pipeline validation (12 attacker vs 6 benign). |
| `eclipse_baseline`      | Control: no attackers; CTR must stay 0/12. |
| `eclipse_attack`        | Real-node Nyx attack (120 attacker vs 8 benign). |
| `eclipse_inject_smoke`  | py-levin injector in Shadow (16 endpoints + 2 injectors). |
| `eclipse_inject_attack` | Injector capstone (40 endpoints + 3 injectors). |
| `eclipse_large`         | Large-scale Nyx (550 attacker, 585 nodes, 3 h). |
| `eclipse_birth`         | Eclipse-at-birth / Moros — reaches 12/12. |
| `eclipse_birth_large`   | ~720-node Moros (batched onboarding, safe large). |
| `eclipse_birth_paperscale` | ~963-node Moros at paper scale — clean 12/12 (12-24 h). |
| `eclipse_conv`          | Long convergence attempt (kept for reference; slow). |
| `eclipse_nyx_full`      | Full-scale Nyx with REAL monerod attackers (~2,211 hosts) — plateaus at 7/12. |
| `eclipse_nyx_fakepeer`  | **Full-scale port-diversity fake-peer Nyx — reaches 12/12 against an established victim.** Onboard-first timing. 12 h+ sim, ~13 h wall. |
| `eclipse_nyx_smoke_onboardfirst` | Fast smoke of the onboard-first sequencing (200 benign, 75 min). |
| `eclipse_socketbuf_verify` | Verifies the peer-list file dump under a saturated 5,000-entry graylist. |

**Unreachable target, deterministically:** `general.reachable_fraction: 0.0`
plus a per-node `daemon_options: {hide-my-port: false}` exemption on every other
relay leaves exactly one host — the target — firewalled by Shadow
(`blocked_inbound_ports: [18080]`). Seeds and miners are always reachable.

## Agents (`agents/`)

- **`eclipse_monitor.py`** — script-only measurement agent. Each poll it reads
  the agent registry, classifies every node attacker/benign/target by its
  `eclipse_role` attribute, and via RPC computes CTR (`get_connections` on the
  target), whitelist/graylist occupation and benign count B (the direct
  `/get_peer_list` endpoint), and benign-node OR. Writes `eclipse_metrics.jsonl`
  to the shared dir; `run_sim.sh` archives it to the run-dir root.
- **`eclipse_injector.py`** — the py-levin injector: a Monero Levin *responder*
  that, when a daemon dials it, answers HANDSHAKE / TIMED_SYNC with a chosen
  `local_peerlist_new` (attacker listener records, optional trash). Peers flow
  responder→initiator in Monero, so the injector is a reachable node that others
  dial; it then floods their graylists.
- **`levin_lib.py`** — a minimal Monero Levin framing + epee portable-storage
  codec (from the wire format up) used by the injector. Validated against a real
  `monerod`: the daemon ingested every injected record via one genuine handshake.

## Analysis harness (`analysis/eclipse/`)

- `analyze_run.py` — one-shot: parse a run_sim log → find metrics → print table +
  write CSV/SVG. `analyze.py` — the underlying analyzer. `inspect_metrics.py`,
  `locate_metrics.py` — debugging helpers. `verify_config.py` — pre-run check that
  the firewall lands only on the target and roles/`/24`s are correct.
  `test_codec.py` / `test_injector_standalone.py` — codec round-trip and the
  standalone injector-vs-monerod validation. `chartdata.py` — emit chart series.
- `report.html` — the published visual report.
- `results/<run>/` — per-run `eclipse_metrics.jsonl`, `eclipse_timeseries.csv`,
  and SVG figures.

## Caveats / threats to validity

- **Scale.** The paper ran 1,200 nodes; these runs span ~10² up to a **963-node**
  network — approaching the paper's size, bounded by Shadow's documented ~1,000-host
  scheduler cliff (`docs/PERFORMANCE_AND_SCALE.md`) and a shared, memory-heavy host.
  Onboarding >~600 nodes uses batched staggering (`start_time_stagger: auto`) to
  avoid the concurrent-startup memory spike that OOM-killed a naive 1,146-node/1 s
  attempt. Absolute timings still need not match; the mechanism, trends, and the
  full 12/12 at paper scale are what reproduce.
- **Honest seeds.** monerosim injects 6 real hardcoded seeds, always reachable; a
  persistent seed connection held the established-victim case at 11/12.
- **/24 filter kept enabled.** The paper disabled it (its 1,000 IPs sat in few
  /24s); here every attacker gets its own /24, so the stock filter stayed on — a
  more conservative setting.
- **Client version** v0.18.5.1 vs the paper's v0.18.4.3 (reviewer: attack is
  marginally stronger on v0.18.5.x).
- **No mainnet.** The paper's Moros was run against controlled mainnet targets;
  this reproduction is entirely in simulation.
