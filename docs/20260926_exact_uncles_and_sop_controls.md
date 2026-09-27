# MRL #144 exact uncles on the h10 base, and the SoP upgrade-transition controls (2026-09-26/27)

Campaign 3 (owner decisions 2026-09-26 17:40Z; `docs/20260926_dev_branch_handoff.md`
progress log, evening entry). Companion to `docs/20260926_sop_h10_rerun.md`.
Everything ran on the 64-core box with the `monerod-sim` builds named per
section; every run's `binary_provenance.txt` records the patch shas.

## 1. Stage 1a — `pop_exact_h10{,_rep}`: exact uncles at micro scale (18:15–19:56Z)

Cells: ES, lead-2, honest × exact (`sim-publish-or-perish`,
`sim-pop-uncles-header`, `sim-pop-det-tie` on the two honest miners), base
`selfish_micro_sop.yaml` (h10 graft, α = 0.40), seeds 12345 / 54321. Stock
pairs: `pop_sop2_h10{,_rep}` `*_stock` rows (same base, same seeds). Daemon:
the 17:50Z build (verifier sibling fix F5c in; template refresh F5d NOT in).

| cell | draw 1 | draw 2 | mean | stock pair (same seeds) | blocks/6 h | forks seen | health |
|---|---|---|---|---|---|---|---|
| ES, exact | 0.169 | 0.199 | 0.184 | 0.377 / 0.441 | 130 / 156 | 2743 / 2530 | ok |
| lead-2, exact | 0.284 | 0.292 | 0.288 | 0.305 / 0.469 | 148 / 144 | 1519 / 1990 | ok |
| honest control, exact | 0.378 | 0.389 | 0.383 | 0.381 / 0.410 | 222 / 193 | 0 / 0 | ok (no forks, expected) |

Bridge and honest-node references agree in every row (PoP nodes and the
stock bridge converge). Uncle diagnostics on both honest miners, all four
attack cells: **0 uncle headers embedded, 0 counted, 0 rejected**, against
83–93 fork decisions per honest miner, 50–66 of them with an in-time
alternative chain and 18–31 exact weight ties (4–14 of the form
`TIE 1/1 vs 1/1 -> KEEP (det tie)`: the attacker's single tie block WAS in
time and would have been embeddable).

**So these rows measure pop-core + det-tie on the h10 base, not the exact
variant** — for a reason different from the 2026-09-24/25 defects. Stock
monerod rebuilds the miner's block template only when the chain top changes.
An in-time sibling that arrives after the miner's own block (the normal tie:
the honest miner finds height N, the attacker's withheld N follows ~200 ms +
one hop later) is accepted as an alternative block, but the template for N+1
was already built and is not refreshed, so `sim_pop_find_uncle_header` never
runs while the sibling is embeddable. The race-heavy smoke's embeddings all
sit one line after `REORGANIZE SUCCESS`: the template is rebuilt on a reorg,
and the displaced main block is then the in-time sibling. Under ES at γ ≈ 0
the reorg that displaces an honest block is a 2-over-1 release, which leaves
no sibling at the new parent's height, so the bonus could not fire there
either. The per-second template refresh the sim miner already has is
SoP-only (it advances the share slot). Pre-existing since rung 3.

As det-tie readings on the real-DAA base these rows are useful and are kept
under that label: ES 0.184 vs stock 0.409 (the genesis-base det-tie set was
n = 5, mean 0.22); lead-2 0.288 vs stock 0.387; honest control ≈ α with no
orphaning (the 2026-09-23 honest_exact dip to 0.322 did not recur).

### Fix F5d (2026-09-26 20:05Z) — refresh the template on a sibling at the tip

