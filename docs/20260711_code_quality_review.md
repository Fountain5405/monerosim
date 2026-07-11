# Code Quality Review: Full-Codebase Assessment

**Date:** 2026-07-11
**Method:** Five parallel AI reviewers (Claude, one per subsystem) each performed
a deep read of their slice — not a lint pass; every major file was read and
mechanisms were traced through call sites — plus a git-history pass over all 598
commits. This codebase has been AI-generated ("vibe coded") from the start; the
review's explicit brief was (a) overall quality and (b) patterns that indicate
AI authorship. Findings below cite `file:line` as of commit `704cb098` (v0.2.0).
**Caveat:** findings were verified by the reviewers by tracing code paths, but
each fix in the priority list gets independently re-verified before repair.
Fix status is tracked in §6.

## 1. Verdict

**B− as a research instrument, C+ as software.** The simulator works, is
deterministic by design, and the results that matter (topology study, Rucknium
validation) rest on subsystems that are genuinely well-engineered. But the
middle strata carry heavy AI-accretion debt — dead fallback layers, N parallel
reimplementations of the same helper, fabricated statistical confidence — and a
handful of real bugs surfaced, two of which touch result integrity.

| Subsystem | LOC | Grade | One-liner |
|---|---|---|---|
| Rust orchestrator core (`src/` minus analysis) | ~9.4k | C+ | Works, deterministic, zero compiler warnings — but ~500 LOC dead code, 5× copy-pasted pipelines, one result-affecting bug |
| Rust analysis (`src/analysis/`, `tx_analyzer`) | ~7k | C+ | Sound layering; several reported metrics are fabricated confidence |
| Python agents (`agents/`) | ~9k | C+ | Solid framework, honest tests; dead fallback towers and a real file race |
| Python scripts/tooling (`scripts/`, `gml_processing/`) | ~16k | B− | Two generations welded together: 2026 code is good, 2025 leftovers are slop |
| Shell + repo hygiene (~14 scripts) | ~5.8k | B | Far better than "vibe coded" implies; breaks at the seams between sessions |

Test-coverage meta-finding: the bugs live exactly where coverage stops. 87 fast,
honest pytest tests in `agents/`; golden-file output-equivalence tests for the
Rust generator; **zero** tests for 16k LOC of `scripts/` and near-zero (10
trivia tests) for the analysis math.

## 2. The AI-tell taxonomy

The stereotypical tells (emoji spam, "Step 1/2/3" narration, `_v2_final` files)
are mostly **absent** — earlier cleanup passes (commits titled "Remove AI slop",
"Complete AI slop review") pruned them. What remains is subtler and structural.
Ranked by how diagnostic each pattern is:

### 2.1 Session-seam drift (the #1 tell)

Every unit is internally coherent; the seams *between* AI sessions are where it
breaks, because no session ever ran the combinations.

- `start_here.sh:707` passes `--full-monero`; `setup.sh` only accepts
  `--full-monero-compile` → the wizard's "Full reinstall" option exits 1,
  guaranteed. Same function mis-describes what `--clean` deletes.
- `update.sh:187,213` uses raw `-j$(nproc)`; `setup.sh:77-96` carefully computes
  RAM-capped `BUILD_JOBS` because Monero TUs OOM at ~2 GB each. The rebuild path
  never got the fix. `update.sh` also pulls sister repos to branch tips,
  silently un-pinning `setup.sh:607`'s `SHADOWFORMONERO_REF` pin.
