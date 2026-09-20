# Run index — design

**Date:** 2026-09-20
**Status:** design approved, not yet planned or implemented
**Scope:** increment 1 of a larger "chat with the codebase/software" helper. This
spec covers the run index and its query CLI only.

## 1. Problem

Every fact about a past simulation run exists on disk, and none of it is
queryable across runs. A run directory holds its config, its Shadow log, its
monitor report and its memory samples — but answering "which run reproduced the
paper?" or "has any 2,000-host run finished clean?" means hand-walking four
locations in four formats and reconstructing the answer from memory.

That reconstruction is unreliable in practice. In a single working session on
2026-09-19/20 it produced three wrong answers:

1. The wrong eclipse config was identified as the paper reproduction, because a
   stale write-up was treated as an index of the work.
2. A phase-3 selfish-mining run was declared "no longer on disk" when it is
   present in the backup volume — a claim that reached `main` in
   `docs/20260912_selfish_mining_results.md`.
3. Raw daemon logs were said to exist "solely on this box", missing a 49 TB
   backup volume holding 153 run directories.

Each failure has the same shape: scattered state, reconstructed by hand, stopping
at the first plausible answer. An index makes the answer a query instead of a
recollection.

## 2. Non-goals

Out of scope for this spec; each may get its own later:

- **Capability Q&A** over docs ("what does `--sim-relay-alt-blocks` do?"). A
  different retrieval corpus. The CLI states the boundary rather than guessing.
- **Feature-request routing.** Depends on capability Q&A; without it a model
  that hallucinates capabilities files nonsense.
- **Fine-tuning a model.** Considered and rejected: repo facts change every
  commit, a fine-tune is a frozen snapshot that cannot be grepped or corrected,
  and it cannot cite. Retrieval supplies facts; a fine-tune would only ever be
  justified later for tool-call reliability, and only with real usage traces.
- **An MCP wrapper.** A clean `--json` contract already serves any agent. Add a
  shim only if something demands it.
- **Writing to run data.** The index is strictly read-only over run artifacts;
  `scan` never writes to the volume it walks.

## 3. Sources and cutoff

**Ordered, labelled roots** in local config. First root holding a given run ID
wins, so a complete local run directory beats a trimmed archive copy of the same
run. Defaults:

| label | root | tier |
|---|---|---|
| live | `archived_runs/` | full run dirs |
| curated | `~/basement_monerosim/` | reduced, often gzipped |
| cold | `/mnt/remote_spinny/monerosim_backups/` | full run dirs, historical |
| metrics | `analysis/eclipse/results/` | metrics-only, no logs |

**Version cutoff, configurable, default 2026-05-13** (the v0.1.0 release date,
"Pancake Plethora", the first public beta). Runs older than the cutoff are
skipped. This must be a config value rather than a hardcoded date: the 23
pre-cutoff runs in the backup do have real configs, they are simply from a period
not worth supporting today.

A cutoff is genuinely required. The obvious alternative — "index any directory
carrying an `input_config.yaml`" — was tested against the corpus and does not
separate the eras: all 23 pre-v0.1.0 run directories also have one.

**Corpus reality.** Of the 153 run directories on the backup volume, 130 fall on
or after the cutoff (2026-06-05 → 2026-09-13). Artifact coverage across those
130:

```
input_config.yaml    130/130    the exact config that ran
monerosim.log        130/130
shadow_run.log       129/130    wall clock, processes-failed
memory_samples.csv   129/130    RSS over time
monitoring/          115/130    final_report.json
summary.txt          115/130
```

This supports **one extractor, not a tiered era-sniffer**. `monitoring/` and
`summary.txt` are nullable fields at 88% coverage, not a separate era.

## 4. Record schema

One JSON object per run in `~/.monerosim/run_index.jsonl`.

**Identity** — `run_id`, `timestamp`, `run_name`, `source_root`,
`config_sha256`, `config_path_hint` (the source config path if recoverable from
`monerosim.log`, else null). The digest groups "same config, different
run", which is how an A/B pair is found without diffing two 398 KB files.

**Intent** — `description`: the leading comment block of `input_config.yaml`.
These headers state what the experiment tests and why; capturing them makes runs
findable by meaning rather than filename.