`core::handle_incoming_block`: when either uncle flag is on and an incoming
block is accepted as an alternative whose height equals the current tip's,
call `update_miner_block_template()` (logged
`SIM-PoP: sibling alternative block at the tip height N -- refreshing the
block template for the uncle header`). MRL #144 rewards the miner that
embeds the uncle; a miner that wants the reward refreshes. Smoke:
two race-heavy exact smokes (fixed difficulty 40, 60 sim-min) on
the refreshed build, `20260926_200552_pop_exact_fast_fix3` and (with
template-side diagnostics) `20260926_201720_pop_exact_fast_fix3b`: health gate
green both times (reorgs balanced on every node, 0 exceptions, 19–22 uncles
counted per honest miner), **but every embedding still followed a reorg
(12/12, 14/14, 11/11, 8/8)** and the refresh fired 1–4 times per hour against
208 alternative blocks on honest-001, 77 of them at the tip height.

### Why: at γ ≈ 0 there is nothing to embed (structural, not a defect)

The 77 alternative blocks at the tip height did not arrive alone. The
attacker's tie block goes to the UNFLAGGED bridge, which stores it as an
alternative and — stock behaviour — relays nothing; that is what makes the
topology γ ≈ 0. Honest nodes learn of the attacker's block N only when the
attacker's N+1 arrives, whose parent they lack, so they fetch N and N+1
through the sync path (`handle_incoming_blocks`, template update deferred)
and reorganize at once. The `TIE 1/1 vs 1/1` decisions in stage 1a are that
first block being stored a moment before its child displaces the honest
block. By the time any template is rebuilt, the sibling of the new parent is
the DISPLACED honest block — embedded only after 1-for-1 det-tie switches,
which is exactly where the counted uncles of every smoke come from. An
honest miner in this topology never holds an in-time attacker sibling with
its own block still on top, so MRL #144's uncle term has no attacker block
to act on. **Exact uncles equal det-tie at γ ≈ 0 by construction**; the
uncle term can only bite where ties propagate — natural honest-vs-honest
ties (several miners) or an attacker with γ > 0 (a bridge that relays
alternatives, `sim-relay-alt-blocks`). The template refresh (F5d) is kept:
it is what lets a template pick up a natural tie (the 1–4 firings), and it is
the correct miner behaviour under the rule.

Consequence for the plan: the micro exact re-run (`pop_exact2_h10`, written
and then withdrawn the same evening) would have reproduced stage 1a and was
dropped; the mid-scale matrices, where six honest miners race each other,
went ahead. A γ > 0 exact cell (bridge relaying alternatives) is a new
experiment for the owner to decide on.

## 2. Stage 1b — `sop2_h10_ctl{,_rep}`: SoP upgrade-transition controls

Question (`docs/20260926_sop_h10_rerun.md` reading 5): the SoP honest
control's second draw lost 17 same-height races, all by the honest-strategy
attacker, whose daemon was stock (no shares) AND offline behind the bridge
(blocks pushed by RPC, ~200 ms + one hop late). Two controls, honest
strategy, α = 0.40, sop2 countermeasure exactly as in `pop_sop2_h10`:
`upgraded` = attacker daemon P2P-connected and SoP-flagged (w = 16);
`connected` = P2P-connected, unflagged.

Runs 18:15–20:19Z on the 17:50Z daemon (F5c; SoP code paths unchanged by
F5c/F5d). Seeds 12345 / 54321; all four rows health ok.

| control | draw 1 | draw 2 | attacker found / canonical | attacker orphan | same-height ties | forks seen (all nodes) |
|---|---|---|---|---|---|---|
| `upgraded` (connected + SoP-flagged) | 0.363 | 0.368 | 71/193, 81/220 | 0.014, 0.000 | 2, 1 | 26, 12 |
| `connected` (connected, unflagged) | 0.394 | 0.418 | 69/175, 76/182 | 0.000, 0.000 | 0, 0 | 0, 143 |
| honest_sop2 (offline + bridge, unflagged; `pop_sop2_h10`) | 0.440 | 0.326 | — | 0.01, 0.22 | 1, 17 | 0, 0 |
| honest_stock (`pop_sop2_h10`) | 0.381 | 0.410 | — | 0.00, 0.00 | 0, 0 | 0, 0 |

