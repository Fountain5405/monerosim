# Contributing to monerosim

Thanks for the interest. This guide describes how to get a working dev
environment, run the test tiers, and submit changes.

## Project status

Monerosim is in 0.x public beta. The codebase is mid-cleanup; some
rough edges (as of 2026-05-12, since moved to attic/) are documented in
[AUDIT.md](attic/AUDIT_20260512.md). Treat it as historical context, not
a current TODO list — see `docs/20260711_code_quality_review.md` for a
more recent pass.

## Dev environment

The same `setup.sh` that installs monerosim also gets the dev
environment running:

```bash
git clone https://github.com/Fountain5405/monerosim.git
cd monerosim
./setup.sh                    # ~30-60 min: builds Shadow, monerod, monero-wallet-rpc
pip install -e .[dev]         # Python dev deps (pytest, black, mypy, isort, flake8)
```

After that, `cargo build --release` builds the Rust orchestrator and
`pytest` runs the Python test suite.

## Test tiers

Three tiers, used in this order from fastest to slowest:

### Tier 0 — Rust orchestrator goldens (per-commit, <1s)

```bash
cargo test
```

`tests/orchestrator_smoke.rs` and `tests/orchestrator_quickstart.rs`
byte-diff the orchestrator's emitted YAML against committed goldens in
`tests/golden/`, with path normalization (`/tmp/...` → `TMPDIR/`,
`$CWD` → `REPO_ROOT`, `$HOME` → `HOME`).

If you intentionally change orchestrator output, refresh the goldens:

```bash
UPDATE_GOLDEN=1 cargo test
```

Then inspect the diff and commit the new goldens alongside the source
change.

### Tier 1 — Python unit tests (per-commit, seconds)

```bash
pytest agents/ scripts/ tests/
```

~86 assertions across 9 agent modules — parser shape, RPC payloads,
DNS resolution, registry caching, helpers. `conftest.py` at repo root
sets the path.

### Tier 2 — Shadow smoke test (pre-release, ~15 min wall)

```bash
./scripts/smoke_test.sh                # quickstart, ~15 min wall
./scripts/smoke_test.sh refactor_gate  # any scenario with a YAML + baseline
```

Runs a real end-to-end Shadow simulation and checks the resulting
archive against a strict baseline in `tests/baselines/`. Exit code 0
= all assertions PASS; non-zero = at least one assertion failed (see
the script for the exit-code map). Adding a new scenario means adding
both the scenario YAML in `test_configs/` and the matching
`tests/baselines/<scenario>_metrics.json`.

Run Tier 2 before tagging a release and after any non-trivial agent
or orchestrator change.

## Code style

- **Rust:** `cargo fmt` and `cargo clippy` clean. New lints can be
  added to `[lints.clippy]` in `Cargo.toml` once that section exists.
- **Python:** PEP 8 via `black` (line length 100, see
  `pyproject.toml`). `isort`, `flake8`, and `mypy` are configured but
  not strict-enforced yet.

Don't write multi-paragraph docstrings or comment-block essays. The
working assumption is that well-named identifiers and a focused
function body explain what the code does; comments should only call
out non-obvious *why* — a hidden constraint, a workaround, a
surprising invariant. See the existing source files for the tone.

## Commit style

- Short imperative subject line. Prefer scope-prefixed: `setup.sh:`,
  `run_sim.sh:`, `ai_config:`, `scenario_parser:`, `docs:`.
- Body explains *why* the change exists. Reference incident commits,
  related audit items, or scenario YAMLs that triggered the fix.
- Group related changes into one commit; don't fragment a single
  logical edit across five tiny commits.

Example:

```
ai_config: harden large-group stagger defaults

The small open-weight Qwen3 model used in practice kept
anchoring on the small 10-relay `5s` example and applying it to
800-relay groups. The prompt now has an
explicit term-mapping for "batched bootstrap" and a final
pre-output checklist. The validator also flags any 50+ range
group with a non-`auto` stagger so failures are caught at
generation time even if the model misbehaves.
```

## Pull-request flow

1. Fork on GitHub and clone locally.
2. Create a feature branch: `git checkout -b feature/short-description`.
3. Make the change. Keep the diff focused; refactors should land
   separately from feature work.
4. Run the relevant test tiers (at least Tier 0 + Tier 1 for any
   code change; add Tier 2 for orchestrator/agent changes).
5. Push your branch and open a PR against `main`.
6. PRs should have a one-paragraph description of *what* changed and
   *why*, plus a test plan describing how you verified it.

## Reporting bugs

Use the [GitHub issue tracker](https://github.com/Fountain5405/monerosim/issues).
Please include:

- The version / commit hash.
- The scenario YAML you ran (or a minimal reduction of it).
- The archive directory name (`archived_runs/<TS>_<name>/`) and the
  relevant log/log-extract.
- What you expected vs. what happened.

For security issues see [SECURITY.md](SECURITY.md) instead.

## License

By contributing, you agree your contribution will be licensed under
the BSD 3-Clause License (see [LICENSE](LICENSE)).
