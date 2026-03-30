# Harness (Phase 1)

This is the Phase 1 BioTaskBench harness implementation.

## Commands

```bash
benchmarkAgentBfx validate --tests-root tests
benchmarkAgentBfx validate --tests-root tests --allow-missing-expected
benchmarkAgentBfx run --suite biotaskbench --model claude-opus-4-6 --domain chip-seq
benchmarkAgentBfx run --suite biotaskbench --domain chip-seq --agent-cmd "python agent.py"
benchmarkAgentBfx run --suite all --model claude-opus-4-6
benchmarkAgentBfx run --suite biotaskbench --skills-path ~/.claude/skills/ --domain chip-seq
benchmarkAgentBfx run --suite bixbench --agent-cmd "python agent.py" --resume results/bixbench-run-20260329/run.json
benchmarkAgentBfx compare results/run-a/run.json results/run-b/run.json
benchmarkAgentBfx report results/run-a/run.json --output results/report.json
benchmarkAgentBfx audit-data --tests-root tests
benchmarkAgentBfx audit-flaky results/run-1/run.json results/run-2/run.json results/run-3/run.json --threshold 0.3
benchmarkAgentBfx adapter-status
./scripts/run_phase4_calibration.sh
BIO_SKILLS_PATH=~/.claude/skills ./scripts/run_phase5_baselines.sh
```

## BioAgent Bench Integration

BioAgent Bench (10 open-ended bioinformatics tasks) is fully integrated via the `--agent-cmd` execution path. The adapter downloads/symlinks data, prepares task.json (same format as BioTaskBench), and grades agent output deterministically against reference results.

### Setup

Pre-download reference results (required for grading):

```bash
cd external/bioagent-bench
uv run python src/dataset.py download --all --dest tasks/ --results
```

Optionally pre-download input data (otherwise agents download via URLs in task.json):

```bash
uv run python src/dataset.py download --all --dest tasks/
```

### Running

```bash
# Run all gradable BioAgent Bench tasks via Claude
benchmarkAgentBfx run --suite bioagent-bench \
  --agent-cmd "python $(pwd)/scripts/run_claude.py" \
  --model claude-sonnet-4-6 --effort high --output results/

# Run with skills (A/B testing)
benchmarkAgentBfx run --suite bioagent-bench \
  --agent-cmd "python $(pwd)/scripts/run_claude.py" \
  --skills-path /path/to/skills/ --output results/

# Run via Codex
benchmarkAgentBfx run --suite bioagent-bench \
  --agent-cmd "python $(pwd)/scripts/run_codex.py" \
  --model o3 --effort high --output results/

# Ingest pre-computed results (no agent execution)
BIOAGENT_BENCH_RESULTS_JSON=/path/to/results.json \
  benchmarkAgentBfx run --suite bioagent-bench --output results/
```

### Grading Methodology

Deterministic grading compares agent output against reference results with three weighted components:

| Component | Weight | Method |
|-----------|--------|--------|
| Column overlap | 0.2 | Jaccard similarity of CSV/TSV column headers |
| ID set overlap | 0.4 | Jaccard similarity of identifier column values (gene IDs, pathway names, etc.) |
| Numeric correlation | 0.4 | Mean Pearson correlation across shared numeric columns |

VCF outputs (giab task) use a simplified structural check (header presence + data line count).

Tasks without pre-downloaded reference results are automatically skipped when using `--agent-cmd`.

### Prompting Parity

All three suites (BioTaskBench, BioAgent Bench, BixBench) produce identical task.json format consumed by the same agent scripts. The agent scripts (`scripts/run_claude.py`, `scripts/run_codex.py`) handle skill prompting uniformly via the `BENCHMARK_SKILLS_PATH` environment variable.

## Notes

- `suite=all` now emits a combined multi-suite run artifact. External suites are scaffolded and reported as `scaffold_ready` when setup/listing works; execution and grading remain to be wired.
- External suites can also ingest precomputed benchmark results via env vars:
  - `BIOAGENT_BENCH_RESULTS_JSON`
  - `BIXBENCH_RESULTS_JSON`
- Optional external execution hooks:
  - `BIOAGENT_BENCH_RUN_CMD`
  - `BIXBENCH_RUN_CMD`
- Grading implements deterministic criteria and task-level weighted scoring.
- `compare` returns both overall and per-domain deltas.
- `--allow-missing-expected` is useful while expected artifacts are still being generated.
- `audit-data` checks per-test and total data-size constraints from the benchmark plan.
- `audit-flaky` computes per-test score spread across repeated run artifacts.
- `--agent-cmd` enables direct per-test command execution for BioTaskBench runs (inputs are copied from each test `data/` directory into a temporary workspace).
- `compare` and `report` accept:
  - direct `run.json`
  - a run directory containing `run.json`
  - a parent output directory containing `run-*/run.json` (latest is used)
- `--resume` continues a previous run, skipping tests that already completed successfully (i.e. `attempted=True`). Results from the prior run are carried forward and merged with newly executed tests into a fresh run artifact.
- External suite status values:
  - `scaffold_ready`: adapter loaded, but no ingested results yet
  - `ok`: results ingested/scored
  - `error`: adapter execution failed; inspect `adapter_execution.stderr` in run JSON