Reading:

1. **The race cost is a property of the offline-bridge control, not of not
   upgrading.** A P2P-connected miner that gossips no shares (`connected`)
   entered no same-height race in two draws and orphaned nothing; its share
   {0.394, 0.418} brackets α. The 17 lost ties of `honest_sop2` draw 2 arose
   because the offline daemon learns of honest blocks only through the
   agent's RPC forwarding and its blocks reach the network through the
   bridge — both a hop and a reaction delay late — so it kept producing
   competitors to blocks the network already had, which one-unit blocks
   lose. At 120 s blocks and 10 h/s a directly connected miner does not race
   often enough for the one-unit tie weight to cost it anything measurable.
   The upgrade-transition cost the rule implies is real in principle but is
   not observable at this scale; sizing it needs a topology with frequent
   natural ties (mid or mainnet-replica scale).
2. **The upgraded attacker's shares circulate** (1,127 share events in its
   daemon log, `embedding N workshares` at template time) and its blocks are
   canonical: orphan 0.014 / 0.000. Its share {0.363, 0.368} sits below α in
   both draws, but so does its block-finding rate (71 of 193 and 81 of 220
   found, against 77 and 88 expected): a −1.4 σ luck draw, not a rule cost.
3. **SoP forks among honest nodes exist.** `connected` draw 2 saw 143
   alternative blocks across nodes with the network orphan rate at 1.6 %:
   one event at height 491 where honest-001 switched to a share-heavy block
   (weight 402) while four one-unit blocks accumulated on the other branch
   (`alt 268/4 vs main 402/1 -> KEEP`) until rule 1 (k = 3) resolved it. The
   subjectivity of share weights lets a node hold a lighter-by-length branch
   for several blocks; the cost here was ~8 minutes of one miner's work.
   Worth a dedicated count at scale.


## 3. Stage 2 — `pop_exact_mid{,_rep}`

Launched 20:31Z on the installed F5c+F5d daemon (pop patch sha `9492d7cb…`,
provenance matches the tree; the SoP smokes were not re-run for F5d, whose
hook is guarded by the uncle flags and cannot run in a SoP cell). Cells: ES,
lead-2, honest × {exact, none} on the unchanged genesis mid base
(`selfish_scaled_mid.yaml`, 6 miners + 16 relays, α = 0.40), seeds 12345 /
54321, six cells at once (~2 waves of ~7 h). Exact compares directly with the
retained det-tie mid rows ({0.170, 0.285} vs stock {0.387, 0.463}), and this
is the first setting where natural ties give the uncle term something to
embed — read the template-side `embedding uncle header` and
`no uncle embedded` diagnostics per honest miner before the shares.

Finished 2026-09-27T01:46Z. All 12 rows health ok: reorganizations started ==
succeeded on every node, zero `add_new_block` exceptions, forks seen in every
cell (41–6,872), attacker found 48–117 blocks.

| cell | draw 1 | draw 2 | mean | stock draws | stock mean | attacker orphan (exact / stock) | uncle headers embedded (6 honest miners) |
|---|---|---|---|---|---|---|---|
| ES | 0.253 | 0.303 | **0.278** | 0.376, 0.518 | 0.447 | 0.55, 0.48 / 0.27, 0.14 | 22, 13 |
| lead-2 | 0.241 | 0.251 | **0.246** | 0.455, 0.351 | 0.403 | 0.50, 0.48 / 0.25, 0.24 | 13, 12 |
| honest control | 0.416 | 0.367 | 0.391 | 0.405, 0.470 | 0.437 | 0.00, 0.00 / 0.01, 0.01 | 3, 11 |

Bridge and honest-node references agree in every row. The stock ES draw 1
(`es_none`, seed 12345) ran on a slow genesis difficulty ramp and has only
93 canonical blocks (others 145–195); it is the noisiest row.

Reading:

