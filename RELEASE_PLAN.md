# Monerosim Release Readiness Plan

Audit and plan to prepare the project for its first public beta release.
This document is the result of a fresh-eyes audit of the working tree; it
draws on `AUDIT.md` (codebase audit, May 2026) and `PORTABILITY.md`
(cross-distro audit, May 2026) for context on already-investigated areas
but does not treat them as authoritative for release readiness.

---

## 1. Readiness summary

**Status: CLOSE, but not releasable today.** Roughly one focused day of
work stands between the current `HEAD` and a defensible first public beta.

The fundamentals are in place: BSD-3-Clause `LICENSE`, real `README.md`,
`QUICKSTART.md`, `CHANGELOG.md`, a working install path on a documented
matrix of distros, a committed test suite (3 tiers, ~86 Python +
integration Rust tests), and no secrets or credentials in the working
tree. Recent portability and audit-driven cleanup waves (commit history
since `ecc8f7ee`) closed most of the obvious gaps.

What's left before tagging:

1. **One real-user blocker in `scripts/scaling_sweep.sh`** — hardcoded
   `/home/lever65/.monerosim/bin/...` paths in `pkill` patterns
   (lines 169–171). The script will silently no-op on anyone else's
   machine. Trivial fix.
2. **The entire `examples/` folder is dead weight.** Three configs
   from January 2026 reference non-existent topology files and use
   the old `user_agents:` schema; the bundled topology generator
   script is a stale wrapper that nothing else calls. Production flow
   already lives in `gml_processing/` (generator + pre-built GMLs)
   and `test_configs/` (working configs). Delete the folder and
   re-point the three docs that reference it.
3. **Author/maintainer metadata is placeholder text** —
   `"MoneroSim Developer" / "noreply@example.com"` in both `Cargo.toml`
   and `pyproject.toml`. Replace before tagging if you want commits to
   point at a real human (or use a project alias deliberately).
4. **No user-facing beta signal in the README** — `pyproject.toml` has
   the `Development Status :: 4 - Beta` classifier, but the README that
   actual users read has zero "beta" / "alpha" / "experimental"
   mentions. The "we may break things" expectation isn't being set.
5. **No CI** — `.github/` directory doesn't exist at all. Tests are
   committed and runnable but nothing automatically enforces that they
   stay green. Not a blocker for a quiet first beta, but it's the
   single biggest piece of release polish you can ship.

Everything else (CONTRIBUTING/SECURITY/CODE_OF_CONDUCT, expanded docs,
SPDX headers, lint enforcement) is either polish or can be drawn from
the limitations list and shipped with explicit "known gaps" framing.

---

## 2. Findings

Findings are grouped by audit category. For each, I give location,
issue, severity, effort, and a suggested fix. I've omitted items where
the audit confirmed something was already in good shape.

### 2.1 Project identity & metadata

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| ID-1 | `pyproject.toml:13`, `Cargo.toml:8` | Author is placeholder `"MoneroSim Developer" / "noreply@example.com"`. Git committer is `Fountain5405 <Fountain5405@keepd.com>`. | **blocker** | trivial |
| ID-2 | `Cargo.toml:7` vs `pyproject.toml:8` | Descriptions are inconsistent: Rust says *"Configuration utility for Monero network simulations in Shadow"*, Python says *"Configuration generator and agent framework for Monero network simulations in Shadow"*. Pick one. | important | trivial |
| ID-3 | `Cargo.toml` (missing field), `pyproject.toml:57–61` | Cargo.toml has no `repository`, `homepage`, or `documentation` URLs. Python manifest has them. Add to `[package]`. | important | trivial |
| ID-4 | `Cargo.toml` (missing field) | No `keywords` or `categories` declared for Rust crate. Discoverability on crates.io / search. | nice-to-have | trivial |
| ID-5 | `README.md`, `QUICKSTART.md` | Neither file mentions the current version or release status — readers can't tell from the docs alone what state the project is in. (`pyproject.toml` classifier says "Beta" but it's invisible to GitHub readers.) | important | trivial |

