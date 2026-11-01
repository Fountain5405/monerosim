# Five-day work review (2026-10-23 to 10-28), written 2026-10-28

A second-pass audit of the campaign's work since 10-23 (entries E17-E62, runs ~60-102,
patches 6-14), done before fixing anything. Deep audit of the newest results (E58-E62:
every journal number re-checked against the committed run artifacts), the fourteenth
patch read line-by-line against tevador's MRL #160 spec, the generator and live-cell
wiring checked, and the two in-flight cells (P53, P54) verified against their
pre-registrations. Spot-checks on E59/E60 artifacts. E17-E57's archives were not
re-derived; their estimators were not re-run.

## Verified sound

- E59/E60/E61/E62 journal numbers match the committed `spy_estimators.{txt,json}` and
  `meta.json` in their run folders (named exceptions below, R1-R3).
- E58/N4 numbers match the four committed `n4_*.json` outputs (exception R6c).
- The X3 patch is a faithful implementation of tevador's 2026-05-28 comment: edge 1
  from real outgoing only, local txs pinned to it (the `get_stem` nil-source pin),
  edge 2 the /16-deduplicated union with the virtual list (one random /24 per /16,
  one random conn per /24, cap 12, deduped against outgoing /16s), `x3` epoch events.
  With the flag off the stock code path is byte-identical (the else-branch is the
  original code; `get_stem`'s pin is flag-guarded). Adoption scope (relays/mediums/
  observers via `**st`; users and sender-a/b excluded) matches the cells' design.
- The E62-vs-E27 precision comparator is fair: the estimator's "busy 5 / 65 txs" row
  is the five miner wallets (deterministic, identical in both runs), so the
  "unreachable" class is the same 40-user class on both sides.
- simbox3's `monerod-sim` (md5 4dc0d4da) carries all fourteen sim flags (`strings`
  check); P53 runs the right binary. tr's is 8e73b0a7.
- The running cells match their predictions: P53's cell is exactly
  `fx_x3_mw25h_ui43200_rs60_bs6_s12345` (START 10:26); P54's is
  `sr300_ud_x3_s12345` (START 10:31). Both >20 h cells carry the fixed RandomX seed;
  P54's 19 h stop correctly does not.
- Predictions P49-P54 were filed before queueing (commit times vs queue STARTs).

## Findings