1. **Exact PoP cuts both attackers at mid scale, n = 2, non-overlapping.**
   ES 0.278 vs stock 0.447; lead-2 0.246 vs 0.403. The attacker's orphan
   rate roughly doubles (0.14–0.27 → 0.48–0.55) and the network orphan rate
   is unchanged (~0.24–0.35 in every attack cell: the attack's forks happen
   either way, PoP changes who loses them). Lead-2 is hit as hard as ES here,
   unlike the micro det-tie readings (lead-2 0.288 vs stock 0.387).
2. **The uncle term is live at mid scale but rare.** 12–22 headers embedded
   per attack cell over 6 h across six honest miners (against 40–58
   same-height ties), 28–65 fork decisions whose weight carried an uncle
   bonus, and the F5d refresh fired 25–49 times. Every template that skipped
   an available alternative block did so because it was not a sibling of the
   template's parent (37–100 per cell, 0 skipped as late): attacker blocks
   appear to honest miners as displaced branches, not fresh siblings (§1).
3. **The uncles add nothing measurable over det-tie at mid scale.** The
   same-daemon, same-seed det-tie pair (`pop_dettie_mid{,_rep}`, uncle flag
   removed and nothing else, finished 2026-09-27T04:38Z, all health ok):

   | attacker | det-tie only | exact | stock |
   |---|---|---|---|
   | ES | 0.159, 0.162 (orphan 0.72, 0.75) | 0.253, 0.303 (0.55, 0.48) | 0.376, 0.518 |
   | lead-2 | 0.293, 0.389 (orphan 0.34, 0.29) | 0.241, 0.251 (0.50, 0.48) | 0.455, 0.351 |

   The two variants differ in opposite directions by strategy and pool to
   the same mean (det-tie 0.251, exact 0.262 over the four draws each). Both
   cut stock. `scripts/uncle_parents.py` (new) classifies every embedding by
   who mined the template's parent and the embedded sibling: **all 60 mid
   embeddings are honest-parent, honest-sibling** — the uncle term never
   touched an attacker block at mid scale, so it has no direct route to the
   attacker's share. The ES gap (det-tie lower in both draws, with the
   attacker orphan rate 0.72–0.75 vs 0.48–0.55) is consistent across draws
   but has no identified mechanism: exact cells show somewhat more tie
   switches (18–22 vs 12–13 on honest-001) and reorgs (26–31 vs 18–19), and
   only 4–9 fork decisions per cell carried an uncle bonus. Open; not
   claimed. The retained pre-fix det-tie mid rows ({0.170, 0.285}) agree
   with the new ES det-tie draws.
4. **No collateral damage to honest miners.** The honest control under
   exact is {0.416, 0.367} ≈ α with attacker orphan 0.00, against stock
   {0.405, 0.470}; network orphan 0.055–0.058 vs 0.067.

## 4. Campaign 4 — exact with a RELAYING attacker bridge (`pop_exact_relay{,_rep}`)

Owner request 2026-09-27. **Why relay:** MRL #144's uncle term needs an honest
miner to hold the attacker's competing block beside its own tip while building
the next block. Behind a stock bridge that never happens: the bridge stores
the attacker's tie block as a side block and announces nothing, so honest
nodes meet it only together with its child and reorganize at once.
`scripts/uncle_attribution.py` (new) confirms it for every exact cell so far —
**0 attacker blocks ever counted as uncles**, micro or mid; the mid uncles
were all honest-vs-honest natural ties (1–3 unique per cell).

With `sim-relay-alt-blocks` on the bridge, the attacker's tie block is
announced like a tip block and honest miners receive it about one hop after
their own. Two effects, separated by the cells: (1) under stock rules nodes
keep the first-seen block, so relay alone should not lift γ (phase 4
measured 0/10); PoP det-tie nodes break an in-time equal-weight tie by hash,
so relay may hand the attacker about half the ties; (2) honest templates can
embed the attacker's block as an uncle and win the next race. Relay makes
ties *visible*; it is not "γ > 0" in the stock sense.

