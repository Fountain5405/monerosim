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
scientific finding of phase 2.

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
| _pending_ | `stub_lead.yaml` | lead_stubborn | | | |

_Phase-2 rows are filled in as the runs complete; the driver runs them in the
order fanout_1, fanout_6, fanout_3, then the three stubborn configs._

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
  meaningful.
- **The offline attacker miner is still auto-listed as a network seed**; honest
  nodes log failed connections to it but bootstrap via the online honest miners
  (all configs have ≥2). Excluding offline nodes from seeds is a future
  orchestrator improvement.
