# studies/antiproxy — CLAUDE.md

Purpose: measure how spy fleets infiltrate Monero's peer lists and trace transaction origins
(Dandelion++ first-hop attribution), and defend against them at the p2p layer. Method: Shadow
simulations of monerod (patched, flag-gated) on two lab boxes, pre-registered predictions
scored blind against measured outcomes; mainnet evidence from the owner's nodes, a 2026-09-23
crawl, and observer.monerodevs.org daily feeds.

- The experiment journal (docs/SPY_EXPERIMENT_JOURNAL.md) is the source of truth: file a
  prediction (Pn) BEFORE queueing a cell; score it as an entry (En) after; never edit either,
  only append. `analysis/spy/run_register.py add <archive> --box <name>` registers each run.
- Cells: generate ONLY via `docs/spy_journal/drivers/make_cell.sh` (pins
  ~/.monerosim/calibration.json, md5 e5276ee06c11 — copy in this folder if missing — and
  MONEROSIM_CORES=32). Cells are gitignored; they travel by scp; the journal cites their md5s.
- Boxes: tr (antiproxy@192.168.1.33, /fast for archives) and simbox3 (lever65@192.168.1.176,
  shared VM, slower). Queue driver `~/queue/x0_queue.sh` (copy of the repo's; launch with an
  ABSOLUTE q.txt path; on tr prefix `X0_ARCHIVE=/fast/antiproxy/monerosim_archives`). Archives
  move to the array under /spinny on tr (rsync, verify by file count + `rsync -ain` empty, then
  delete local).
- Binaries: built per-box by `./setup.sh --sim-binary` (interactive: feed y's with delays —
  its 0.1 s input drain eats pre-fed answers: `{ sleep 2; echo y; sleep 3; echo y; sleep 300;
  echo n; } | ./setup.sh --sim-binary`). NEVER rebuild while a queue is running (staggered
  agents exec the binary mid-run). Binary = pin v0.18.5.1 + the 16 patches in setup.sh's array.
- Scoring a finished run: run spy_estimators.py, spy_stem_receipts.py (+ x3_census.py for x3
  cells) detached ON THE BOX (each bash -c cd's into ~/monerosim itself; scripts take
  `--json PATH`); register on the box with $HOME-expanded paths; scp the run folder back; git
  clean the box's runs dir; journal entry + outcome + decision row + counters + register table.
- Conventions: never push to origin without the owner's word (feat/spy-relay-log was
  authorized 2026-11-01); raw mainnet data NEVER enters the repo (~/monerosim_local/ only);
  no pkill -f (kill by pid); no amend once a box holds the commit; updateInstead pushes only
  into idle checkouts; .claude/HANDOFF.md is the running session log (gitignored).
- Pitfalls: BUILD_TESTS=ON cannot compile the patched series (test_core stub lacks R7+
  symbols) — unit-test new logic via a standalone g++ driver; grep -c with 0 matches exits 1
  and breaks && chains; make_lean tags decode the cell name (k=subnets, m=daemons-per-subnet
  each on its OWN IP, _hpl=ports-per-host cap, _idc=id enforcement, _sid=shared spy id);
  m-daemons do NOT share an IP (10-31 correction).

Machine-specific notes (control box): see CLAUDE.local.md (untracked, this machine only).
