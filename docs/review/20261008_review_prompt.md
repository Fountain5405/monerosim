# Independent review of the `dev` branch: Share-or-Perish (MRL #146) campaign 7

You are reviewing research done by another agent working with the owner of this repository. The owner wants to know which findings are true and valid before relying on them or reporting them publicly. Be skeptical. The author has already corrected several of its own claims after checking them (listed below), so assume more errors may remain. Your job is to find them, not to defend the work.

Do not re-run simulations. Verify everything else from primary sources: the code, the patches, the extracted logs of the finished runs, the stored analysis outputs, the monero source and the MRL #146 text.

## Setup (fresh clone)

1. Clone `https://github.com/Fountain5405/monerosim`, check out `dev`. Record the HEAD hash in your report.
2. Put `monerosim_campaign7_evidence.tar.xz` (given to you separately) in the repo root and run `tar -xJf monerosim_campaign7_evidence.tar.xz`. This creates `archived_runs/` (git-ignored) with 72 runs. Each daemon log keeps only the lines the analysis scripts read; the per-share receive lines are kept for the three `banfix` runs only. Machine paths were replaced with `/home/user` and `/tmp/scratch`. See `data/campaign7/README.md`. Anything that needs lines outside the extract is NOT VERIFIABLE; say so instead of guessing.
3. Python: create `venv/` with the packages the scripts and tests import (try `pip install -r requirements.txt` if present). Run `venv/bin/python -m pytest -q`. The author's last run gave 886 passed, 2 skipped.
4. Monero source: clone `monero-project/monero` at tag `v0.18.5.1` outside the repo, for example in `/tmp/dev_review/monero`.
5. Spec: `gh issue view 146 --repo monero-project/research-lab --json body,comments`, or the web page. tevador's simulator is `share-or-perish/blockhain-sim.py` in `github.com/tevador/scratchpad`.

## Deliverable

Write ONE markdown file, `review_report.md`, in the repo root, and do not commit it. The owner will carry it back. Write nothing else in the repo. The report must stand on its own: someone who reads only it should know what holds, what doesn't, and why.

Structure:
1. **Verdict summary.** The 5–10 most important problems, ranked by how much they would change what the owner reports. Then one line on what you found solid.
2. **Claim ledger.** One row per claim (the list below, plus anything you add):
   - the claim, quoted with its file:line;
   - the verdict: CONFIRMED, CONFIRMED WITH CAVEAT, OVERSTATED, WRONG or NOT VERIFIABLE;
   - how you checked it: reproduced from data (give the command and the key output), read in code (file:line), or read in the spec (quote);
   - if it isn't confirmed, the corrected statement.
3. **Method critique.** Whether each approach is fit for the claim it supports. Cover topology size, statistics, model assumptions, attacker fidelity, simulator fidelity to the spec, and confounds.
4. **Interpretation critique.** Where the conclusions go further than the evidence, or where another reading fits the data as well.
5. **Doc consistency.** Places where the results doc, manuscript, conformance doc and code disagree with each other. Also any superseded number still presented as current.
6. **Not checked.** What you could not verify, and why.
7. **Checks run.** Every command you ran, with its exit status.

Quote primary sources exactly. Mark anything you infer, rather than read or measure, as inference.

## Hard rules

- Do NOT run simulations: no `scripts/selfish_matrix.py` except `--reanalyze`, no `run_sim.sh`, no `shadow`, no `setup.sh`, no monerod.
- Do NOT edit, create or delete any file in the repo other than the report. No git commits, no pushes, no branch changes, no `git stash`, no checkouts.
- Do NOT post to GitHub or any outside service. Reading with `gh` is fine, for example `gh issue view 146 --repo monero-project/research-lab --json body,comments`.
- Treat `archived_runs/` and `data/` as read-only. Write scratch files only under `/tmp/dev_review/`.
- Allowed: reading anything; `venv/bin/python -m pytest -q`; the analysis scripts on existing run directories; your own read-only Python or grep over logs; `git log`, `git show`, `git diff`. Memory pressure is not a concern (1 TB of swap). The daemon logs are large, so stream them.

