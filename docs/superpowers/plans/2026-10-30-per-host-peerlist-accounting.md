# Per-Host Peer-List Accounting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and measure the per-host peer-list cap (at most N ports per IP in white/gray, one entry per host in the gossip head) as a sim patch, generator flag, and cell series.

**Architecture:** One flag-gated monero patch implements R1 (list caps at the insert sites) and R2 (per-host gossip head); make_lean grows `--host-port-limit` to emit it into every daemon's options; boxes rebuild the patched binary; six pre-registered cells read stock vs capped at the fleet's real shape (9 /24s, 7 ports per IP — the existing `--spies-per-subnet` already packs m daemons onto one node, proven by the k8 m5 cell that ran as E67/P59).

**Tech Stack:** C++17 (monero v0.18.5.1 patch series, boost::multi_index peerlist), Python (make_lean generator), bash queue drivers, Shadow simulation on tr/simbox3.

**Spec:** `docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md` (approved 2026-10-30).

## Global Constraints

- Monero pin: tag `v0.18.5.1` (commit 4f92268d). Patch work happens in a FRESH worktree at the pin, never in /tmp/monero13 (hand state, memory: patch-validation-fresh-worktree).
- Every sim flag is off by default and bit-identical to stock when off (the series' rule; setup.sh:52).
- Flag name verbatim: `--sim-peerlist-ports-per-host N`, N=0 means stock infinity (flag off).
- Cells are gitignored: they travel by scp; md5s come only from `make_cell.sh` (pins phantom calibration e5276ee06c11 and MONEROSIM_CORES=32).
- Predictions are filed in the journal BEFORE cells are queued (memory: experiment-journal).
- Never push to origin (public GitHub); lab boxes tr/simbox3 only (memory: no-github-push).
- No `pkill -f` anywhere (memory: no-pkill-f).

## Review Focus

1. **A host at cap in white whose other port is gossiped into gray** — the gray cap must apply independently (gray has its own N), not inherit white's count. Test: Task 1, Step 1.
2. **Two ports of one host promoting while at cap** — second promote must displace the host's oldest white entry, not be silently dropped (contact always wins). Test: Task 1, Step 1.
3. **v4-mapped IPv6 vs IPv4 of the same address** — must count as one host (same host key as the pick's host-dedup uses). Test: Task 1, Step 1.
4. **A white list dominated by one host's ports** — R2 must still return at most one entry for that host in the 250-sample, and the sample must not degenerate (still ≤250 total). Test: Task 1, Step 1.
5. **N=0 (stock) and N greater than ports present** — both must be exact no-ops; N=0 must be bit-identical behavior to unpatched stock. Test: Task 1, Step 1.

---

### Task 1: The cap patch with unit tests

**Files:**
- Create: `patches/monero-sim-peerlist-ports-per-host.patch` (generated from the worktree diff)
- Modify (inside the fresh worktree at the pin): `src/p2p/net_node.cpp` (arg descriptor), `src/p2p/net_node.h` (member `size_t m_sim_peerlist_ports_per_host = 0;`), `src/p2p/net_node.inl` (arg add + init_get_config read + MGINFO when nonzero), `src/p2p/net_peerlist.h` (R1 and R2), `tests/unit_tests/test_peerlist.cpp` (the cap tests)

**Interfaces:**
- Produces: `--sim-peerlist-ports-per-host N` (0 = stock), read by node_server init and enforced by peerlist_manager; consumed by Task 2's generator emission and Task 4's cells.

- [ ] **Step 1: Write the failing tests in `tests/unit_tests/test_peerlist.cpp`**

Five tests, one per Review Focus line, using the file's existing peerlist_manager test fixtures:
`per_host_cap_white_gray_independent`, `per_host_cap_promotion_displaces_oldest`,
`per_host_cap_v4_mapped_ipv6_same_host`, `per_host_cap_gossip_head_one_per_host`,
`per_host_cap_zero_and_large_n_noop`. Each constructs a peerlist_manager, inserts 3-4 ports of
one host (and a second host's single entry), sets the cap via the manager's new setter
`set_ports_per_host_limit(N)` (peerlist_manager needs the value passed from node_server; a
setter keeps the manager testable), and asserts entry counts / displaced ids / gossip head
composition. Assertions use exact counts (e.g., white holds 1 entry for the host at N=1, the
newest port's id, and the other host untouched).

- [ ] **Step 2: Build and run the tests to verify they fail**

Run: in the worktree, cmake build target `unit_tests` then `./build/debug/tests/unit_tests/unit_tests --run_test=peerlist/*per_host*` (follow the existing test_peerlist build path).
Expected: FAIL — `set_ports_per_host_limit` not declared.

- [ ] **Step 3: Implement the patch**

In `net_peerlist.h`: `set_ports_per_host_limit(size_t)` stores the limit (0 = infinity);
R1 as a private helper `enforce_per_host_cap(list, new_entry)` called from
`append_with_peer_white` and `append_with_peer_gray` after insert and from the merge path:
if the limit is nonzero and the host (same host_str key as the pick's `get_host_string`)
now exceeds N entries, erase that host's oldest-by-last_seen entry unless it is the just-
inserted one. R2 in `get_peerlist_head`: skip a sampled entry whose host was already emitted
(this only tightens the existing random sample). In net_node.{cpp,h,inl}: the arg descriptor,
member (default 0), init read, one MGINFO when nonzero, and the call to the setter per zone.
All under the existing patch-series style (compare monero-sim-whitelist-candidates.patch).

- [ ] **Step 4: Run the tests to verify they pass**

Run: same as Step 2. Expected: PASS, all five.
Then `git diff` in the worktree → write it as `patches/monero-sim-peerlist-ports-per-host.patch` (path-stripped, series style: header comment lines naming the flag, default, and what it models).

- [ ] **Step 5: Commit**

```bash
git add patches/monero-sim-peerlist-ports-per-host.patch
git commit -m "feat(sim): per-host peer-list accounting patch (R1 list caps + R2 gossip head cap)"
```

### Task 2: Generator flag `--host-port-limit`

**Files:**
- Modify: `test_configs/x0/make_lean.py`

**Interfaces:**
- Consumes: Task 1's flag name `sim-peerlist-ports-per-host`.
- Produces: `--host-port-limit N` (default 0 = omit the option entirely), cell tag `_hpl{N}`, written into every daemon's options header (honest and spy — the cap is global policy, like `sim-subnet-dedup`).

- [ ] **Step 1: Write the failing structural check**

```bash
venv/bin/python test_configs/x0/make_lean.py --reachable 300 --spy-subnets 9 \
  --spies-per-subnet 7 --spy-node0 600 --warmup 46800 --probe 3 --dedup 24 --list none \
  --seed 12345 --host-port-limit 1 2>&1 | tail -2
```
Expected before implementation: exits with argparse error "unrecognized arguments".

- [ ] **Step 2: Implement**

Follow the `--white-limit` pattern end to end: argparse arg, `wtag` addition
(`(f"_hpl{a.host_port_limit}" if a.host_port_limit else "")` placed after the `_wc` term), and
the header regex emission
(`head = re.sub(r"(?m)^(    sim-subnet-dedup:).*", ...)` neighborhood: add
`sim-peerlist-ports-per-host: N` line for every daemon when nonzero — mirror exactly how
`sim-white-peerlist-limit` is emitted today, grep `wl` in make_lean.py).

- [ ] **Step 3: Verify**

Generate the Step 1 cell and a default (no flag) cell. Assert: the tagged cell's yaml contains
`sim-peerlist-ports-per-host: 1` under every daemon block (count equals total daemons); the
default cell's yaml contains zero occurrences; the tag `_hpl1` appears in the filename; 63 spy
agents on 9 distinct topology nodes (7 per node). Then delete both generated cells (the real
ones come from make_cell.sh in Task 4).

- [ ] **Step 4: Commit** (`git add test_configs/x0/make_lean.py`).

### Task 3: Rebuild the patched binary on both boxes

**Files:**
- Modify: none in-repo; boxes' `~/.monerosim/bin/monerod-sim` (rebuilt), provenance updated.

**Interfaces:**
- Consumes: Task 1's patch in `patches/` (reaches boxes via the repo push).
- Produces: the R8 binary (md5 recorded in the journal's next decision row), the flag visible in `monerod-sim --help`.

- [ ] **Step 1: Push the repo to tr and simbox3 (both idle, queues empty — verified).**
- [ ] **Step 2: On each box, run setup.sh's opt-in patched build** (the step that logs "Building patched monerod (monerod-sim)"); confirm the patch applied in its output.
- [ ] **Step 3: Verify**: `~/.monerosim/bin/monerod-sim --help | grep sim-peerlist-ports-per-host` on both boxes; record md5s (`md5sum`) as R8; note the previous R7 md5 in the decision row (tr 025e7b12, simbox3 e9ed436b).

### Task 4: Cells, predictions, queue

**Files:**
- Create: six cells under `test_configs/x0/cells/` (via `make_cell.sh`), journal predictions P62-P67, decision row.

**Interfaces:**
- Consumes: Task 2's `--host-port-limit`, Task 3's R8 binary, the standing queue drivers (absolute-path launch, `X0_ARCHIVE` override on tr).

- [ ] **Step 1: File predictions P62-P67 in the journal** (section 5, before any queueing), one per cell: B1 `k9 m1` stock (ports=1 baseline), M1 `k9 m7` stock, M2 `k9 m7 hpl1`, M3 `k9 m7 hpl2`, I1 `k42 m7` stock, I2 `k42 m7 hpl1`. Bands from the spec's success criteria: M2/M3 fleet white share at/below B1's share x (port multiplier)/(N... spec formula: capped share ~ stock share x N/7); honest occupancy up by the displaced entries; light toward the k-series ceiling; sp recall null expected (state it as the predicted null).
- [ ] **Step 2: Generate all six via `make_cell.sh`** (exact args as Task 2 Step 1 with `--spy-subnets 9|--spy-subnets 42`, `--spies-per-subnet 7|1`, `--host-port-limit` 0/1/2 as appropriate); record md5s in the filings.
- [ ] **Step 3: Smoke-run M1 first on tr** (full cell, ~3 h): before trusting the series, assert from its estimator header 63 spies logging and from its peerlist dumps that the 7 daemons on each spy node show distinct ports. If ports collide, STOP — the harness assumption is wrong; re-plan (spec's fallback note).
- [ ] **Step 4: Queue the rest** (tr: M2, M3, I1; simbox3: B1, I2), launch drivers with absolute q.txt paths, arm DONE watchers, decision row, commit, push.

## Post-plan (not in scope)

Scoring the six cells as E72+ per the standing recipe; the upstream note once the deltas are read.
