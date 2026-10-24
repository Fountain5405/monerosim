# SoP scale smoke (300 relays) and the stranded attacker (2026-10-23)

Rung 1 of the scale check, `sop_scale_n300_hs_a045_d5_8h` (313 hosts, the v4
campaign cell share_sop2_hs_a045_d5, 8 simulated hours, seed 27782, build
`b5bc1a02`), run alone on the box with CPU pinning off
(`.claude/campaign9/scale_smoke.py`, queue.log 2026-10-23 02:57-07:08Z).
Run: `archived_runs/20261023_025705_sop_scale_n300_hs_a045_d5_8h__share_sop2_a045`.

## 1. The four smoke questions

| question | answer |
|---|---|
| wall-clock ratio | 1.91 sim s per wall s (8 h in 4.19 h wall); sim time advanced linearly, 0 processes failed |
| RAM | peak 83 GB used, of which ~68 GB was the box's idle baseline (another monerod runs outside the sim): ~15 GB for 313 hosts, ~50 MB/host; swap 0.3 GB, unchanged |
| freeze | none (native_preemption true as in the 12-daemon cells) |
| attacker at 300 relays | mechanically fine: embeds remote shares (92 in 8 h), oracle 0 mismatches on all 312 logging nodes, A3 untested because it never revealed |

For the 1,000-node run (1,013 hosts): RAM is no concern (~+50 GB on a 251 GB
box). Wall time is the open question: if the ratio falls with host count as
313 -> 1.9 suggests, 72 h could take 4-6 days of wall clock. **Do not launch
it with this attacker** (section 2): its result would mostly measure the
give-up rule, not the network.

## 2. The attacker was stranded for 6.5 of the 8 hours

The attacker revealed 0 times and all 104 of its blocks were orphaned
(share 0.000). Its agent loop ran every tick; the bridge daemon tracked the
honest chain (HEIGHT 995 -> 1107); the honest miners mined at their nominal
rate within noise. What happened:

- At sim 01:29 the attacker conceded (fork -> 1026) for the last time. From
  then to the end it mined a private branch of 85 blocks while the honest
  chain grew 81, at equal difficulty (1156 vs 1161).
- window_stubborn gives up only when honest leads by `give_up_depth` = 5
  **blocks** (`agents/selfish_strategy.py`). Honest at 5.5 h/s against the
  attacker's 4.5 h/s at the same difficulty drifts ahead by only ~1 block
  per ~5 found, with a random-walk spread of the same size, so a 5-block
  lead can take hours to arrive; here it never did.
- Meanwhile the attacker's branch, past the 32-object window, was behind by
  **weight** (its blocks carry 15.4 shares each vs 16.6-19.2 on honest
  blocks, and the honest tip pool counts), so the reveal test
  (`att_weight > hon_weight`) never passed either. Block parity is weight
  deficit: a dead state. The 12-daemon run of this cell shows the same
  (`weight=5344 honest_weight=5325` at a=5, h=2 is a typical reveal; the
  honest side gains ~1.2x weight per block-time).
- Honest shares are handed to the attacker only while it mines on the public
  tip (`_relay_honest_shares`), so the "remote 92" count above is the
  bootstrap plus the few minutes after each concession, not a propagation
  problem.

The same stranding is in every v4 campaign run, and it is much worse there
than under the old rule (`scripts/selfish_mining/sop_stuck_time.py`, gaps
> 2 h between attacker events):

| run (72 h) | stuck h | gaps |
|---|---|---|
| v4 a033 built d2 | 2.1 | 1 |
| v4 a040 hs d2 | 2.3 | 1 |
| v4 a045 hs d5 | 19.0 | 6 |
| v4 a045 hs d2 | 22.5 | 4 |
| v4 a045 hs d2, 2nd | 21.0 | 5 |
| v4 a045 noown | 26.9 | 7 |
| v4 a045 noown, 2nd | 17.4 | 5 |
| v3 a045 hs d5 | 5.3 | 2 |
| v3 a045 hs d2 | 4.2 | 1 |
| v3 a045 built d5 | 11.3 | 3 |
| v3 a040 hs d2 | 2.6 | 1 |
| n300 smoke (8 h) | 6.5 | 1 |

