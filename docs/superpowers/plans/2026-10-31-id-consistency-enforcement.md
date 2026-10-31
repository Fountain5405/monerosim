# Identity-Consistency Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build and queue the observational id-consistency defense: R1 (shared id, direct evidence only, grace G) + R2 (self-advertisement contradiction) + egress hygiene, as the series' 16th sim patch with a shared-id fleet mode and the k42 trio cells.

**Architecture:** A self-contained, unit-testable evidence class (`id_evidence_map`) holds the rules; node_server wiring feeds it direct observations (handshake, ping, self-advertisement) and consults it at white promotion and gossip egress. Fleet mode forces all spies to one id at the id-generation site. Cells cross enforcement on/off with shared-id vs per-endpoint fleets; I1 (running) is the baseline.

**Spec:** `docs/superpowers/specs/20261031-id-consistency-enforcement-design.md` (approved 2026-10-31).

## Global Constraints

- Pin `v0.18.5.1`; patch work in a fresh worktree stacked on the 15-patch R8 baseline (procedure: commit the R8 state, diff after edits).
- Flags off by default, bit-identical to stock when off: `--sim-enforce-id-consistency G_hours` (0 = stock), `--sim-shared-spy-id`.
- Hearsay never enters the evidence map — direct observations only (R1's anti-framing property).
- Public zone only. No wire-format changes.
- Predictions filed before queueing; cells via make_cell.sh; scp travel; no origin pushes; no pkill -f.
- R9 box rebuilds ONLY after both queues drain (~15:30 UTC — a mid-run binary swap corrupts staggered agent starts).

## Review Focus

1. **Id migration inside the grace window** (honest dynamic-IP): must NOT flag when the old address's evidence is stale beyond G — test pins the boundary at exactly G.
2. **Id change at the same address** (honest restart): never a violation — test.
3. **Two addresses, grace expired, then re-observation of the old address** (proxy returning to a parked IP): flags — test.
4. **G=0 flag-off**: map inert, no behavioral delta — test.
5. **R2 over one connection** (handshake id vs self-advertised id differing): violation recorded against the address — test at the wiring seam via the class's observe API.

---

### Task 1: Evidence class + rules (unit-tested), node_server wiring, fleet mode

**Files (worktree at pin, stacked on R8):** `src/p2p/id_evidence_map.h` (new class, header-only), `src/p2p/net_node.{h,cpp,inl}` (flags, wiring at handshake/ping/timed_sync observation points, white-promotion gate, gossip-egress check, shared-spy-id at the id-generation site), `tests/unit_tests/test_id_consistency.cpp` (new; add to tests/unit_tests/CMakeLists.txt).

**Interfaces:** `id_evidence_map::observe(id, adr, now) -> std::vector<adr> (addresses newly in violation)`; `in_violation(adr_or_id)`; `violation_free(adr, id, now)`; grace hours in ctor. Tests construct the class directly (no node_server needed); the wiring is verified by the cells.

- [ ] Five failing tests (one per Review Focus line), exact assertions on returned violation sets.
- [ ] Run on tr (`-j12`, beside the cells): FAIL (header missing).
- [ ] Implement the class (time-windowed id->address multimap; violation = an address holding direct evidence older than the newest while within G of it) + wiring + both flags + MGINFO lines.
- [ ] Rebuild, tests PASS; full `peer_list.*` and existing suites still pass.
- [ ] Extract `patches/monero-sim-id-consistency.patch` vs the R8-committed baseline; verify the 16-patch series applies clean at the pin; commit; update setup.sh array.

### Task 2: Generator flags

`--id-enforce G` (tag `_idc{G}`) and `--shared-spy-id` (tag `_sid`), head-level emission per the established pattern; structural check (one head occurrence each; 63 spies / 9 nodes unaffected); commit.

### Task 3: R9 rebuilds (after ~15:30 drain) + verification

Push repo; `setup.sh --sim-binary` with the delayed-y feed on both boxes; verify `--help` shows both flags; record md5s as R9; decision row.

### Task 4: Filings P68-P70 + cells S1/S2/S3 + queue

S1 `k42 m7` + `_sid` (P68), S2 `+ _sid _idc24` (P69), S3 `+ _idc24` only (P70; baseline = I1). Bands per the spec's success criteria. Queue S1-S3 on tr after its drain; make_cell.sh md5s in filings; scp; absolute-path driver; watchers; handoff.