**Shape** — `stop_time`, `agent_count`, `gml_path`, and notable knobs lifted from
the config: `mining_mode`, `reachable_fraction`, `node_implementations`, and the
distinct set of `daemon:` values used (which answers "which runs used a patched
binary?").

**Execution**, parsed from the Shadow progress line and terminal marker:

```
Progress: 100% — simulated: 05:58:15.355/06:00:00, realtime: 04:22:00, processes failed: 0
** Shadow completed successfully
```

→ `sim_achieved`, `sim_target`, `wall_clock`, `processes_failed`, `completed`.

**Outcome is read from `summary.txt`, not `monitoring/final_report.json`.**
Both carry the same fields, but `final_report.json` is ~43 MB (it embeds the full
`historical_data` time series) while `summary.txt` is ~0.1 MB — a 400x I/O
difference across 130 runs on a spinning NFS volume. `summary.txt` also carries
`Exit code` and `Wall time` directly. Fall back to `final_report.json` only when
`summary.txt` is absent.

**Completion is never read from `final_report.json`'s `status` field.** It
reports `running` on runs that finished cleanly; the monitor's last write never
flips it.

**Cost** — `peak_total_rss_mb`, `min_system_free_mb` from `memory_samples.csv`,
plus derived `sim_wall_ratio` and `rss_per_agent_mb`. The last is the per-relay
memory figure currently quoted by hand in config comments; computing it answers
"can my machine run this?" directly.

**Outcome** — `exit_code`, the raw `success_criteria` dict stored as-is, and a
derived `tx_workload` boolean (true when the run created any transactions), with
**no single pass/fail field**.

This is settled by measurement, not principle. Across the 115 post-cutoff runs
carrying a `summary.txt`, the two signals disagree in **both** directions:

- **36 of 111 clean-exit runs report a failed criterion.** Every one is the
  transaction pair, and every one created exactly zero transactions — configs
  with no transaction workload, where those criteria are meaningless. There are
  zero cases of transactions being created and the criteria still failing.
- **3 of the 4 non-zero-exit runs report ALL CHECKS PASSED**, including
  `20260911_025410_native_daa_300_10h_r2`, the published 300-node DAA gate. A
  late wallet crash takes the exit code without invalidating the simulation.

`tx_workload` lets a query ignore the transaction criteria where they do not
apply, so the tool can answer "passed every *applicable* criterion" instead of
libelling a third of the corpus. A run with no transaction workload reports
`transactions_created_broadcast: false` and prints "SOME CHECKS FAILED" while
being a perfectly good run; the 2026-09-18 phase-4 selfish-mining run is exactly
this case. "Ran to completion with zero process failures" and "passed every
success criterion" are different questions, and collapsing them produces
authoritative-looking wrong answers. The query layer composes; the record does
not editorialise.

**Provenance** — `schema_version`, `extractor_version`, and `missing: [...]` naming fields that
could not be determined and why. The 15 of 130 runs without `monitoring/` carry
`missing: ["success_criteria", "total_nodes"]` rather than silent nulls, so a
query can report "6 runs match; 2 have no wall clock" instead of dropping them.
A `schema_version` bump invalidates the index and forces a full rebuild; records
are cheap to regenerate and must never be migrated in place, since a
half-migrated index is precisely the silently-wrong artifact this design exists
to prevent.

## 5. CLI surface

Python, under `scripts/runs/`, matching the existing `scripts/ai_config/`
package. Invoked as `python -m scripts.runs <subcommand>`. The Rust binary does
not grow a reporting surface.

```
python -m scripts.runs index              # build/refresh the local index
python -m scripts.runs scan <path>        # discover run data on a volume
python -m scripts.runs ls [filters]       # filter and list
python -m scripts.runs show <run_id>      # one full record
python -m scripts.runs find <text>        # search descriptions + config bodies
```

Filters are predicates over schema fields: `--after`, `--config-sha`,
`--daemon`, `--completed`, `--min-agents`, `--failed-processes`. Every
subcommand accepts `--json`.

**`scan`** walks a path looking for run-directory signatures — a
`YYYYMMDD_HHMMSS_<name>` directory name carrying any known artifact — and reports
counts and date ranges with a `sources` entry to paste into config. Read-only,
depth-limited, and skips `shadow.data/` so it never crawls hundreds of GB of
LMDB.

**Staleness is surfaced, never hidden.** The index records each source root and
the run count seen there. `ls` compares against disk and prints
`index is N runs behind <root> — run 'python -m scripts.runs index'` rather than
answering from a stale snapshot. Given that the premise of this work is "stale
artifacts cause wrong answers", the index must not pretend.

## 6. Model layer (increment 4)

The model translates English into a **filter expression**, never into an answer.
It emits a query; deterministic code runs it; records come back with `run_id`s
the user can independently `show`. The model may select and rank. It may not
produce field values, so it cannot invent a CTR or a wall-clock figure.

This constraint is what makes a small local model adequate, and it is the
structural fix for fluent-but-unsourced answers. Every answer traces to a record.

Reuses the `scripts/ai_config` provider pattern (OpenAI-compatible `base_url` +
`api_key` + `model`), so it works against a local ollama, a hosted V100 endpoint,
or MoneroWorld with no new plumbing. No GPU is required for increments 1–3, and
increment 4 requires only an endpoint, not a specific one.

## 7. Increments

1. **Extractor + index + `ls`/`show`/`find`.** Useful with no model installed.
2. **`scan`.** Volume discovery.
3. **Run-time capture.** `run_sim.sh` writes `run_card.json` at archive time; the
   extractor becomes the fallback for history. **Deferred** — it touches a hot
   script with a long multi-day run currently depending on it. Increments 1–2
   only read, so they are safe to land meanwhile.
4. **Model layer.** NL → filter.

## 8. Testing

Follows the repo's existing golden pattern: trimmed fixture run directories under
`tests/fixtures/`, golden extracted records under `tests/golden/`, mirroring
`tests/golden/selfish.yaml`. Fixtures must pin the awkward real formats, not just
the happy path:

- a run whose `final_report.json` says `status: "running"` after finishing
- a clean-exit run whose transaction criteria FAIL with zero transactions created
- a non-zero-exit run reporting ALL CHECKS PASSED (the DAA-gate case)
- a run with no `monitoring/` directory (15 of 130 in the corpus)
- a metrics-only run with no Shadow log at all
- a gzipped basement-tier run
- a pre-cutoff run that must be skipped

## 9. Deferred and follow-up

- Correct `docs/20260912_selfish_mining_results.md`, which states the phase-3 run
  directory is no longer on disk. It is on the backup volume, so the phase-3 vs
  phase-4 comparison described there as impossible is in fact testable.
- Increment 3 (`run_sim.sh` capture) once the box is free.
- Capability Q&A and feature-request routing, as separate specs.