## Where things are

- **Campaign-7 work:** the commits from `0b9e8089` (2026-09-30, the SoP fidelity audit) to HEAD. Commit messages carry the reasoning, so read them.
- **Main results:** `docs/20261007_sop_campaign7_results.md`. Start here: its summary table states a confidence for each finding.
- **Manuscript:** `docs/20260922_selfish_mining_manuscript.md`, findings 9 and 10, §7 ledger (run ID → commit → spec), Appendix A (the superseded text).
- **Implementation conventions:** `docs/20260930_sop_conformance.md`.
- **Superseded docs (should be marked so):** `docs/20260923_sop_design.md`, `docs/20260926_exact_uncles_and_sop_controls.md`, `docs/20260926_sop_h10_rerun.md`.
- **Daemon patches:** `patches/*.patch`, applied in the order `setup.sh` uses. SoP fork choice, `--sim-sop-rejudge-displaced` and the ban fix are in `patches/monero-sim-pop.patch` (`sim_sop_should_switch`, `sim_pop_should_switch`, the `hit_score` change).
- **Attacker and miners:** `agents/selfish_strategy.py` (`window_stubborn`), `agents/selfish_miner.py`.
- **Analysis tools:** `scripts/selfish_mining/` (`sop_reveals`, `sop_shares`, `sop_model_compare`, `p2p_ban_replay`, `flipback_scan`, each with tests), `scripts/sop_oracle.py` (re-derives every logged fork-choice decision), `scripts/sop_race_model.py` (Model B, cheap to re-run), `scripts/selfish_matrix.py --reanalyze <spec>`.
- **Stored data:** `data/campaign7/` (analysis outputs, Model B results, matrix cell records).
- **Run data:** `archived_runs/<run>/` from the tarball. `daemon_logs/<node>/bitmonero.log` has `SIM-SoP-DEC` JSON lines for every fork-choice decision. Run IDs are in results doc §2 and manuscript §7.
- **Provenance:** dev's history was rewritten on 2026-09-27. Older run records may carry pre-rewrite hashes that you cannot map, so flag them rather than guess.

## Claims to check (headline first)

1. **SoP defeats the spec's stubborn attacker.**
   - At α = 0.33 the attacker's revenue share falls from about 0.30 under stock to 0.015–0.025 under SoP (13 runs of 240 h, plus the 3 `banfix` runs).
   - At α 0.40 it is 0.11–0.19 (6 h, n = 3); at α 0.45, 0.37.

   Check:
   - how "share" is computed;
   - that the attacker follows the spec's stubborn strategy (reveal at ≥ 48 own work objects with more weight; give up at depth d);
   - that the simulator implements Tables 3–5 as written (`docs/20260930_sop_conformance.md` against the patch);
   - whether the miner fix (`e2955754`) and the 2026-09-30 audit (`0b9e8089`) really make earlier SoP numbers unusable.
2. **Model B reproduces the simulator** (revenue, reveal rate, orphan rates, race shapes, reorg depth). Check its assumptions (Poisson objects, fixed difficulty, "canonical day" = 720 kept blocks) and whether "reproduces" is earned or just "doesn't contradict".
3. **10+ block reorg rates by give-up depth** (Model B at α 0.33: once per 2.9, 1.5 and 0.41 years at d = 2, 3, 5). Also the claim that #146's "about 1 per 3 years" is the rate of tevador's T5 attacker, which counts work objects, not blocks, and is not a bound.
4. **The P2P ban cascade.** Under SoP, nodes switch to shorter, heavier branches. Stock monero's `hit_score` at three call sites penalizes the peer's height drop; at `DROP_PEERS_ON_SCORE` the connection is dropped with fail score 5; past `P2P_IP_FAILS_BEFORE_BLOCK` (10) the host is blocked for 24 h, and the score never decays. Bans appeared in 3 of 5 d5 runs, and 67 of 67 were replayed exactly. Then the fix (`002cd40c`) and its check (§6.4: 0 bans and 0 scored drops in 3 × 240 h). Check the monero constants and code paths, the replay logic, and whether the fix is safe, given that it also stops penalizing peers that misreport their height.
5. **SoP is a hard fork** (results §7 item 2). Check:
   - the `version_minor` = workshare-count rule in the issue text;
   - `HardFork::do_check` in v0.18.5.1;
   - the "has old version" observation in run `20260930_161539`;
   - that every sim daemon skips the vote check, so no run contains a real unupgraded node.