- `scripts/configure_upgrade.py:305` still uses the old `--agents` semantics
  after `generate_config.py:393` redefined it ("--agents now means user count
  directly") → a "30 agent" wizard run emits 35 hosts.
- Wallet argument lists maintained in two places (`process/wallet.rs:16-59` vs
  `user_agents.rs:798-831`), same "do NOT set --max-concurrency" comment, kept
  in sync by hand.

### 2.2 Reimplement-instead-of-reuse, then drift

- **Duration parsing ≥4 implementations that disagree**:
  `config_generation/timeline.py:241` (single-unit only),
  `ai_config/validator.py:17` (mangles `"2.5h"`→25 s),
  `smoke_assertions.py:44` + `append_run_history.py:75` (compound), plus Rust
  `utils/duration.rs` (mis-parses `"5m30s"`→5 s) — while `humantime-serde` sits
  unused in Cargo.toml.
- **Stats helpers 5×** across `src/analysis/` with **three incompatible median
  conventions**; Gini implemented twice (`mod.rs:36` vs `metrics.rs:243`).
- **Four hand-rolled retry loops** in `agents/` with four backoff conventions,
  next to the shared `retry_with_backoff` helper (used twice in the package).
- **Three shell logging vocabularies** (`log_step/…`, `print_status/…`,
  `say/info/ok/…`) over one properly shared `colors.sh`.
- The "emit a Python agent wrapper script" pipeline exists 5–6× in the Rust
  orchestrator (`miner_distributor.rs`, `pure_scripts.rs`,
  `simulation_monitor.rs`, `emit_dns_server_host`, `agent_scripts.rs`), each
  differing by ~10 lines, each hardcoding `"1000000000"` bandwidth past the
  `DEFAULT_BANDWIDTH_BPS` constant that exists for exactly this.

### 2.3 Speculative fallback towers whose primary layers are provably dead

- Miner discovery (`agent_discovery.py:350`, `base_agent.py:707`) has 4 layers;
  layers 1–2 **cannot match**: registry types are `"autonomous_miner"` /
  `"regular_user"` (derived from class names), never `"miner"`; attributes are
  CLI strings (`"true"`) compared `== True`. Only layer 3 (`miners.json`,
  written by the Rust orchestrator) ever works. Nobody noticed because the
  tower "works".
- Registry handling for `wallets.json` / `block_controller.json`
  (`agent_discovery.py:173-192`) — **no producer exists anywhere in the repo**;
  vestige of a removed architecture (stale comment survives at
  `regular_user.py:218`).
- Defensive code that misfires: `run_sim.sh:1182` `total=$(echo "$all_dirs" |
  grep -c . || echo 0)` — `grep -c` prints `0` *and* exits 1 on no match, so the
  fallback appends a second `0` → `"0\n0"` → arithmetic syntax error → snapshot
  archiving fails. The safety fallback *causes* the failure. Five unreachable
  `[[ $? -eq 0 ]]` checks under `set -e` in `setup.sh` (544, 803, 910, 929,
  1022). Loop caps on already-terminating stem walks (100 in one copy, 50 in
  the other).

### 2.4 Fabricated rigor (most damning for a research tool)

- `src/analysis/time_window.rs:317-326`: hand-rolled Welch t-test whose small-df
  path is `standard_normal_cdf(t * 0.9) // Conservative adjustment` — an
  invented fudge factor backing every "* Statistically significant at p < 0.05"
  in upgrade reports.
- `src/analysis/tx_relay.rs:232-246`: "V2 fulfillment" =
  `requests_sent.min(total_tx_observations)` where the latter is all v1
  broadcasts network-wide → ratio ~always 100%; the fallback branch hardcodes
  `1.0 // Assume working if we have observations`.
- Invented scoring rubrics with zero rationale: spy confidence weights
  0.3/0.15/0.4 (`spy_node.rs:163-195`), privacy-score deductions 30/10/25/15
  (`dandelion.rs:389-483`), health verdict bands 90/70/50
  (`tx_relay.rs:263-382`) — all presented as authoritative "Score: 85/100".
- `report.rs:90-91`: every spy report unconditionally recommends "Consider
  implementing Dandelion++ or similar" — Monero *has* Dandelion++; this codebase
  analyzes it.

### 2.5 Aspirational surface never wired up

- `tx_analyzer.rs:441`: documented `--expected-outbound` flag parsed then
  destructured to `_`; library hardcodes 8.
- `tx_relay.rs:139`: `txs_in_blocks: 0, // Will be set by caller` — no caller
  ever sets it; serialized into every JSON report. `drops_protocol_violation`
  counts a reason string the parser never emits.
- `simulation_monitor/agent.py:1443-1446`: `--enable-alerts` is
  `action='store_true', default=True` — cannot be turned off; `enable_alerts`
  and `detailed_logging` are parsed, stored, never read.
- `miner_distributor/selection.py:49-54`: `"balance"`-based miner selection is
  advertised, validated, *tested* — and is a placeholder that selects randomly.
- `network_graph.rs:552-586`: DOT export emits a graph **with no edges**
  (comment admits it), while the CLI prints instructions to render it.

### 2.6 Fossil comments and session residue

- `setup.sh:188,276,362`: comments referencing "**Fix 6**" — a numbered item
  from a long-dead conversation plan.
- Doc comments describing superseded implementations: `as_manager.rs:213` claims
  10.x/192.168.x; code uses ARIN octets. `registry.rs:39` says "10.100.x.0";
  code uses `100.64.{}` (RFC 6598). "BFS" over a DFS
  (`network_resilience.rs:187`). "Exponential backoff with jitter"
  (`monero_rpc.py:146`) — no jitter.
- `regular_user.py:6`: "Currently a placeholder implementation that will be
  extended in future tasks" — atop 507 lines of finished implementation.
- `AUDIT.md` + `RELEASE_PLAN.md` frozen at 2026-05-12 at repo root, describing a
  codebase that no longer exists (AUDIT.md claims "no committed tests at all";
  flags files since deleted). AUDIT.md even brags AI tells "have largely been
  pruned".
- Commit `a7cb2b89`: *"the transaction finally sent"*.

### 2.7 Nothing is allowed to fail

- 5-deep IP fallback chain ends, on conflict, by logging an error **and
  returning the duplicate IP anyway** (`ip/allocator.rs:138-148`) → two Shadow
  hosts, one IP. `assign_ip`'s retry can format octets > 255 into YAML
  (`registry.rs:149`).
- `resolve_binary_path_for_shadow(...).unwrap_or_else(|_| monerod_path...)`
  (`user_agents.rs:655,710,837,908`): a failed custom/upgrade binary resolution
  silently runs default monerod — the opposite of what an upgrade test intends.
- `post_run_analysis.sh:19` launches an analyzer missing its `required=True`
  `--config` (argparse-errors every run), then prints "✅ All scripts have been
  launched."
- `run_sim_helpers.py:713-715`: `cmd_print_summary_kv` catches everything,
  prints `ERROR=`, **returns 0**.

The consequence of 2.7: the generator almost cannot fail, so misconfigurations
ship into 50-hour Shadow runs instead of erroring in 5 seconds at generation
time.

## 3. Per-subsystem highlights

Condensed; each reviewer's full findings (≈70 total) are preserved in the
review session transcript. The items promoted to the fix list are in §6.

### 3.1 Rust orchestrator core — C+

- **`orchestrator.rs:671-691`**: `_effective_seed_nodes` loop kept "for the
  informative print statement" calls `get_agent_ip(..., network_node_id=0)` for
  every miner *before* `process_user_agents` runs; all allocation paths persist
  to `agent_to_ip`, and later lookups return that forever → in GML+Dynamic mode
  every miner's IP comes from node 0's AS subnet (one /24 — which Monero's peer
  selection dedups by). A println decides IP topology.
- ~500 LOC of confirmed-dead `pub` items invisible to rustc (lib-crate `pub`
  suppresses dead_code lints): all of `utils/ip_utils.rs`,
  `generate_peer_connections`, `TopologyType`, `SubnetAllocation`, binary-path
  validators, `DaemonConfig` helpers. `ip_utils.rs`: dead since birth
  (authored 2025-11-02, never called).
- Two parallel "geographic IP realism" systems (`as_manager.rs:221-317` vs
  `registry.rs:100-135`) with overlapping octet spaces that can collide.
- Dead data plumbed three layers deep: `--stop-time` built from an
  environment key never inserted, defaulted to magic `"1800"`, pushed into
  args, then `retain`-ed away 40 lines later (`agent_scripts.rs:42-92`).
- Stringly-typed dispatch: 26 `.contains(` sites routing agents by substring of
  ID/script path.
- Space-joined unquoted args interpolated into bash wrappers while
  `shell_quote_args` exists and is used two lines away.
- 8.3k lines of `cargo fmt --check` drift; visible refactor indentation scar in
  `user_agents.rs:444-1062`.
- **Good**: golden-file output-equivalence tests (`tests/golden/`,
  `UPDATE_GOLDEN=1`); the turnover/reachability subsystem (deterministic
  FNV+splitmix64 seeding with regression-tested avalanche fix); deliberate
  quoting discipline in recent layers; near-zero `unwrap()` in production paths.

### 3.2 Rust analysis — C+

- Fabricated metrics (§2.4). Absolute-vs-sim-relative time confusion produces
  labels like "t=262972h"; `tx_analyzer.rs:1202` re-hardcodes `946684800.0`
  though `SHADOW_EPOCH` exists in `lib.rs:39`.
- Dead pub windowing API superseded by `upgrade_analysis/windows.rs` but left
  exported; `find_fluff_point` kept under `#[allow(dead_code)]`.
- O(agents) linear scan inside the hot loop of a function named
  `calculate_window_metrics_fast` (`metrics.rs:138-141`) — the reverse map it
  needs is built correctly one function away.
- 81 identical `.expect("write to String is infallible")` from one mechanical
  unwrap-sweep (commit `3bf8562a`).
- 10 `#[test]`s across ~6.6k LOC, all on trivia; spy inference, stem
  reconstruction, the t-test — untested.
- **Good**: the binary genuinely reuses the library (no parallel
  implementation); `upgrade_analysis/` pre-partitioning + rayon is documented,
  complexity-analyzed, seeded; the zstd/bincode parsed-log cache
  (mtime-invalidated, atomic tmp+rename) is production-grade; log regexes are
  anchored, precise, and handle three directory layouts + merged
  turnover-restart logs.

### 3.3 Python agents — C+

- **Registry race**: writer `_register_self` (`base_agent.py:683-721`) flocks
  the registry **file itself** and rewrites in place (`r+`/`truncate`); readers
  flock the **sidecar** `agent_registry.lock` (miner, DNS) or nothing
  (`read_shared_state` defaults `use_lock=False`; distributor, regular_user).
  Different lock objects = zero mutual exclusion → torn reads, masked by retry
  loops. The correct discipline (temp+atomic-rename) already exists in
  `write_shared_state`.
- Dead discovery layers (§2.3); ~200+ LOC of never-called methods
  (`_select_recipient`, `_send_transaction`, `get_daemon_address`, 9 uncalled
  RPC wrappers, `wait_for_height`/`wait_for_wallet_sync`).
- `simulation_monitor/agent.py` metric bugs hidden under 26 `except Exception`
  blankets: pool size read from the wrong key (always 0); per-cycle counting
  presented as per-transaction; `blocks_to_unlock` stored under `"height"`;
  `total_weight` computed then ignored.
- O(n²) I/O: full historical dataset rewritten every cycle; every user tx does
  a full read-modify-rewrite of `transactions.json` under one global lock.
- 4 layers of open-or-create wallet logic, including mutual recursion between
  `create_wallet` and `open_wallet`; error dispatch by string-matching monerod
  messages at 8+ sites.
- Two truthiness conventions (`parse_bool` accepting `1/yes/on` vs `== "true"`)
  → a config saying `is_miner: "1"` is a miner to some components only.
- **Good**: `BaseAgent` is a real abstraction (lifecycle, interruptible sleep,
  atomic `write_shared_state`, annotated broad-catch policy); determinism
  engineering is correct (per-agent sha256 seeds, sort-before-choice, knowing
  `SHADOW_EPOCH` conversion — a naive reviewer would false-flag it); post-mortem
  comments cite exact reverted commits and archived runs; the 87 tests are
  honest (no mock-theater), just narrow.

### 3.4 Python scripts/tooling — B−

- **Zero pytest coverage** for the entire ~16k LOC (`pyproject.toml` lists
  `scripts` in testpaths; every collected test is in `agents/`).
- `analyze_network_connectivity.py:436-461` **geolocates simulated IPs via live
  ipapi.co**, sequentially, 5 s timeout each, potentially 1000+ requests —
  and Shadow's 11.x addresses bypass the private-prefix guard. `MAX_RETRIES`
  defined, never used.
- `monero_verification.py`: 1041 lines serving 2 live importers; 125 lines of
  singleton/delegation ceremony; a parallel JSON-RPC client; IP substring
  matching (`"10.0.0.1" in peer_address` matches `10.0.0.100`) at 6 sites →
  false-positive connectivity verification; `_setup_file_logger` adds a new
  handler per instantiation and writes `monerosim_errors.log` to CWD (the
  stray files at repo root).
- Two rival YAML emitters in one pipeline (hand-rolled `yaml_emit.py` never
  escapes embedded single quotes → invalid YAML possible; `--from` path uses
  `yaml.dump`).
- 637-line `main()` in `generate_config.py`; 415-line `expand_scenario`;
  dual-import `try/except ImportError` boilerplate pasted 5×.
- Report round-trip: `final_report.json` → rendered `summary.txt` → regex-parsed
  *back* into dicts by two separate consumers.
- **Good**: Gen-2 discipline — `timing_constants.py` documents every constant
  with the failure run that derived it; `attic/` quarantine with honest README;
  stdlib-only regression gate (`smoke_assertions.py` + baselines + run-history
  CSV); the AI-config subsystem does not trust the LLM (structural + semantic
  validation, error feedback loops, `<think>`-strip, no `shell=True`, no
  hardcoded paths).

### 3.5 Shell + repo hygiene — B

- Seam bugs promoted to the fix list (§2.1, §2.3, §2.7).
- `check_shadow_status.sh` (214 lines): orphaned near-duplicate of
  `check_sim.sh` watching a `shadow.log` the pipeline deletes and grepping a
  completion marker nothing emits. `archive_simulation.sh`: legacy duplicate of
  run_sim.sh's built-in archiving with a divergent schema and hardcoded
  `~/scale_run_logs`.
- `prune_archives.sh:96` keys crash-detection to a magic `\.bash\.1028` Shadow
  process suffix — silently stops preserving crashed users when numbering
  shifts.
- Interactive prompts with no non-interactive escape (`run_sim.sh:601`
  disk-space confirm hangs unattended runs exactly when disk is tight).
- Hygiene: CHANGELOG stale (no v0.2.0 entry); `AUDIT.md`/`RELEASE_PLAN.md`
  frozen and misleading; 18 old config YAMLs tracked inside gitignored
  `archived_runs/`; `miner-0*|miner-1*|…|miner-9*` where `miner-[0-9]*` does it.
- **Good**: `set -euo pipefail` everywhere with a written justification at every
  deliberate `-e` omission; containment-checked `rm -rf` (readlink -f against
  project tree + /tmp); the setsid-detached ramdisk-cleanup watchdog registered
  before mount; stdin-draining before prompts; `smoke_test.sh`'s documented
  exit-code contract with baseline assertions firewalled from the verdict.

## 4. The generational arc (what changed across model generations)

There is a clear arc visible in `git log` and file dates:

1. **Gen-1 (2025-07 → 09)**: classic early-AI slop — facade classes, delegation
   wrappers, emoji logging, geolocation-of-simulated-IPs, speculative features.
   Much of it survives in `monero_verification.py`,
   `analyze_network_connectivity.py`, `analyze_success_criteria.py` (2.3k LOC),
   still wired into the live pipeline (one via a broken invocation).
2. **Cleanup passes (2026-01 → 05)**: real but *mechanical* — commits literally
   titled "Remove AI slop" pruned emoji and narration; one unwrap-sweep left 81
   identical `.expect()` strings. Cosmetics improved; structure didn't.
3. **Gen-2 (2026)**: markedly better engineering (turnover subsystem,
   `upgrade_analysis` performance work, calibration constants with provenance,
   golden tests) — but introduced the modern failure mode: **integration debt at
   session seams**. Newer models write locally excellent code and still don't
   read their neighbors, don't delete superseded layers, and don't run the
   wizard they just edited.

Every reviewer independently converged on the same sentence: *each feature
works; the layers were accreted by sessions that didn't read each other.*

## 5. Meta-observations

- The bugs concentrate exactly where tests stop. The golden-file harness and the
  87 agent tests protect what they cover; everything found in §6 lives outside
  that perimeter.
- The repo already knows some of this about itself:
  `docs/ANALYSIS_TOOLS.md` opens with "This analysis tool was LLM-generated and
  has 0% human-verified validity" — admirable candor that §2.4 confirms was
  warranted.
- A softer tell: confident comments justifying models later disproven — the
  capacity model behind `calibrate.py`'s guardrails was empirically refuted
  (2026-06-10, see `docs/20260605_max_connections_per_ip_bug.md` follow-ups),
  yet the code retains its assured narrative. Comments look equally
  authoritative whether or not the claim survived contact with data.

## 6. Fix list and status

Statuses updated as fixes land. "Verified" = independently re-confirmed in this
repo before the fix, not just asserted by a reviewer.

### P0 — result integrity

| # | Where | Bug | Status |
|---|---|---|---|
| 1 | `src/orchestrator.rs:671-691` | Discarded print-loop side effect pins all miner IPs to node 0's /24 | **FIXED** `009c3041` (golden diff verified IP-only; miner-002..005 move to true GML subnets) |
| 2 | `agents/base_agent.py:683-721` + readers | agent_registry.json torn-read race (writer/readers lock different objects; non-atomic rewrite) | **FIXED** `cf5decb3` (sidecar lock + atomic rename; stress: 1 torn read before, 0 after over ~850k reads) |
| 3 | `src/analysis/time_window.rs:317-326` | t-test `t*0.9` fudge behind every "statistically significant" claim | **FIXED** `b9feae12` (exact Student's t via regularized incomplete beta; unit tests pin known values) |
| 4 | `src/analysis/tx_relay.rs:232-246` | Fulfillment metric structurally ~100%, fallback hardcodes 1.0 | **FIXED** `b9feae12` (deleted — real pairing not derivable from logs; phantom `txs_in_blocks`/`drops_protocol_violation` also removed) |
| 5 | `scripts/configure_upgrade.py:305` | Wizard emits N+5 hosts for "N agents" after `--agents` semantics change | **FIXED** `97ec143e` (verified 30→30) |

### P1 — broken wiring

| # | Where | Bug | Status |
|---|---|---|---|
| 6 | `start_here.sh:707` (+700,709) | Passes `--full-monero` (rejected by setup.sh); `--clean` description wrong | **FIXED** `8b803afe` |
| 7 | `scripts/post_run_analysis.sh:19` | Analyzer launched without required `--config`; fails every run behind a ✅ | **FIXED** `cbc46155` (config wired through run_sim.sh; jobs now waited on, exit code honest) |
| 8 | `run_sim.sh:1182` | `\|\| echo 0` yields `"0\n0"` → arithmetic error → snapshot archiving fails | **FIXED** `cbc46155` |
| 9 | `update.sh:187,213` | Missing RAM-capped BUILD_JOBS (OOM regression); un-pins setup.sh's ref pin | **FIXED** `8b803afe` |
| 10 | `scripts/analyze_network_connectivity.py:436-461` | Live ipapi.co geolocation of simulated IPs | **FIXED** `cbc46155` (static placeholder; requests dependency dropped) |
| 11 | `agents/simulation_monitor/agent.py:1159,878,670,621` | Metrics silently garbage (wrong key → always 0; cycles counted as txs) | **FIXED** `6c52e682` (verified vs real archived final_report.json; consumer keys audited, baselines unaffected; +1 pin test) |

Baseline repair note: the golden output-equivalence tests had been red since
June — `d21f971b` added the max-connections-per-ip floor without regenerating
goldens. Repaired in `d9d30b3c` (diff verified as exactly the 17 injected flag
lines) *before* any fix landed, so every fix above was validated against a
green baseline. Post-fix suite: cargo 78 passed / 0 failed, pytest 88 passed
(87 baseline + 1 new pin), `bash -n` clean on all touched scripts.

### P2 — debt (not this pass; tracked)

Dead code deletion (~500 LOC Rust pub items, ~200 LOC agents methods, dead
discovery layers, orphaned `check_shadow_status.sh`/`archive_simulation.sh`);
consolidate duration parsers / stats helpers / retry loops; retire
`AUDIT.md`/`RELEASE_PLAN.md` to `attic/`; CHANGELOG v0.2.0 entry; `cargo fmt`
(as its own commit); IP-fallback chains → hard errors; binary-resolution
fallback → hard error; unify truthiness parsing.

### P3 — structural

Smoke tests for `scripts/` (duration parsing, config generation round-trip);
split the 600-line `main()`s; single YAML emitter; report consumers read
`final_report.json` directly instead of regex-parsing `summary.txt`.

## 7. Regression protocol used for the fixes

1. Baseline before any change: `cargo test` (incl. golden output-equivalence
   tests) + `pytest -q` (87 tests) recorded.
2. Every fix re-verified against the live code before editing (not trusted from
   the review alone).
3. After each fix: full `cargo test` + `pytest -q`. For orchestrator changes,
   the golden diff must show **only** the intended change (e.g. miner IPs
   moving off node-0's subnet) before goldens are regenerated with
   `UPDATE_GOLDEN=1`.
4. `bash -n` on every edited shell script; edited Python imported/exercised
   directly.