Smoke (`20260927_031322_pop_exact_relay_smoke`, race-heavy fixed difficulty
40, 60 sim-min): gate green (reorgs balanced on every node, 0 exceptions,
4,611 forks), uncle headers embedded 85 vs 19 without relay
(`20260926_201720_pop_exact_fast_fix3b`), template refreshes 149 vs 5, and the
first attacker block ever counted as an uncle (1 of 2 unique counted).
`scripts/uncle_parents.py` on the smoke: 73 of 85 embeddings put the
ATTACKER's block in as the uncle on an honest parent (11 honest-honest, 1 on
an attacker parent); without relay, 19 of 19 were honest-honest.

Cells: {ES, lead-2} × {stock, det-tie, exact}, relay on the bridge in all,
h10 micro base, seeds 12345 / 54321, 12 cells, launched 03:27Z (8 at once).
Read: stock vs det-tie = what visible ties do to PoP; det-tie vs exact = the
uncle term against the attacker; all against the no-relay rows of §1 and
`pop_sop2_h10`. Results: to follow.

## Runs (reproducibility ledger rows)

| Run directory | Commit | Config | What it shows |
|---|---|---|---|
| `20260926_181457_pop_exact_h10__es_exact` | `38c2af3d` | `pop_exact_h10` cell | es_exact: share 0.169 (honest-ref 0.169), blocks 130, forks 2743, sw 0, health ok |
| `20260926_181517_pop_exact_h10_rep__es_exact` | `38c2af3d` | `pop_exact_h10_rep` cell | es_exact: share 0.199 (honest-ref 0.199), blocks 156, forks 2530, sw 0, health ok |
| `20260926_181457_pop_exact_h10__es_r2_exact` | `38c2af3d` | `pop_exact_h10` cell | es_r2_exact: share 0.284 (honest-ref 0.284), blocks 148, forks 1519, sw 0, health ok |
| `20260926_181517_pop_exact_h10_rep__es_r2_exact` | `38c2af3d` | `pop_exact_h10_rep` cell | es_r2_exact: share 0.292 (honest-ref 0.292), blocks 144, forks 1990, sw 0, health ok |
| `20260926_181457_pop_exact_h10__honest_exact` | `38c2af3d` | `pop_exact_h10` cell | honest_exact: share 0.378 (honest-ref 0.378), blocks 222, forks 0, sw 0, health no-forks |
| `20260926_181517_pop_exact_h10_rep__honest_exact` | `38c2af3d` | `pop_exact_h10_rep` cell | honest_exact: share 0.389 (honest-ref 0.389), blocks 193, forks 0, sw 0, health no-forks |
| `20260926_181537_sop2_h10_ctl__connected_sop2` | `38c2af3d` | `sop2_h10_ctl` cell | connected_sop2: share 0.394 (honest-ref 0.394), blocks 175, forks 0, sw 0, health no-forks |
| `20260926_181557_sop2_h10_ctl_rep__connected_sop2` | `38c2af3d` | `sop2_h10_ctl_rep` cell | connected_sop2: share 0.418 (honest-ref 0.418), blocks 182, forks 143, sw 178, health ok |
| `20260926_181537_sop2_h10_ctl__upgraded_sop2` | `38c2af3d` | `sop2_h10_ctl` cell | upgraded_sop2: share 0.363 (honest-ref 0.363), blocks 193, forks 26, sw 14, health ok |
| `20260926_181557_sop2_h10_ctl_rep__upgraded_sop2` | `38c2af3d` | `sop2_h10_ctl_rep` cell | upgraded_sop2: share 0.368 (honest-ref 0.368), blocks 220, forks 12, sw 24, health ok |
| `20260926_203140_pop_exact_mid__es_exact` | `e6f6c854` | `pop_exact_mid` cell | es_exact: share 0.253 (honest-ref 0.253), blocks 190, forks 6872, sw 65, health ok |
| `20260926_203201_pop_exact_mid_rep__es_exact` | `e6f6c854` | `pop_exact_mid_rep` cell | es_exact: share 0.303 (honest-ref 0.303), blocks 195, forks 4144, sw 37, health ok |
| `20260926_203140_pop_exact_mid__es_none` | `e6f6c854` | `pop_exact_mid` cell | es_none: share 0.376 (honest-ref 0.376), blocks 93, forks 1366, sw 0, health ok |
| `20260926_203201_pop_exact_mid_rep__es_none` | `e6f6c854` | `pop_exact_mid_rep` cell | es_none: share 0.518 (honest-ref 0.518), blocks 195, forks 3507, sw 0, health ok |
| `20260926_203140_pop_exact_mid__es_r2_exact` | `e6f6c854` | `pop_exact_mid` cell | es_r2_exact: share 0.241 (honest-ref 0.241), blocks 166, forks 3449, sw 44, health ok |
| `20260926_203200_pop_exact_mid_rep__es_r2_exact` | `e6f6c854` | `pop_exact_mid_rep` cell | es_r2_exact: share 0.251 (honest-ref 0.251), blocks 175, forks 1939, sw 28, health ok |
| `20260926_230344_pop_exact_mid__es_r2_none` | `e6f6c854` | `pop_exact_mid` cell | es_r2_none: share 0.455 (honest-ref 0.455), blocks 145, forks 2424, sw 0, health ok |
| `20260926_230504_pop_exact_mid_rep__es_r2_none` | `e6f6c854` | `pop_exact_mid_rep` cell | es_r2_none: share 0.351 (honest-ref 0.351), blocks 194, forks 1758, sw 0, health ok |
| `20260926_231316_pop_exact_mid__honest_exact` | `e6f6c854` | `pop_exact_mid` cell | honest_exact: share 0.416 (honest-ref 0.416), blocks 178, forks 41, sw 0, health ok |
| `20260926_231036_pop_exact_mid_rep__honest_exact` | `e6f6c854` | `pop_exact_mid_rep` cell | honest_exact: share 0.367 (honest-ref 0.367), blocks 188, forks 106, sw 34, health ok |
| `20260926_231717_pop_exact_mid__honest_none` | `e6f6c854` | `pop_exact_mid` cell | honest_none: share 0.405 (honest-ref 0.405), blocks 195, forks 90, sw 0, health ok |
| `20260926_231908_pop_exact_mid_rep__honest_none` | `e6f6c854` | `pop_exact_mid_rep` cell | honest_none: share 0.470 (honest-ref 0.470), blocks 181, forks 46, sw 0, health ok |
| `20260927_014733_pop_dettie_mid__es_dettie` | `97c6494f` | `pop_dettie_mid` cell | es_dettie: share 0.159 (honest-ref 0.159), blocks 164, forks 6329, sw 0, health ok |
| `20260927_014753_pop_dettie_mid_rep__es_dettie` | `97c6494f` | `pop_dettie_mid_rep` cell | es_dettie: share 0.162 (honest-ref 0.162), blocks 198, forks 11776, sw 0, health ok |
| `20260927_014733_pop_dettie_mid__es_r2_dettie` | `97c6494f` | `pop_dettie_mid` cell | es_r2_dettie: share 0.293 (honest-ref 0.293), blocks 164, forks 2025, sw 0, health ok |
| `20260927_014753_pop_dettie_mid_rep__es_r2_dettie` | `97c6494f` | `pop_dettie_mid_rep` cell | es_r2_dettie: share 0.389 (honest-ref 0.389), blocks 180, forks 3637, sw 0, health ok |

The `pop_exact_relay{,_rep}` rows follow when that pair finishes.
Daemons: stage 1 ran the 17:50Z build (pop patch `dcfbaeeb…`), stage 2 the 20:25Z build (`9492d7cb…`); every run's `binary_provenance.txt` records it.