R1 (moderate, wrong headline number in three places). E61's "light 0.2935 = 1.92x the
ceiling" divides by the standard cell's 0.1531. Run 100's own calibration model is
**0.1299** (`meta.json model_out`, 366 honest reachable in 295 /24s); by the program's
own convention (each run quotes against its own `model_out`, as E27 does) the
multiplier is **2.26x**, not 1.92x. The conclusion ("the passive multiplier transfers
to mainnet rate") is strengthened, not weakened. Carried in: E61 entry,
findings-summary Finding 6, commit 6847ffee. Not pre-registered (P51's clauses are
unaffected; five-of-five stands). Same care needed when writing E63/E64: quote against
each run's own `model_out`.

R2 (minor, one-sender slip). E61's "38 of 49 (77.6 %) had at least one tx exposed" —
the estimator's combined-exposure table reads reachable 2-4: **38/47** plus 1 tx:
**1/2** = **39 of 49 = 79.6 %**. (The unreachable 8/37 and busy 19/22 sums check out.)
Carried in: E61 entry, findings-summary Finding 6, commit 6847ffee ("78 % exposed").

R3 (minor, arithmetic phrasing). E62's "for the plan's ~0.3 the user would need to
forward ~2.3 relayed stems per own tx, ~15x what the mechanism delivers" mixes two
ratios: the mechanism delivers 0.067 relayed stems per own tx (71/1,063), so ~2.3 per
own is **~34x** what it delivers; 15x is the own:cover ratio (1,063:71), not the
shortfall factor. Likewise "the dilution arithmetic gives ~0.94-0.98": the plain
arithmetic gives 0.937; 0.983 is the measured value. Conclusion unaffected (every one
of these numbers is far above the 0.6 reading-rule ceiling). Carried in: E62 entry,
findings-summary Finding 7, commits 72b60789/fa24f6b5/00bcdb12 ("15x too thin").

R4 (moderate, process). The section-3 register table ends at run 97
(`<!-- register:end -->`); runs 98-102 have no rows, though the entries and commit
messages call them registered. Per-run artifact folders exist for all five. The
register is the program's run inventory; five rows are missing.

R5 (minor, doc rot). Findings-summary internal counters disagree with each other and
with the journal: header says "E1-E61/P1-P51, 100 runs", the Pointers section says
"E1-E57/P1-P48, 97 runs", the journal is at E62/P54 and run 102. Finding 7 and the
bottom line were updated; the counters and pointers were not.

R6 (moderate, reproducibility). Three groups of quoted numbers have no committed,
working artifact behind them:
  (a) E62's cover census — the 71 relayed stems, the edge-kind counts, the smoke's
      107-vs-0 — exists only in prose. The only surviving script (tr:/tmp/verify_x3.py)
      is a broken draft: `kind()` returns a constant, `my_ip_of` is a stub, dead
      conditionals. The 30,961 x3-event count is trivially re-derivable from the
      archived txrelay log; the census is not.
  (b) E59/E60's dump-composition numbers (spy entry counts, front/honest ages,
      newest-20 cut) come from tr:/tmp/read_dumps.py — working, but uncommitted and
      referenced by name in the journal.
  (c) E58's "first fluffs are handed over by well-connected relays and miners —
      24.5k and 13.6k of them" — cue-level first-fluffer counts that no committed
      n4 artifact carries (the jsons' `fluff1.first_fluffer` are per-tx counts with
      no miner class).

R7 (minor, latent code defect). `sim_stemmable.h`'s CIDR-file parser: the length
digit-check `for (const char c : len) if (c < '0' || c > '9') continue;` — `continue`
skips the loop iteration, not the line, so a malformed length like `10.0.0.0/8x`
reaches `std::stoi` and throws (uncaught, node init dies) instead of skipping the
line. Only reachable with `--sim-stemmable-cidrs` and a malformed file; no current or
queued cell passes one (the X3b strategy-pole cells are the first that will).

R8 (minor, provenance typo). P54's prediction text records the cell as
`..._n600_x3_sr300_ud_s12345`; the queued and running cell is
`..._n600_sr300_ud_x3_s12345` (make_lean's tag order puts `_x3` last). The failed
first launch (guessed tag order) left the guess in the prediction text.

R9 (observation, interpretation only). The estimator's classes are
blocked-ports + tx-count thresholds, not the designed schedules: in X1a, "busy 22"
is 6 sender-b plus ~16 sender-a that happened to reach 5 txs, and "occasional 49"
excludes them (and includes the miners at ~2 txs); selection on tx count correlates
with exposure, so the class table's mapping to the plan's section 2.3 classes is
approximate. Directionally robust (caps and precisions match ground truth), but
E63/P53's class read should state the threshold semantics, or score sender-a/b by
name prefix.

## Suggested fix order (not applied; awaiting the owner)

1. R1/R2/R3: dated correction lines in the journal (the P32-correction pattern) plus
   in-place fixes to findings summary; no run artifacts change.
2. R4: register rows 98-102 from the runs/ folders' meta.json files.
3. R6: commit read_dumps.py to adhoc/; write a working x3 census script, run it
   against the array copy of run 102, and confirm (or correct) the 71 in a dated
   line; re-derive the 24.5k/13.6k or drop the sentence.
4. R7: one-line patch fix (`continue` → line-skip), rebuild on both boxes before the
   first X3b cell that passes a cidrs file.
5. R5/R8: counter refresh; P54 cell-name correction line.