**Suggested fixes**: Replace placeholder author with `Fountain5405 <…>`
or chosen project alias (consistent across both manifests). Pick one
description and copy it. Add `repository`/`homepage`/`documentation` to
`Cargo.toml`. Add a one-line version + status banner to the top of
`README.md`.

### 2.2 License & legal

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| LIC-1 | `LICENSE:3` | Copyright line reads `"Copyright (c) 2026, The Monero Project"`. The repo is not under the Monero Project's GitHub org. If this is intentional (donation of code, attribution choice), fine; otherwise the copyright holder line should match the actual rights holder. **Open question — see §7.** | important | trivial |
| LIC-2 | All `.rs` and `.py` source files | No SPDX-License-Identifier headers. Optional under BSD-3-Clause but standard practice. | nice-to-have | small |
| LIC-3 | Missing | No `NOTICES.md` / `THIRD_PARTY_LICENSES.md` attributing Rust crate and Python package licenses. Monero binaries themselves are loaded at runtime, not bundled, so the redistribution surface is small — but it's worth a one-liner pointing at `Cargo.lock` / `requirements.txt` for downstream attribution. | nice-to-have | small |

### 2.3 Documentation

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| DOC-1 | `examples/` (entire folder) | Folder is dead: three configs (last content-touched 2026-01-08) reference non-existent topology files (`topology_large_2000.gml`, `topology_5k.gml`, `topology_1k.gml`); use the old `user_agents:`-list-with-`count:` schema rather than the per-agent layout used by `test_configs/` and the current `monerosim` binary; the bundled `generate_caida_topology.sh` is a stale wrapper around `gml_processing/create_caida_connected_with_loops.py` that nothing else calls and writes outputs to the wrong folder. **Decision: delete `examples/` outright.** Production flow lives in `gml_processing/` (generator + pre-built GMLs) and `test_configs/` (working configs). | **blocker** | small |
| DOC-2 | `README.md:91`, `QUICKSTART.md:164`, `docs/NETWORK_SCALING_GUIDE.md:435–444` | Three doc references point at the (about-to-be-deleted) `examples/` folder; `NETWORK_SCALING_GUIDE.md:439` already cites the wrong filename (`generate_topology.sh` vs actual `generate_caida_topology.sh`), confirming it's stale. Re-point each to `test_configs/` and `gml_processing/`. | **blocker** | trivial |
| DOC-3 | `scripts/generate_config.py` (40+ flags) | Many flags (`--relay-nodes`, `--batched-bootstrap`, `--upgrade-binary-v1/v2`, `--upgrade-order`, `--steady-state-duration`, `--post-upgrade-duration`, `--close-to-deterministic`, etc.) are present in the CLI but not described in `docs/CONFIGURATION.md` or `docs/AI_CONFIG_GENERATOR.md`. | important | medium |
| DOC-4 | `src/config/agent_config.rs:167–193` | Agent schema fields `daemon_phases`, `wallet_phases`, `daemon_env`, `wallet_env`, `attributes` are described inconsistently across `docs/CONFIGURATION.md`. Phase semantics are only fully explained inside `docs/SCENARIO_FORMAT.md`. | important | medium |
| DOC-5 | `README.md:222–231` ("Distros" section) | EL9-unsupported note is in `QUICKSTART.md:5` and `PORTABILITY.md` but missing from `README.md`'s distribution coverage. | important | trivial |
| DOC-6 | `agents/base_agent.py:28`, `src/lib.rs:24,32` | Code reads `MONEROSIM_SHARED_DIR` and `MONEROSIM_DAEMON_DATA_DIR` env vars to override defaults, but no docs explain them. | nice-to-have | small |
| DOC-7 | `scripts/check_sim.sh` | No `--help` / `-h` flag handler; running `./scripts/check_sim.sh --help` errors. | nice-to-have | trivial |
| DOC-8 | `src/main.rs:47–56` (clap declarations) | `monerosim --help` is bare — single-line descriptions only. No `long_about` or examples. | nice-to-have | trivial |
| DOC-9 | `src/bin/tx_analyzer.rs` | Multiple docs describe `tx-analyzer` output as "LLM-generated, unverified" — that warning is invisible from `--help`. | nice-to-have | trivial |

