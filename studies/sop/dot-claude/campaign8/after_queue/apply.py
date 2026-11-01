#!/usr/bin/env python3
"""Apply the post-campaign-8 SoP change to the repo (run from the repo root
once the rev2 queue has ended):

  venv/bin/python .claude/campaign8/after_queue/apply.py

What it does:
- installs the prepared patches/monero-sim-pop.patch: the --sim-sop-nf-rule
  option is gone (the revised #146 n_f is the only rule), the window test
  follows the revised h_f (last common block: h0 + 1 < first alt block),
  h0 is the node's tip at its first sync (an --offline node: its DB tip,
  from startup), a node judges objectively until it comes online (record
  field "online"), decision log v3;
- drops `sim-sop-nf-rule: either` from every matrix spec (the new daemon
  rejects the unknown option) and from run_sim_helpers' option map;
- updates docs/20260930_sop_conformance.md to match.

It changes files only; it commits nothing. Afterwards the owner runs
`./setup.sh --sim-binary`; then smoke, pytest, commit.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("APPLY_REPO") or Path(__file__).resolve().parents[3])
HERE = Path(__file__).resolve().parent

LATE_STARTERS = """- *Fixed in log v3:* **`h_0` for a node that starts behind the network
  (found 2026-10-16).** Logs v1 and v2 took `h_0` as the database tip at
  startup. A node that started after the network had mined past that tip
  got an `h_0` below the height at which it came online, so it could judge
  forks it received only while catching up as if it had seen them live.
  We read "the block height when the node came online" as the node's tip
  once it has caught up and follows the network live; from log v3 that is
  its tip at its first sync (convention 3). Every matrix daemon starts on
  the snapshot tip, but not at once: miners at 0 s, seeds at 5 s, and
  relays at 30 s and 60 s (12 daemons) or every 10 s up to 260 s (40
  daemons). Checked 2026-10-19 over 166 archived SoP runs, 73 of them with
  decisions up to height 1050 (11,152 decisions): 62 deciding nodes, all
  relays, came online one to three blocks above their database tip (18 in
  14 of 70 twelve-daemon runs, and 44 of the 72 relays in the three
  40-daemon runs). None decided while catching up. 14 of their decisions were on
  forks off a block at or below the height they came online at, all in
  one run and all objective under either `h_0` (a branch held at least 57
  work objects), so no regime or outcome changed. From log v3 a node also
  judges every fork objectively until it comes online, so a fork it meets
  while catching up is judged on work alone. No archived decision was
  taken before its node came online.
"""


def edit(path, pairs):
    p = REPO / path
    t = p.read_text()
    for old, new in pairs:
        if t.count(old) != 1:
            sys.exit(f"{path}: expected one match for {old[:60]!r}")
        t = t.replace(old, new)
    p.write_text(t)


def main():
    busy = subprocess.run(["pgrep", "-f", "run_queue|selfish_matrix|bin/shadow"],
                          capture_output=True, text=True).stdout.split()
    if busy and not os.environ.get("APPLY_REPO"):
        sys.exit(f"sims or a queue are still running (pids {' '.join(busy)}); not applying")

    n = 0
    for spec in sorted((REPO / "test_configs/matrix").glob("*.yaml")):
        lines = spec.read_text().splitlines(keepends=True)
        kept = [l for l in lines if l.strip() != "sim-sop-nf-rule: either"]
        if any("sim-sop-nf-rule" in l and not l.lstrip().startswith("#") for l in kept):
            sys.exit(f"{spec}: unexpected sim-sop-nf-rule line left")
        if len(kept) != len(lines):
            spec.write_text("".join(kept))
            n += 1
    print(f"specs edited: {n}")

    edit("scripts/run_sim_helpers.py", [
        ("    'sim-sop-nf-rule': 'sim-sop-nf-rule',\n", ""),
    ])

    edit("docs/20260930_sop_conformance.md", [
        ("""   was online before the first diverging block. The revised text defines
   `h_f` as the last common block, one lower, so the spec's test is
   `h_0 < hf - 1` in our terms. The two differ only for a node whose `h_0`
   is exactly the last common block's height (see Known deviations).
""", """   was online before the first diverging block. The revised text defines
   `h_f` as the last common block, one lower, so from log v3 the window
   test is `h_0 < hf - 1` (the daemon: `h0 + 1 < hf`). Logs v1 and v2
   tested `h_0 < hf`. The strict test keeps a fork off the block the node
   started on objective: the node may have missed the gossip of shares
   mined on that block before it came online.

   `h_0` is the node's tip once it has caught up and follows the network
   live. From log v3 the node comes online when monerod first counts it
   as synchronized, which it must be before it mines: at its first sync
   ("You are now synchronized with the network"), with `h_0` its tip
   then. The attacker's private miner runs `--offline`, which monerod
   counts as synchronized from startup; it never syncs, so it comes
   online at startup with the database tip as `h_0`. The daemon logs
   `SIM-SoP: online, h0=...` when the node comes online. Until then the
   node judges every fork objectively (record field `online: false`):
   its receive times are download times, not live observation. Logs v1
   and v2 used the database tip at startup throughout.