Inside one such gap (a045 hs d2, day 2 04:59 -> 13:11): private 1649 -> 1834
(185 blocks), honest 1649 -> 1829 (180), difficulty 751 -> ~700 on both; the
episode ended with "popped 187 private blocks". Under the old rule the
attacker was usually heavier past the window and revealed, so it rarely sat
in the state; the 2026-10-20 revision (honest tip shares, honest shares in
the attacker's first block only) made weight parity rarer and the sit longer.

**Consequence for `docs/20261022_sop_v4_results.md`:** the alpha-0.45
shares (0.054-0.113) were earned with the attacker idle a quarter to a third
of the run, and the model agrees the give-up rule is most of the gap: with
the race model's objects give-up (o5, tevador's rule) at alpha 0.45 it
predicts a revenue share of **0.361** against 0.073 (d5) and 0.105 (d2),
all at rule 20261020 with honest shares; the d5/d2 model values matched the
simulator (0.054-0.113). SoP still holds the attacker below alpha, but
"collapse" was the attacker's stubbornness, not only the rule.

```
venv/bin/python scripts/sop_race_model.py hunt --alphas 0.45 --rules sop \
    --give-ups d5 d2 o5 --release-depth 0 --days 2000 --seed 1 \
    --honest-shares --rule-version 20261020
```

## 3. The change: `give_up_objects`

`agents/selfish_strategy.py` / `agents/selfish_miner.py` (2026-10-23): the
attacker attribute `give_up_objects` (default -1 = the block rule, so every
existing spec is unchanged) replaces the block-depth give-up with the race
model's: give up once the honest branch holds MORE THAN that many work
objects more than the private one since the fork -- blocks, their embedded
shares, and the pending tip-pool shares on each tip (the attacker's own
included: they are its work, whatever `count_own_tip_shares` says about the
reveal-test weight). `_branch_weights` now returns the two totals as
elements 5 and 6 of its tuple; needs `weigh sop`. 10 new unit tests; the
Python suite is 328 passing.

### 3.1 Measured: `sop_v4_o5_72h` (2026-10-23 11:13-17:24Z)

Two draws of the a045 hs cell with `give_up_objects 5`, 72 h each, 12
daemons, seed 27791, build `23162f3a`, both lanes at once, 6.1 h wall each.
Both PASS the check gate (oracle 0 mismatches on 12 nodes, probes, lateness,
reveal stats and embed ok). Runs
`archived_runs/20261023_111307_sop_v4_o5_72h__share_sop2_a045_s{1,2}`.

| draw | share | blocks | reveals (deliv./rej.) | A3 deliveries (tip shares) | att. orphan | net. orphan | stuck h |
|---|---|---|---|---|---|---|---|
| s1 | 0.209 | 1886 | 174 (110/64) | 110 (34) | 0.72 | 0.41 | 0.0 |
| s2 | 0.210 | 1920 | 160 (103/57) | 103 (44) | 0.71 | 0.40 | 0.0 |
| block rule d5 (v4 campaign, n=1) | 0.054 | 1886 | 54 (31/23) | 62 | 0.96 | 0.43 | 19.0 |

The two draws agree to 0.001 (the block-rule cell's run-to-run spread at
the 0.10 level was ~±0.03). The objects give-up quadruples the attacker's
share at this cell, triples its reveal count, and removes the stranding
entirely. It stays well under the model's 0.36 and under alpha, so SoP
still holds the attacker below break-even here; but the campaign's
"collapse" at alpha 0.45 is now measured to be mostly the old give-up
rule. The gap to the model is the network: 37% of reveals were rejected by
the bridge (the model has no rejection path) and A3 tip-share delivery
reached only 34-44 of the delivered reveals.

The scale specs (n300, n1000) were re-pointed to this attacker on
2026-10-24. Open: the o5 attacker at alpha 0.33 and 0.40, the noown
variant, and the model's reconciliation at this cell.

## 4. Not established

- The honest miners' effective hashrate inside a gap looks low (4.5 h/s for
  5.5 nominal) but that is selection: a gap persists exactly while honest
  fails to pull ahead. Over 6-hour windows across 14 runs the honest side
  averages ~5.8 h/s and the attacker ~4.3, both within noise of nominal.
- Whether the objects attacker's share at 300 or 1,000 relays differs from
  the 12-daemon 0.21 (the scale specs now carry it; neither has run).
- The model's 0.36 is a fixed-rate, no-delay model; its reveal count under
  o5 (79/day) means the simulator's reveal path (A3 share delivery, bridge
  rejection) will be exercised far more than before.