### 2.4 Repository hygiene

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| HYG-1 | `scripts/scaling_sweep.sh:169–171` | `pkill -KILL -f "/home/lever65/.monerosim/bin/..."` — hardcoded dev path. Script will no-op for every other user. | **blocker** | trivial |
| HYG-2 | `.gitignore:46` | `install_*.sh` is in `.gitignore` (commented as "scripts that might contain sensitive data"). This is over-eager and will silently ignore any legit `install_*.sh` script a contributor adds. | nice-to-have | trivial |
| HYG-3 | `.gitignore` | No explicit patterns for `.env`, `*.pem`, `*.key`, `*.crt`, `*.p12`, `*.keystore`. Currently fine (none in tree) but defensive depth helps when contributors join. | nice-to-have | trivial |
| HYG-4 | Working tree | `AUDIT.md` is untracked at the moment of this audit. It's a useful artifact to keep (already referenced from `CHANGELOG.md`) — either commit it or add an explicit decision to leave it out. | nice-to-have | trivial |

**Confirmed clean** (no findings): secrets/credentials scan,
scratch/dev files, large binary blobs, commented-out code blocks,
debug `dbg!()` / `print("DEBUG")` leftovers, `main` as default
branch, well-formed `origin` remote.

### 2.5 Build, install, distribution

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| BUILD-1 | `pyproject.toml:31–36` | Python runtime deps use loose `>=` bounds with no `<` upper-bound. For a beta this is fine, but worth a decision: are you happy if a contributor's `pip install` pulls PyYAML 8.x next year and breaks startup? | important | small |
| BUILD-2 | `requirements.lock` (root) | Lockfile exists and is referenced from `scripts/requirements.txt` (per AUDIT.md F-DEP-1). Document the canonical pip flow in README: "use `pip install -r requirements.lock` for reproducible installs, or `pip install -e .` for development". | nice-to-have | small |
| BUILD-3 | `Cargo.toml` | No `[lints.clippy]` section. Recent commit `35dfc2f1` ("clear two deny-by-default clippy errors") shows clippy is run ad-hoc but not enforced. | nice-to-have | small |
| BUILD-4 | `pyproject.toml` (no `[project.scripts]`) | `agents/` and `scripts/` are declared as packages but no console entry points are defined. Users run `python scripts/generate_config.py` — this is fine, just be explicit about it in README ("monerosim is not installed as a CLI command; invoke via the bash wrappers or `python scripts/*.py`"). | nice-to-have | trivial |

**Confirmed working**: setup.sh has dnf/yum/pacman/zypper/apt-get
branches, EPEL+CRB auto-enable on RHEL family, memory-aware
parallelism, working Cargo build/install at
`~/.monerosim/bin/{monerod,monero-wallet-rpc,shadow}`. Package-name
fixes from `PORTABILITY.md` are merged.