"""),
        ("""  h", which changes when the node switches. The daemon's
  `--sim-sop-nf-rule alt` and the v1 log records reproduce it.
""", """  h", which changes when the node switches. The v1 log records reproduce
  it (the oracle replays them with rule `alt`).
"""),
        ("""11. **`n_f` rule.** The daemon flag `--sim-sop-nf-rule` picks the regime
    test. `either` is the revised spec: the window is open while both
    `nf` (alt) and `nf_main` are below `k*w`. `alt` is the earlier formal
    reading, where only `nf` counts. The flag still defaults to `alt`, so a
    spec run must pass `either`; every `sop_either_*` and `sop_rev2_*`
    matrix spec does. The oracle uses the rule the record logs (`nf_rule`),
    and records from before the flag mean `alt`.
""", """11. **`n_f` rule.** The window is open while both `nf` (alt) and
    `nf_main` are below `k*w`: the revised spec, logged as
    `nf_rule: "either"`. The daemon option `--sim-sop-nf-rule`, which also
    offered the earlier alt-only reading (`alt`, its default), was removed
    after campaign 8. The oracle uses the rule a record logs, and records
    from before the option mean `alt`.
"""),
        ("""- **`h_0` at the last common block (found 2026-10-16).** Convention 3 opens
  the window when `h_0 < hf` (first alt block); the revised spec needs
  `h_0 <` the last common block. A node that came online exactly at the
  last common block's height gets a subjective window where the spec says
  objective. The strict test matters: the shares in such a fork were mined
  on a block that existed before the node came online, so the node may
  have missed their gossip. Not fixed in the current build (log v2); fixed
  in log v3. Checked 2026-10-16 over the first 400 decisions of every node
  log in 155 archived SoP runs: 134 of 78,430 decisions, in 7 runs, had
  `h_0` at the last common block (forks off the snapshot tip). 45 of them
  were subjective and become objective under the spec's test, and 2
  outcomes change, both in a `rejudge` run. On the rev2 build: 4
  decisions, in one smoke run, with no outcome change.
""", """- *Fixed in log v3:* **`h_0` at the last common block (found
  2026-10-16).** Logs v1 and v2 opened the window when `h_0 < hf` (first
  alt block); the revised spec needs `h_0 <` the last common block. A node
  that came online exactly at the last common block's height got a
  subjective window where the spec says objective. Over the first 400
  decisions of every node log in 155 archived SoP runs, 134 of 78,430
  decisions, in 7 runs, were such cases (forks off the snapshot tip); 45
  were subjective, and 2 outcomes would change, both in a `rejudge` run.
"""),
        ("""| `v` | int | format version: `2` since 2026-10-15 (block entries carry `ref`), `1` before |""",
         """| `v` | int | format version: `3` after campaign 8 (window test on the revised `h_f`, `h_0` from the first sync, `online`: convention 3), `2` from 2026-10-15 (block entries carry `ref`), `1` before |"""),
        ("""| `nf_rule` | str | `"alt"` or `"either"` (convention 11); absent in records from before the flag |""",
         """| `nf_rule` | str | `"either"` from v3; `"alt"` or `"either"` in older records (convention 11); absent in records from before the option |"""),
        ("""| `h0` | int | the node's `h_0` |""",
         """| `h0` | int | the node's `h_0` at this decision; from v3 the database tip until the node comes online, then the tip it came online at (convention 3) |
| `online` | bool | from v3: whether the node had come online (convention 3); `false` forces the objective regime |"""),
    ])
    # The late-starter entry, replaced whole: it runs from its heading to the
    # first "Not fixed." after it.
    p = REPO / "docs/20260930_sop_conformance.md"
    t = p.read_text()
    head = "- **`h_0` for a node that starts behind the network (found 2026-10-16).**"
    i = t.find(head)
    j = t.find(" Not fixed.\n", i)
    if t.count(head) != 1 or j < 0:
        sys.exit("docs/20260930_sop_conformance.md: late-starter entry not found")
    p.write_text(t[:i] + LATE_STARTERS + t[j + len(" Not fixed.\n"):])
    (REPO / "patches/monero-sim-pop.patch").write_bytes(
        (HERE / "monero-sim-pop.patch").read_bytes())
    print("applied; next: ./setup.sh --sim-binary (owner), smoke, pytest, commit")


if __name__ == "__main__":
    main()
