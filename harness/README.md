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
benchmarkAgentBfx compare results/run-a/run.json results/run-b/run.json
benchmarkAgentBfx report results/run-a/run.json --output results/report.json
benchmarkAgentBfx audit-data --tests-root tests
benchmarkAgentBfx audit-flaky results/run-1/run.json results/run-2/run.json results/run-3/run.json --threshold 0.3
benchmarkAgentBfx adapter-status
./scripts/run_phase4_calibration.sh
BIO_SKILLS_PATH=~/.claude/skills ./scripts/run_phase5_baselines.sh
```

## Notes

- `suite=all` now emits a combined multi-suite run artifact. External suites are scaffolded and reported as `scaffold_ready` when setup/listing works; execution and grading remain to be wired.
- External suites can also ingest precomputed benchmark results via env vars:
  - `BIOAGENT_BENCH_RESULTS_JSON`
  - `BIOCODER_RESULTS_JSON`
  - `BIXBENCH_RESULTS_JSON`
- Optional external execution hooks:
  - `BIOAGENT_BENCH_RUN_CMD`
  - `BIOCODER_RUN_CMD`
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
- External suite status values:
  - `scaffold_ready`: adapter loaded, but no ingested results yet
  - `ok`: results ingested/scored
  - `error`: adapter execution failed; inspect `adapter_execution.stderr` in run JSON