### 2.6 Quality gates

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| QG-1 | Missing | No CI at all (`.github/`, `.gitlab-ci.yml`, etc. don't exist). Tier 0 (Rust integration), Tier 1 (Python pytest, 86 tests), and Tier 2 (smoke script) all exist and run locally, but no automation enforces them on push/PR. | important | medium |
| QG-2 | `README.md:309–322` | "Testing" section documents the three test tiers and how to run them. Excellent for human readers; nothing automates it. (Pair with QG-1.) | important — covered by QG-1 | n/a |
| QG-3 | Missing | No `.pre-commit-config.yaml`. Black, isort, mypy, clippy, rustfmt are all configured in `pyproject.toml`/by convention but nothing enforces them at commit time. | nice-to-have | small |
| QG-4 | `pyproject.toml:79` | `disallow_untyped_defs = false`. Permissive — fine for beta; if you ever flip it, do it incrementally. | nice-to-have | medium |
| QG-5 | Missing | No `rustfmt.toml`. Defaults are fine but worth a stub file declaring `edition = "2021"` to lock the formatter to your intent. | nice-to-have | trivial |

### 2.7 Configuration & runtime behavior

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| CFG-1 | `run_sim.sh:230` (and around the cleanup phase) | `rm -rf shadow.data shadow.log` runs unconditionally on each invocation. If the user passes a bad `--data-dir`, this risks data loss. Add a `--dry-run` flag or refuse to delete paths outside the project tree. | important | small |
| CFG-2 | `src/main.rs` | Error handling is `color_eyre`-based; messages are reasonable. Logging defaults to `info` and honours `RUST_LOG`. No findings. | — | — |
| CFG-3 | Config precedence | YAML file is the only input — no CLI overrides or env var precedence beyond the two `MONEROSIM_*` directory overrides. Document this so users don't go hunting for `--max-peers`-style flags. | nice-to-have | trivial |

### 2.8 Versioning & release artifacts

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| VER-1 | `Cargo.toml:3`, `pyproject.toml:7` | Both at `0.1.0`. Last git tag is `v0.0.2`. `CHANGELOG.md` has a substantial `## Unreleased` section ready. No version drift between manifests — good. | important (because the tag isn't there yet) | trivial |
| VER-2 | `CHANGELOG.md:1–48` | High-quality `## Unreleased` entry covering the audit-driven cleanup, three test tiers, and the portability work. Close to release-notes-ready. Re-section as `## [0.1.0] — YYYY-MM-DD` at tag time. | important | trivial |
| VER-3 | Missing | No `vX.Y.Z` tag matching the manifest version. Create when ready. | important | trivial |

### 2.9 Beta-specific signaling

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| BETA-1 | `README.md`, `QUICKSTART.md` | Zero occurrences of "beta", "alpha", "experimental". Users have no expectation-setting about API/config stability. | important | trivial |
| BETA-2 | Missing | No SECURITY.md. The project doesn't handle user credentials directly, but it does run untrusted Monero binaries, write to `/tmp`, manage RPC ports, and execute Python agents inside Shadow's process tree. Worth a short policy: "report security issues to <email>; no bug bounty; coordinated disclosure expected". | important | small |
| BETA-3 | Missing | No explicit stability statement. Decision needed: during 0.x, can breaking changes appear in any 0.x.y bump? Whatever you choose, state it in README. | important | trivial |
| BETA-4 | Missing | No "known limitations" section in `README.md` that users see before they install. (`PORTABILITY.md` covers distro-level limits, `AUDIT.md` covers code-level limits, but neither is the first thing a reader hits.) | important | small |
| BETA-5 | Missing | No public feedback channel beyond the GitHub repo. Issue tracker URL is in `pyproject.toml` but README doesn't explicitly say "open issues here, expect bug reports to be triaged within Nd". | nice-to-have | trivial |

### 2.10 Open-source readiness

| # | Location | Finding | Severity | Effort |
|---|----------|---------|----------|--------|
| OSS-1 | Missing | No `CONTRIBUTING.md`. README has a short `## Contributing` section (lines 323–331); fine for "we accept patches", thin for "here's how to test, here's the commit style, here's how to run the goldens". | important | small |
| OSS-2 | Missing | No `CODE_OF_CONDUCT.md`. Defer if no community is anticipated yet; add when the issue tracker starts seeing traffic. | nice-to-have | small |
| OSS-3 | Missing | No `.github/ISSUE_TEMPLATE/` or `.github/PULL_REQUEST_TEMPLATE.md`. Optional; pairs with the missing `.github/` directory. | nice-to-have | small |

---

## 3. Recommended version & naming

**Recommendation: `0.1.0`. Tag as `v0.1.0`. Use plain semver during the
0.x line; signal beta status in prose, not in the version string.**

Rationale:

- The manifests are already at `0.1.0`. Bumping them just to add a
  `-beta.1` suffix is churn for no real signal — `0.x.y` already
  conveys "pre-stable" to anyone reading the version field.
- The `Development Status :: 4 - Beta` classifier in `pyproject.toml`
  is the right place for the package-metadata signal. It's tooling-
  visible.
- Where the signal *is* missing is the README. Add an explicit "Beta
  status — APIs and config formats may change between 0.x versions"
  banner near the top of `README.md`. That, plus a "Known limitations"
  section, does more for user expectations than the version string
  ever could.
- For subsequent betas, increment the minor (`0.2.0`, `0.3.0`) for
  releases that ship breaking config or CLI changes, and the patch
  (`0.1.1`, `0.1.2`) for bug-fix-only releases. Move to `1.0.0` when
  you're ready to call the config schema and the YAML keys stable.

**Tag command (when ready):**
```bash
git tag -a v0.1.0 -m "monerosim 0.1.0 — first public beta"
git push origin v0.1.0
```

---

## 4. Remediation plan

Three waves. Each is independently shippable; pick highest-value items
within each wave first.

### Wave 1 — Release blockers (must fix before tagging)

**Target effort: 2–4 hours.**

1. **ID-1: Replace placeholder author metadata.** Update `Cargo.toml:8`
   and `pyproject.toml:13` to a real maintainer name + email (or a
   chosen project alias used consistently).
2. **HYG-1: Fix hardcoded `/home/lever65` in `scripts/scaling_sweep.sh`
   lines 169–171.** Use `${HOME}/.monerosim/bin/...`. Trivial.
3. **DOC-1 / DOC-2: Delete `examples/` and re-point doc references.**
   - `git rm -r examples/` (the three configs, the stale
     `generate_caida_topology.sh` wrapper, and `examples/README.md`).
   - `README.md:91` — replace `or check examples/ for more` with a
     pointer to `test_configs/` and to
     `docs/NETWORK_SCALING_GUIDE.md` for topology generation.
   - `QUICKSTART.md:164` — replace `Check [examples/](examples/) for
     more configuration examples` with a pointer to `test_configs/`.
   - `docs/NETWORK_SCALING_GUIDE.md:435–444` — rewrite the "See the
     `examples/` directory" section to point at `gml_processing/` for
     pre-built topologies and `test_configs/` for working configs.
     Drop the `generate_topology.sh` line (also wrong filename).
   - Sanity-check `AUDIT.md` references to `examples/` (lines 135,
     434, 443) — leave AUDIT.md as a historical artifact, just be
     aware those pointers go stale on delete.
4. **VER-1 / VER-2 / VER-3: Release-readiness for the tag itself.**
   Re-section the `CHANGELOG.md` `## Unreleased` block as
   `## [0.1.0] — <date>`. Verify versions in both manifests match.
   Create the annotated tag `v0.1.0`. **Do not push the tag until the
   Wave 1 checklist below is fully green.**

### Wave 2 — Release essentials (should fix before tagging or ship Wave 2 immediately after)

**Target effort: 1–2 days.**

5. **BETA-1 / BETA-3 / BETA-4: User-facing beta signal in `README.md`.**
   Add a banner near the top:
   > **Beta:** Monerosim is in active development. Config formats and
   > CLI behavior may change between 0.x.y versions. Production use is
   > discouraged; pin to a tagged release if you need stability.

   Add a "Known limitations" section near the end of `README.md`
   pointing at `PORTABILITY.md`, `AUDIT.md`, and the items in §6 of
   this plan.
6. **BETA-2: Add `SECURITY.md`** — minimum viable: "Report
   vulnerabilities by email to <addr>; no bounty; we will respond
   within N days; coordinated disclosure preferred."
7. **OSS-1: Add `CONTRIBUTING.md`** — minimum viable: "How to run the
   test tiers, what `UPDATE_GOLDEN=1 cargo test` does, how the
   `scripts/smoke_test.sh` flow works, commit-message style if any."
8. **QG-1: Minimum viable CI.** Create `.github/workflows/test.yml`
   that on push/PR runs (Ubuntu 22.04):
   - `cargo build --release`
   - `cargo test`
   - `cargo clippy -- -D warnings`
   - `pip install -e .[dev]` then `pytest agents/ scripts/ tests/`
   - `shellcheck` on top-level `.sh` scripts (optional)

   Keep the matrix to one OS for now; cross-distro testing is a
   separate effort.
9. **ID-5 / ID-2 / ID-3: Manifest tidying.** Pick one description and
   apply to both manifests. Add Cargo.toml `repository`, `homepage`,
   `documentation` URLs to match pyproject.toml. Show the version
   somewhere in README.
10. **DOC-5: Add EL9-unsupported note to README's distribution table**
    (it's already in QUICKSTART and PORTABILITY).
11. **LIC-1: Confirm or correct the LICENSE copyright line.** See
    §7 open question.
12. **CFG-1: Add a destructive-ops guard to `run_sim.sh`** —
    refuse to `rm -rf` a `--data-dir` that's outside the project
    tree, or require `--force` to delete.

### Wave 3 — Release polish (can land in 0.1.1, 0.2.0, or any later beta)

**Target effort: 2–4 days, parallelizable.**

13. **DOC-3: Document `generate_config.py` flags** — create
    `docs/CONFIG_GENERATOR_FLAGS.md` or expand
    `docs/AI_CONFIG_GENERATOR.md` with a flag-reference table.
14. **DOC-4: Expand `docs/CONFIGURATION.md` agent-schema section** —
    add tables for `daemon_phases`, `wallet_phases`, `daemon_env`,
    `wallet_env`, `attributes`.
15. **DOC-6: Document `MONEROSIM_*` env var overrides.**
16. **DOC-7 / DOC-8 / DOC-9: Help-text polish** — add `--help` to
    `scripts/check_sim.sh`; add `long_about` to `monerosim` clap
    declaration; add a "results are LLM-generated, unverified" warning
    to `tx-analyzer --help`.
17. **LIC-2: SPDX-License-Identifier headers** across source files.
18. **LIC-3: NOTICES.md or THIRD_PARTY_LICENSES.md.**
19. **OSS-2 / OSS-3: CODE_OF_CONDUCT.md, issue/PR templates.** Defer
    until traffic warrants.
20. **QG-3 / QG-5: pre-commit config, `rustfmt.toml`.**
21. **BUILD-1: Decide Python dep pinning strategy** — loose `>=`
    for compatibility vs `>=,<` for stability. Document the choice.
22. **BUILD-3: `[lints.clippy]` section in Cargo.toml.**
23. **HYG-2: Remove `install_*.sh` from `.gitignore`** (or narrow the
    pattern to a specific known filename).
24. **HYG-3: Add `.env`, `*.pem`, `*.key`, `*.crt` to `.gitignore`**
    for defensive depth.
25. **HYG-4: Decide AUDIT.md disposition** — commit it (with date in
    the filename if multiple audits accrue), or move it to
    `docs/audits/` and add a README explaining the audit cadence.

---

## 5. Beta release checklist

A concrete walk-through immediately before pushing the tag. Each item
is binary; check it off in order.

**Pre-flight (code & docs):**

- [ ] `git status` is clean (no uncommitted changes)
- [ ] `git log origin/main..HEAD` is empty (all commits pushed)
- [ ] Version `0.1.0` in `Cargo.toml`, `pyproject.toml` — verified
      identical
- [ ] Author/maintainer metadata is real (not `MoneroSim Developer`)
- [ ] `LICENSE` copyright line reflects the actual rights holder
- [ ] `CHANGELOG.md` has a `## [0.1.0] — <today>` section (or
      `## Unreleased` renamed to that)
- [ ] README opens with a beta-status banner
- [ ] README has a "Known limitations" section
- [ ] `examples/` folder deleted; `README.md`, `QUICKSTART.md`, and `docs/NETWORK_SCALING_GUIDE.md` no longer reference it
- [ ] No `/home/<username>` strings in committed code:
      `grep -rn "/home/lever65" .` returns nothing inside tracked files
- [ ] No `dbg!(` / `println!("DEBUG"` / `print("DEBUG"` left in
      production paths

**Functional verification (fresh checkout):**

- [ ] On a fresh clone, `./setup.sh` completes without error on Ubuntu 22.04
- [ ] `./target/release/monerosim --version` reports `0.1.0`
- [ ] `./run_sim.sh --config test_configs/quickstart.yaml` completes
      successfully end-to-end and produces a `final_report.json`
- [ ] `cargo test` passes
- [ ] `pytest agents/ scripts/ tests/` passes
- [ ] `cargo clippy -- -D warnings` is clean

**Repo housekeeping:**

- [ ] No secrets in the working tree (rg for `API_KEY`, `BEGIN PRIVATE
      KEY`, `AKIA[0-9A-Z]{16}`, `ghp_`, `sk-` returns no hits)
- [ ] `.gitignore` covers expected artifacts (target/, venv/,
      shadow.data/, analysis_output/, __pycache__/)
- [ ] Default branch is `main`
- [ ] Repo URL in `pyproject.toml`/`Cargo.toml` matches `git remote -v`

**Tag & publish:**

- [ ] `git tag -a v0.1.0 -m "monerosim 0.1.0 — first public beta"`
- [ ] `git push origin v0.1.0`
- [ ] GitHub release created from the tag, body = the `[0.1.0]`
      CHANGELOG entry
- [ ] Open issues channel announced (README link is sufficient if no
      separate channel exists)

---

## 6. Known limitations to publish with the beta

These are issues that should be documented for users rather than fixed
before release. Drawn from `AUDIT.md`, `PORTABILITY.md`, and this
audit.

### Platform support

- **Linux only.** No macOS or Windows support; Shadow itself is
  Linux-only.
- **RHEL / Rocky / Alma 9 unsupported.** `setup.sh` auto-installs
  Python 3.11 and EPEL+CRB but `simulation_monitor` fails to write
  `final_report.json` on EL9, aborting Shadow at ~87% of sim time. Use
  EL10 or later. (Per `PORTABILITY.md` §5.)
- **Alpine / musl unsupported.** Out of scope; uses glibc-only
  syscall surface. (Per `PORTABILITY.md`.)
- **Supported targets:** Ubuntu 22.04+, Debian 12+, Fedora 38+, RHEL
  10+ / Rocky 10+ / Alma 10+ (with EPEL), Arch Linux, openSUSE Leap 16+.

### Functional caveats

- **Resource appetite.** 8 GB RAM is the floor for the quickstart;
  16 GB is the floor for any real work. See `docs/PERFORMANCE_AND_SCALE.md`
  for the RAM-vs-agent-count table. Shadow runs slower than real time
  by a factor that grows with agent count.
- **No deterministic guarantees at high agent counts.** Determinism is
  asserted for small simulations but has not been validated at 1000+
  agents.
- **`tx-analyzer` output is LLM-generated and unverified.** The Rust
  binary at `target/release/tx-analyzer` produces transaction-routing
  analysis whose correctness has not been independently audited. Treat
  outputs as exploratory, not authoritative. (Per `docs/RUNNING_SIMULATIONS.md`.)
- **No CI in this beta.** Tests exist and pass locally (Tier 0/1/2 per
  `CHANGELOG.md`) but are not automatically enforced on every commit.
  Wave 2 of this plan addresses that.

### Code-quality caveats (from `AUDIT.md`, not blockers)

These are documented in `AUDIT.md` as identified-but-deferred work and
appear here so external readers know the codebase is mid-cleanup:

- **Defensive `.unwrap()` density.** ~179 `.unwrap()` calls in Rust;
  some are load-bearing in the analyzer where panic-on-bad-data is
  acceptable, but error messages may surface as panics rather than
  user-facing context in edge cases.
- **API stability.** Config schema (the YAML keys consumed by
  `monerosim --config`) and CLI flags are likely to change between
  0.x.y versions. No keys are frozen yet. Pin to a tagged release if
  you need stability.

### What's *not* a limitation (was at the start of the audit but isn't now)

- Tests *are* committed. The historic `.gitignore` rule that excluded
  `test_*.py` was removed in the May 7–8 audit-driven cleanup
  (`CHANGELOG.md`).
- `setup.sh` *does* support dnf, yum, pacman, zypper, and apt-get —
  not just apt-get.
- `agents/__init__.py` *does* exist.
- The duplicate Python `tx_analyzer.py` script from `AUDIT.md` F-DUP-1
  *has* been consolidated (verified: only `scripts/compare_determinism.py`
  remains of the eight orphan scripts).

---

## 7. Open questions

These need decisions from you before Wave 1 can fully close, or
they're meta-questions worth flagging.

1. **`LICENSE` copyright holder.** The current line is `"Copyright (c)
   2026, The Monero Project"`. Is this intentional (e.g. you intend to
   eventually donate the code, or the work was funded by the Monero
   Project), or is it boilerplate that should be replaced with your
   own name / handle / chosen project alias? This affects LIC-1 in §2.
2. **Author identity.** Resolved 2026-05-12: use
   `gingeropolous <gingeropolous@gmail.com>` for both
   `Cargo.toml` and `pyproject.toml`. Affects ID-1.
3. **CI provider.** GitHub Actions is the obvious choice given the
   repo is on GitHub. Any reason to prefer something else? Affects
   QG-1.
4. **Stability promise wording.** During 0.x, are breaking config/CLI
   changes allowed in any 0.x.y bump, or only on minor-version bumps?
   Affects BETA-3 and the README banner.
5. **Should `AUDIT.md` be committed?** It's a useful artifact and
   `CHANGELOG.md` already references its findings. Currently
   untracked. Affects HYG-4.

### Prior planning files encountered

These were consulted for context but not treated as authoritative for
release readiness:

- `AUDIT.md` — full codebase audit (May 2026). Cleanup waves 1–3 are
  already complete per `CHANGELOG.md`; the dead-code, file-bloat, and
  test-infrastructure findings are addressed. Surviving items
  (`.unwrap()` density, doc cleanup) are surfaced in §6 above as
  documented limitations.
- `PORTABILITY.md` — cross-distro audit (May 2026). Wave 1/2 fixes are
  merged. RHEL 9 / Alpine exclusions are surfaced in §6 above.
- `CHANGELOG.md` — the `## Unreleased` section is high-quality and
  should become `## [0.1.0]` at tag time.
- `README.md`, `QUICKSTART.md` — read for project framing; specific
  findings against them are in §2.

### Files deliberately skipped (per audit charter)

- `TODO/` (gitignored; per-author dev notes)
- `CLAUDE.md` (gitignored; AI assistant context)
- `.claude/` (gitignored; AI session artifacts)
- `docs/2026*.md` dated validation notes
- `docs/20260503_refactor_plan.md` (currently staged for deletion)
