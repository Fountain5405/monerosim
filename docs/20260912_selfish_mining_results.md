# Selfish-Mining Apparatus — Results & Validation (2026-09-12)

This is the human entry point for validating the selfish-mining apparatus
(`docs/SELFISH_MINING.md` describes how it works). Every run below is archived;
for each you get the config, the archived run-dir id, the one command that
reproduces the numbers, the numbers themselves, and how to check them against
theory. Everything ran on branch `feat/native-mining`.

## How to reproduce any run

```bash
# 1. generate + run the sim (nice'd; ~30–60 min wall per 6 h config)
./run_sim.sh --config <config.yaml> --name <label>
# 2. analyse the archived run (attacker share, realized gamma, vs theory)
venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run_dir>
```

The analysis attributes each block on an honest node's **ground-truth canonical
chain** (recorded by the attacker's bridge to `canonical_chain_<bridge>.json`)
to the miner that found it (matching the block hash from the miners' logs), then
reports the attacker's share of the canonical chain, the realized γ, and the
Eyal–Sirer prediction. The theory value is `es_revenue_share(α, γ)`:

```
R(α,γ) = [ α(1-α)^2 (4α + γ(1-2α)) - α^3 ] / [ 1 - α(1 + (2-α)α) ]
```

`realized gamma` = of the forks that an **honest**-found next block resolved,
the fraction the honest network extended the *attacker's* side (it excludes the
attacker's own reorg wins — see Caveats). A single bridge cannot propagate a
tie block, so γ ≈ 0 there by construction.

## Phase 1 — single bridge (γ ≈ 0 regime), `native_preemption: true`

| run-dir | config | α | strategy | attacker share | realized γ (ties) | theory@γ | attacker orphan | verdict |
|---|---|---|---|---|---|---|---|---|
| `20260912_131855_selfish_micro_t1` | `selfish_micro.yaml` | 0.40 | eyal_sirer | 0.471 | 0.071 (14) | 0.490 | 0.138 | PASS |
| `20260912_140443_exp_sw0300` | `selfish_sweep/alpha_0300.yaml` | 0.30 | eyal_sirer | 0.288 | 0.111 (27) | 0.285 | 0.321 | PASS |
| `20260912_143543_exp_sw0400` | `selfish_sweep/alpha_0400.yaml` | 0.40 | eyal_sirer | 0.421 | 0.043 (23) | 0.487 | 0.212 | PASS |
| `20260912_150712_exp_sw0450` | `selfish_sweep/alpha_0450.yaml` | 0.45 | eyal_sirer | 0.548 | 0.056 (18) | 0.655 | 0.204 | FAIL (undershoot) |
| `20260912_154839_exp_honest` | `selfish_micro_honest.yaml` | 0.40 | honest | 0.394 | 0.000 (2) | 0.484 | 0.026 | PASS |
| `20260912_161851_exp_long` | `selfish_long.yaml` (24 h) | 0.40 | eyal_sirer | 0.409 | 0.000 (72) | 0.484 | 0.195 | PASS |

(γ=0 theory for reference: α=0.30 → 0.273, α=0.40 → 0.484, α=0.45 → 0.652.)

### What these show

1. **Neutral plumbing (gate a).** The honest-strategy attacker earns 0.394 ≈ its
   0.40 hashrate, with near-zero orphans (0.026) and γ=0. The two-daemon
   apparatus adds no advantage on its own — the selfish gains below are real,
   not an artifact.
2. **Profitability threshold ≈ 1/3.** At α=0.30 the attacker earns **less** than
   its hashrate (0.288 < 0.30): selfish mining is unprofitable below threshold,
   matching the γ=0 curve. At α=0.40 and 0.45 it earns more (0.41–0.55 > α):
   profitable above threshold.
3. **Selfish beats honest at equal hashrate.** At α=0.40: eyal_sirer 0.41–0.47
   vs honest 0.394. Withholding pays.
4. **γ ≈ 0 with one bridge, confirmed.** Realized γ is 0.00–0.11 across the
   single-bridge runs (exactly 0 on the two longest/cleanest). The attacker wins
   essentially no honest-resolved ties, as expected when a tie block cannot
   propagate.
5. **The idealized curve is an upper bound; realized share undershoots it,
   increasingly with α.** Gaps to the γ=0 curve: +0.015, −0.063, −0.104 at
   α=0.30/0.40/0.45; the 24 h run (the tightest point) pins α=0.40 at 0.409,
   ~0.07 under 0.484. Eyal–Sirer assumes instantaneous, lossless propagation and
   reaction; the sim has a finite reaction delay (200 ms here) and real
   propagation, so the attacker occasionally fails to cash a long withheld lead
   before honest extends — and that costs more at high α (longer leads). This is
   why α=0.45 fails the ±0.10 verdict band: the band is measured against the
   frictionless value, which a real network does not reach. It is a faithful
   cost, not a defect. (Phase 2 lowers the reaction delay to 50 ms to probe how
   much of the gap is reaction-bound.)
6. **Run-to-run variance ≈ 0.05.** The two byte-identical α=0.40 configs gave
   0.471 (micro) and 0.421 (sw0400); `native_preemption: true` trades bit-level
   determinism for wall-clock speed, so identical runs vary by ~1σ (~0.037 at
   ~172 blocks). Use the 24 h run (0.409) for the tightest α=0.40 estimate, and
   a `native_preemption: false` A/A pair for a strict determinism check.

## Phase 2 — multi-bridge γ-lifting + stubborn variants, `fixed-difficulty: 1200`

Configs in `test_configs/selfish_phase2/` on a larger honest network (3 miners +
12 relays) so γ can be lifted by fan-out (more publisher bridges), and with
difficulty pinned so ≥2-block contests are decided by propagation, not
timestamps (see Caveats / review P1). α = 0.40 throughout.

**γ vs fan-out** (eyal_sirer; does realized γ rise with the number of publisher
bridges?):

| run-dir | config | bridges | attacker share | realized γ (ties) | theory@γ | verdict |
|---|---|---|---|---|---|---|
| `20260912_191118_p2_fanout_1` | `fanout_1.yaml` | 1 | 0.475 | 0.167 (12) | 0.498 | PASS |
| `20260912_211111_p2_fanout_3` | `fanout_3.yaml` | 3 | 0.425 | 0.083 (12) | 0.491 | PASS |
| `20260912_201141_p2_fanout_6` | `fanout_6.yaml` | 6 | 0.545 | 0.000 (8) | 0.484 | PASS |

### What the fan-out sweep shows

**Fan-out does not lift γ.** Across 1, 3, and 6 publisher bridges the realized γ
was 0.167, 0.083, 0.000 — but those are 2, 1, and 0 tie wins out of ~10
honest-resolved ties each: small-count noise around γ = 0, not a trend. Attacker
share (0.475, 0.425, 0.545; mean ≈ 0.48) sits on the Eyal–Sirer **γ = 0** curve
(0.484) within the ~0.05 preemption noise at every fan-out level. Adding bridges
bought the attacker no tie-breaking advantage.

**Why — verified by forensic on the 6-bridge run.** In
`20260912_201141_p2_fanout_6` the attacker produced 74 blocks, of which 8 were
orphaned (never reached the 121-block canonical chain); **none of those 8
orphaned blocks appears in any honest miner's daemon log**
(`daemon_logs/monero-honest-00{1,2,3}/bitmonero.log`, grepped exhaustively). The
attacker's losing tie-blocks never reached the honest network at all. The cause
is structural, not a tuning problem: the attacker *learns* of a new honest block
through its bridges (it polls them with `get_info`/`get_block`) and *publishes*
its matching block through the same bridges. So its equal-height block is always
submitted **after** the bridge has already received the honest block over P2P,
adopted it as the main tip, and relayed it onward. Stock monerod re-floods only
blocks that extend the main chain; an equal-height block arriving second is an
**alt-block and is not relayed**. Every bridge independently hits this same "too
late → alt-block → not relayed" outcome, so more bridges only make more
un-relayed copies. Lowering the reaction delay cannot fix it: the attacker's
release is *causally downstream* of the bridge adopting the honest block, so the
tie-block is second by construction — at 50 ms or at 0 ms.

**This agrees with the model; it is not a contradiction.** The γ = 0 Eyal–Sirer
curve already prices in the attacker's non-tie gains — profitable withholding:
releasing a strictly-longer private chain, which *does* extend the main chain,
*is* relayed, and *does* trigger an honest reorg. The sweep confirms the attacker
sits exactly on that γ = 0 curve and earns essentially nothing from ties, as
expected when tie-blocks do not propagate.

**Implication for the "γ vs network position" experiment.** Lifting γ requires
the attacker's block to arrive *first* at some honest miners — a network-position
advantage (publishers near part of the honest set; the honest finder far from
it). monerosim uses a single global, deterministic scheduler with **no
per-agent topology placement**, so that regime cannot be created by any number of
bridges: fan-out is not a substitute for position. The honest conclusion is a
**fidelity limitation** — the current simulator reproduces the α-threshold
(phase 1) faithfully but *cannot* study γ as a function of network position,
because it cannot place the attacker's publishers advantageously relative to
honest miners. A real γ experiment would need per-agent topology/latency control
(a Shadow topology with placed hosts) or a *preemptive-release* strategy that
publishes the matching block on a timer rather than reactively. This is the main
scientific finding of phase 2. (Phase 3 below adds exactly that per-agent
placement and finds it *still* insufficient — the reactive attacker's block is
second everywhere — which sharpens what a γ>0 setup actually requires.)

*Reproduce the forensic:* the attacker's found-block hashes are in
`daemon_logs/monero-attacker-miner/bitmonero.log`; the canonical hashes in
`transaction_registry/canonical_chain_bridge-*.json` (all six identical, 121
blocks); grep any orphaned attacker hash against
`daemon_logs/monero-honest-*/bitmonero.log` — it will not appear.

**Stubborn variants vs eyal_sirer** (all at fan-out 6, fixed difficulty; this is
a *relative* comparison — our mechanism's renderings of the stubborn families do
not have a closed-form theory curve here, see review P2):

| run-dir | config | strategy | attacker share | realized γ | vs fanout_6 eyal_sirer |
|---|---|---|---|---|---|
| `20260912_201141_p2_fanout_6` | `fanout_6.yaml` | eyal_sirer | 0.545 | 0.000 | — (baseline) |
| `20260912_221005_p2_stub_trail` | `stub_trail.yaml` | trail_stubborn(2) | 0.658 | 0.000 | +0.113 (0.545→0.658) ⚠ |
| `20260912_230834_p2_stub_equalfork` | `stub_equalfork.yaml` | equal_fork_stubborn | 0.512 | 0.000 | −0.033 (0.545→0.512) |
| `20260913_024558_p2_stub_lead_fixed` | `stub_lead.yaml` | lead_stubborn | 0.297 | 0.000 | −0.248 (0.545→0.297) † |

### What the stubborn variants show

All three ran at fan-out 6 with `fixed-difficulty: 1200`, against the same
eyal_sirer baseline (0.545). The comparison is *relative* (no closed-form
stubborn theory here — review P2), and the results split exactly along the γ≈0
finding above:

- **trail_stubborn(2): 0.658 (+0.113) — a real gain, off a fragmented honest
  network.** trail-stubborn refuses to concede while behind by ≤2, so it
  accumulates longer private leads and cashes them as strictly-longer reorgs. A
  forensic on the run confirmed the gain is *consensus-legitimate*: the attacker
  found 46% of blocks (≈ its hashrate — not a mining bug) and all 15 of its
  canonical reorgs had strictly-greater cumulative difficulty (no equal-length
  shortcut — fixed-difficulty is working). But the *magnitude* rides on honest
  fragmentation (see Caveats): the reorgs ran up to **19 blocks deep**, which is
  only possible because the honest majority was not building one coherent chain.
  Read +0.113 as "trail-stubborn exploits a fragmented honest network more than
  plain selfish mining does," not as a clean α=0.4 revenue.

- **equal_fork_stubborn: 0.512 (−0.033, ≈ baseline) — no effect, as expected.**
  Equal-fork stubbornness is a *tie-winning* refinement (hold one extra round out
  of a tie). Ties do not propagate here (γ≈0, shown above), so it has nothing to
  exploit and degrades to eyal_sirer within noise.

- **lead_stubborn: 0.000 → 0.297 after a bug fix — and still underperforms at
  γ≈0, as a γ>0 strategy should.** The first run (`…_p2_stub_lead`) scored
  **0.000** (attacker orphan 1.000, 64 losing "ties"). Cause: lead-stubborn's
  override (`a−h==1`) revealed only to a tie and kept the top hidden, but it
  *replaced* eyal_sirer's winning commit (`a−h==1 → fork = priv_height`, reveal
  the whole strictly-longer branch) **without any other path that advances
  `fork`** — so its only non-conceding move never committed, and it could never
  place a block on the canonical chain (a genuine strategy-completeness bug, not
  an analysis artifact: the attacker mined normally, every block orphaned).
  **Fixed 2026-09-13** (commit `0a3151c6`, `agents/selfish_strategy.py`): keep
  the distinctive a−h==1 hold-the-top (the γ-bet tie), and add the missing
  **cash path** — when ≥2 ahead of an *active* honest chain (`h>0`, `a−h≥2`),
  reveal the whole branch and commit the strictly-longer overtake; a regression
  test now asserts every withholding strategy has a winning commit path. The
  re-run (`20260913_024558_p2_stub_lead_fixed`) scores **0.297**: the attacker
  now wins blocks, but earns *less than eyal_sirer (0.545) and even less than its
  own 0.40 hashrate* (attacker orphan 0.380 — it burns its own blocks on losing
  ties; network orphan 0.213, lower than the other runs since it reorgs honest
  less). That is the correct γ≈0 outcome: lead-stubborn trades guaranteed
  overtake wins for a γ-bet that never pays when ties don't propagate, so at γ≈0
  it actively *hurts* the attacker. It is a γ>0 strategy, faithfully useless at
  γ=0. († the −0.248 in the table is post-fix.)

**Net:** at γ≈0, only the *reorg-persistence* family (trail-stubborn) helps, and
only by exploiting honest fragmentation; the *tie-exploiting* families gain
nothing — equal-fork ties eyal_sirer, and lead-stubborn (once its
winning-commit-path bug was fixed) realizes *below* both eyal_sirer and its own
hashrate because its γ-bet never pays when ties don't propagate. Tie-exploiting
stubbornness needs γ>0, which this apparatus structurally cannot provide.

## Phase 3 — γ vs network position (per-agent placement)

Phase 2 concluded that lifting γ would need per-agent topology placement, which
monerosim lacked. That knob now exists — `topology_node: <gml node id>` pins an
agent to a chosen GML node (design:
`docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md`). Phase
3 uses it to give γ its best shot and measures whether position lifts it.

| run-dir | config | placement | attacker share | realized γ (ties) | result |
|---|---|---|---|---|---|
| `20260913_051102_p3_gamma_lift` | `selfish_phase3/gamma_lift.yaml` | honest miners spread to 3 distant regions; attacker detector central; 5 publishers spread near honest regions; reaction 10 ms | 0.411 | 0.000 (12) | γ **not** lifted |

### What it shows

**Position does not lift γ in this apparatus.** Despite the deliberate contrast —
honest miners pinned far apart (GML nodes 100/500/900), the attacker's detector
central (500), publisher bridges spread near each honest region
(100/300/500/900/1100), and the reaction delay dropped from 50 ms to 10 ms —
realized γ was **0.000** (0 of 12 honest-resolved ties won). Attacker share 0.411
sits on the γ=0 Eyal–Sirer bound (0.484) and ≈ α within preemption noise: the
attacker profits marginally from withholding but earns nothing from ties, exactly
as in phase 2.

**Why — the barrier is reactive timing, not position.** The attacker must *hear*
the honest block (through its detector bridge), then react, then publish through
its bridges. So its competing block starts the propagation race a fixed
detection+reaction penalty behind, and then must cover ~the same network distance
the honest block has already travelled — *everywhere*. Worse, its bridges relay
the honest block first: a bridge that has already received the honest block treats
the attacker's second-arriving equal-height block as an alt-block, which stock
monerod does **not** re-flood (the same mechanism the phase-2 forensic found).
Moving the bridges changes latencies but not this ordering — the attacker's
tie-block is second at every node it can reach. (Network orphan fell to 0.245,
below phase-2's co-located 0.31–0.38, confirming the honest network really was
placed more spread out; the pins worked, they just don't help γ.)

**What a γ>0 setup would actually require.** Placement is necessary but not
sufficient. Lifting γ needs the attacker's block to arrive *first* at some honest
miners, which requires one (ideally both) of:

1. **One-hop peer dominance + near-zero reaction** — the attacker's publishers
   directly peered with a chosen honest subset that is many hops from the finder,
   so the attacker's one-hop delivery beats the honest multi-hop propagation
   despite reacting late. This needs a *peer-pinning* knob (force specific
   bridge↔honest peer links; `topology_node` sets position, not the peer graph,
   which `peer_mode: Dynamic` discovers) plus the smallest possible reaction.
2. **A daemon-level relay change** so the attacker's second-arriving equal-height
   block is still adopted/relayed — i.e. the deliberately **rejected**
   `--withholding`-style monerod patch. Out of scope by the project's no-daemon-
   patch rule.

So the honest conclusion of the γ line of work: **the reactive,
publish-through-stock-bridges attacker cannot realize γ>0 by network position
alone; γ in this apparatus is structurally ≈0.** The `topology_node` feature is a
correct, general capability (useful for eclipse/partition/latency experiments) —
it simply is not the missing piece for selfish-mining γ. A peer-pinning knob is
the next lever if the γ question is pursued further.

## Phase 4 — γ vs relay (the sim-only `--sim-relay-alt-blocks` flag)

Phase 3 named two levers that could plausibly lift γ: (1) one-hop peer dominance
with near-zero reaction, and (2) a daemon-level relay change so the attacker's
second-arriving equal-height block is still adopted/relayed. Lever 2 was built as
`patches/monero-sim-selfish-relay.patch` — a sim-only, default-off flag that makes
a daemon relay a **locally-submitted** block even when it is accepted only as an
alternative (equal-height) block. It never affects P2P-received blocks. Phase 4 is
`gamma_lift.yaml` with that flag on the five bridges and nothing else changed, so
relay is the only variable versus phase 3.

| run-dir | config | change vs phase 3 | attacker share | realized γ (ties) | result |
|---|---|---|---|---|---|
| `20260918_175657_p4_gamma_relay` | `selfish_phase4/gamma_relay.yaml` | `sim-relay-alt-blocks: true` on all 5 bridges | 0.528 | 0.000 (10) | γ **not** lifted |

### What it shows

**Relay does not lift γ either.** Realized γ was **0.000** — 0 of 10
honest-resolved ties won — identical to phase 3's 0.000 of 12, despite the
attacker's tie-block now being actively relayed into the honest network.

**This is a real measurement, not an untested code path.** That distinction
matters for a negative result, so it was verified in the daemon logs rather than
assumed. All five bridges logged the patch's startup banner (and only the
bridges did). For every one of the **10/10** tie heights, all **3/3** honest
nodes logged `Received NOTIFY_NEW_FLUFFY_BLOCK <attacker hash>` from a bridge IP
and then `----- BLOCK ADDED AS ALTERNATIVE ON HEIGHT <n>` — the attacker's block
arrived, verified, and was accepted as a valid alternative. No `Invalid`,
`rejected`, `switched` or reorg line appears near any of those hashes. The run
uses `log-level: monitor`, which maps to `net.p2p.msg:INFO` + `blockchain:INFO`
— exactly the categories that emit those lines — so this is positive evidence,
not an argument from silence.

**Why it fails: relay is not adoption.** The patch changes what the *sender*
does (relay a locally-submitted alt-block). The tie-break lives in the
*receiver*: monerod keeps the block it saw first at a given height and files any
later equal-height block on an alternative chain without switching. The honest
nodes in this run did exactly that — accepted the attacker's block, cached it as
an alt, and went on extending their own. Removing the relay barrier simply
delivers the attacker's block to nodes that have already made up their minds.

**This refines phase 3's conclusion rather than confirming it.** Phase 3 listed
the relay change as one of two possibly-sufficient levers; phase 4 shows it is
**not sufficient, and not even partially effective** — γ did not move by a single
tie. The binding constraint is arrival *order*, which only lever 1 addresses. A
patch that actually lifted γ would have to change the receiving node's tie-break
rule, i.e. make honest nodes prefer a later-arriving equal-height block. That is
consensus behaviour, not relay plumbing, and a network running it would no longer
be modelling Monero — which is a good reason not to build it.

**Side observation (unverified, small sample).** Attacker share rose from phase
3's 0.411 to 0.528 and network orphan rate from 0.245 to 0.304, while γ stayed
flat at 0.000. The plausible mechanism is fragmentation rather than tie-winning:
honest nodes now hold a pre-validated copy of the attacker's branch, so a later
reorg onto it is cheaper — the same family of effect as phase 2's trail-stubborn
result. This is **a hypothesis, not a finding**: both runs measure ~142 blocks
(10 and 12 ties), where the standard error on a share estimate is roughly ±0.04
before accounting for reorg autocorrelation, so a 0.411→0.528 gap is suggestive
at best. Establishing it would need repeated seeds.

The phase-3 run **is** available for a direct comparison:
`20260913_051102_p3_gamma_lift` is preserved on the backup volume
(`/mnt/remote_spinny/monerosim_backups/20260915_backup/`), so the reorg-cost
mechanism above can be tested at log level rather than left as a hypothesis.
(An earlier revision of this section stated the phase-3 directory was gone; that
was wrong — only `archived_runs/` and `~/basement_monerosim` had been checked.)

## Verify it yourself

1. Pick any phase-1 row, re-run its analysis:
   `venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run-dir>` —
   you should get the same attacker share and realized γ (the inputs are the
   archived logs + `canonical_chain*.json`, which do not change).
2. Check the theory by hand: `python3 -c "a=0.4;g=0.0; print((a*(1-a)**2*(4*a+g*(1-2*a))-a**3)/(1-a*(1+(2-a)*a)))"` → 0.484 for α=0.4, γ=0.
3. Re-run a sim from scratch: `./run_sim.sh --config test_configs/selfish_micro.yaml --name my_check` then analyse it. With `native_preemption: true` expect the share within ~0.05 of 0.42 (not bit-identical — see finding 6).
4. Read the logs: the attacker's agent log (`archived_runs/<run>/shadow.data/hosts/attacker-miner/*`) shows `Bridge connected`, native mining start, and honest-reorg re-forwards; the bridge log shows `Canonical chain recorded: N blocks`.

## Caveats (read before trusting a number)

- **The idealized Eyal–Sirer curve is an upper bound**, not a target; a real
  network with finite reaction and propagation realizes less, most at high α
  (finding 5). Treat a verdict FAIL at high α as "below the frictionless bound,"
  not "broken."
- **`native_preemption: true` is non-deterministic** (finding 6). For a strict
  A/A determinism check, use a `native_preemption: false` copy.
- **The realized-γ estimator was corrected on 2026-09-12** (review C1): the first
  version counted every coexistence height and conflated reorg wins with
  tie-breaks, reporting γ ≈ 0.70 on a γ ≈ 0 run. The numbers here use the
  corrected estimator (honest-resolved forks only); re-running the analysis on
  any archive gives the corrected value.
- **Phase-2 uses `fixed-difficulty: 1200`** (review P1): below ~600 blocks
  monerod's difficulty has no lag, so equal-length contests would be decided by
  the older fork (always the attacker) rather than by γ. Pinning difficulty (the
  120 s / 10 h·s⁻¹ equilibrium) makes contests propagation-decided. Phase-1 runs
  used the native DAA and are unaffected (their contests are 1-block ties,
  genuinely tied and propagation-decided).
- **Stubborn variants are compared relative to eyal_sirer**, not to a theory
  curve (review P2): the apparatus's renderings of trail/equal-fork/lead stubborn
  are faithful to the spec (§4.2 of the phase-2 design) but are not the exact
  Nayak et al. Markov chains, so only a same-config eyal_sirer comparison is
  meaningful. (lead-stubborn had an implementation bug — no winning commit path,
  realizing 0.000 — fixed 2026-09-13 (commit `0a3151c6`); the re-run realizes
  0.297, below eyal_sirer and below α, as a γ>0 strategy should at γ≈0. See the
  stubborn-variants section.)
- **Phase-2's honest network is fragmented** (network orphan rate 0.31–0.38
  across every phase-2 run, vs ~0.27 in phase-1). With 3 honest miners on a small
  network at fixed difficulty and native mining, honest blocks frequently fork
  against each other, so the effective honest chain grows slower than its 60%
  hashrate implies. This **inflates absolute attacker shares** (the attacker's
  unified 40% fork can win deep reorgs it could not against a coherent majority —
  trail-stubborn's depth-19 reorgs are the clearest case). Same-config
  comparisons (stubborn vs eyal_sirer, fan-out vs fan-out) remain sound because
  both sides see the same fragmentation, but do not read the absolute phase-2
  shares as clean α=0.4 selfish-mining revenue. A cleaner run would tighten
  honest-honest convergence (more relays / faster propagation / lower block rate)
  or use a single honest miner.
- **The offline attacker miner is still auto-listed as a network seed**; honest
  nodes log failed connections to it but bootstrap via the online honest miners
  (all configs have ≥2). Excluding offline nodes from seeds is a future
  orchestrator improvement.
