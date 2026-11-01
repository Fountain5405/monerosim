# Eclipse study: status

**Closed.** Nothing runs, and no follow-up work is open. Paths are relative to
this folder unless they start at the repository root.

The study reproduced, in the simulator, the unreachable-node eclipse attack
of "Are Unreachable Nodes Truly Safe? Fully Eclipsing Monero's P2P Network!"
(Shi et al., ACM CCS 2026; arXiv:2609.10260), in 2026-09. On 2026-10-06 it
reran a colleague's 50-hour eclipse simulation with `--bootfast`.

## Findings

- The paper's core claim holds: an unreachable node is eclipsed with no
  inbound access, through the protocol's own timed sync.
- How completely it is eclipsed depends on the number of distinct-/24
  connectable endpoints, not on injected records. The ceiling is reached at
  about 950 endpoints.
- Eclipse at birth reaches 12/12 connections: 126 nodes with 120 attacker
  endpoints, in 30.8 min (the paper reports about 27). At paper scale (963
  nodes) the victim is born fully eclipsed.
- An established victim is harder to take. Real attacker nodes at 2,211 hosts
  plateau at 7/12. A port-diverse fake-peer attacker first reaches 12/12 at
  633 min, but does not hold it (12/12 in 46 % of later polls).
- The `--bootfast` rerun cut wall time from 22.5 h to 15.6 h. The eclipse
  reproduced (12/12 at simulated 21.5 h, against 20.6 h), but persistence did
  not (it ended at 9/12; the doc reads this as run-to-run variance). Both runs
  used a monerod that reverts the countermeasure commits, despite the config
  name.

## Where things are

- `docs/eclipse_reproduction.md` (method and results) and
  `docs/20261006_bootfast_eclipse_reproduction.md`.
- `configs/`: the 21 eclipse scenarios.
- These stay in core, because core and other work use them:
  - `agents/eclipse_*.py`;
  - `analysis/eclipse/`, including `results/` and `report.html`;
  - the peer-list-dump patch (`patches/monero-sim-peerlist-dump.patch`,
    documented in `docs/PEERLIST_DUMP_PATCH.md`).
- Run archives are not in git; the docs name their run directories.