6. **Re-judging displaced blocks.** IMPORTANT: the docs are out of date here. Results §7 item 1 and summary row 5 present two "readings" (rejudge vs whole_branch) with attacker revenue {0.043, 0.000} vs 0.187 at α 0.40. The author's current position (2026-10-08), not yet in the docs, has four parts. Check each part:
   - a. In stock monerod, after a reorg every displaced block goes back through `handle_alternative_block` (stock blockchain.cpp ~1167–1179 in v0.18.5.1), so the fork choice is re-run. Under cumulative difficulty this check can never succeed.
   - b. SoP's pairwise comparison can say "switch" in both directions for the same two branches. n_f counts only the side branch's work objects, and lateness is timed against whichever block is main at each height. Worked example: the conformance doc's worked example 2, replayed in arrival order: 4,104 vs 912 one way, 912 vs 456 the other.
   - c. The rejudge result is a monerod accident, not a reading of the spec:
     - the re-check switches back inside the first switch;
     - the nested switch fails to re-file the attacker's blocks (duplicate check, blockchain.cpp ~2073);
     - the outer switch then deletes them from the alt store (~1182–1186).

     The claimed evidence is the attacker-bridge logs of `archived_runs/20261004_111002_stubborn_h10_rejudge*`: no honest node ever reorganized in the runs with flip-backs, and in the `rejudge_rep` α 0.40 run no honest node ever evaluated a side block.
   - d. Our default (`whole_branch`: displaced blocks are stored unjudged and re-judged only when a new block extends them) matches tevador's simulator, which treats a winning reveal as final.

   Also check the issue's own sentence "the two chains differ by fewer than k*w work objects" against its formal n_f definition.
7. **§7.1 thread claims** about albinjm's 2026-10-04 comment and tevador's 2025-10-15 comment, and the reading that Tables 4 and 5 apply to both chains.
8. **Controls (§8)** and the deviation in **§9 / conformance doc**: "n_f counts shared workshares; it cannot affect our attack forks". Also "our attacker never embeds honest workshares". Look at the attacker's `n_sh` values in the `SIM-SoP-DEC` lines.
9. **Statistics:** the depth test, binomial tests, the "not significant" and "did not replicate" calls, and whether n = 2–3 short runs support the stated ranges.
10. **Superseded handling:** every SoP number from before 2026-10-04 is marked superseded wherever it appears, and nothing superseded is still cited as current.

Also look for problems nobody asked about, for example:
- whether the 12-daemon topology or the h10 chain snapshot drives any result;
- whether moving from Shadow v0.2.4 to v0.2.5, or unpinned CPUs, could confound comparisons;
- whether the seeds give independent runs;
- whether the analysis scripts parse the logs correctly. Spot-check them against raw lines.

## Corrections the author already made (check they propagated)

- "1 per 3 years holds only at d = 2": wrong. T5 counts work objects, d counts blocks.
- "Per-time claims assume a fixed block rate": withdrawn. tevador sets difficulty from honest hashrate.
- "Per real day the rates are 1.5× higher": wrong. Model B's canonical days are real days.
- "We judge only the alt chain": wrong. Lateness applies to both chains.
- "Not a soft fork may be partly ours": wrong. The `version_minor` rule is the spec's.
- A depth-tail "excess" at d5 did not replicate and is not reported.
- The re-judging reframing in claim 6, which is not yet in the docs.

Be concrete. A finding without a file:line, a quote or a command output is not useful here.
