# BioTaskBench

> **WIP:** this repository is still in active development.

BioTaskBench is a benchmark suite for evaluating LLM/agent bioinformatics capability, plus a unified harness for running BioTaskBench and external benchmark suites under one CLI.

## What Is Built

- A BioTaskBench test corpus across 10 domains under `tests/` (currently 33 tests).
- Deterministic grading harness with weighted multi-criteria scoring:
  - `file_check`, `column_check`, `exact_match`, `range_check`
  - `set_overlap`, `numeric_correlation`, `code_executes` (plus `llm_judge` stub)
- Coverage and score reporting:
  - `coverage` = attempted / total
  - `completion_rate` = tests with score > 0
  - `score` = mean across attempted tests
  - `score_overall` = mean across all tests
  - domain and difficulty breakdowns
- Multi-suite runner:
  - `biotaskbench`, `bioagent-bench`, `biocoder`, `bixbench`, `all`
- External adapter scaffolds with:
  - setup/listing
  - optional command execution hooks
  - optional precomputed results JSON ingestion
  - score normalization
- Utilities for benchmark health:
  - data-size audit (`<10MB/test`, `<500MB total`)
  - flakiness audit across repeated run artifacts
  - adapter readiness/status diagnostics
- Automation scripts for Phase 4/5 calibration/baseline workflows.

## Repository Layout

- `harness/`: CLI, runner, grader, reporter, schemas, adapter integrations, audit utilities
- `tests/`: BioTaskBench domain manifests + task definitions + data + expected outputs
- `tests_harness/`: harness unit/integration tests
- `mock_outputs/`: deterministic mock outputs for regression runs
- `reference/`: writing guide + benchmark survey
- `scripts/`: calibration and baseline run scripts

## Core CLI

```bash
# Validate suite/task schemas and expected artifacts
benchmarkAgentBfx validate --tests-root tests

# Run BioTaskBench using precomputed workspace outputs
benchmarkAgentBfx run --suite biotaskbench --tests-root tests --workspace-root mock_outputs

# Run BioTaskBench by executing an agent command per test
benchmarkAgentBfx run --suite biotaskbench --domain chip-seq --agent-cmd "python agent.py"

# Run all suites (BioTaskBench + external adapters)
benchmarkAgentBfx run --suite all --tests-root tests --workspace-root mock_outputs

# Compare and report
benchmarkAgentBfx compare results/run-a/run.json results/run-b/run.json
benchmarkAgentBfx report results/run-a/run.json results/run-b/run.json --output results/report.md

# Benchmark health audits
benchmarkAgentBfx audit-data --tests-root tests
benchmarkAgentBfx audit-flaky results/run-1/run.json results/run-2/run.json results/run-3/run.json --threshold 0.3

# External adapter readiness snapshot
benchmarkAgentBfx adapter-status
```

## External Adapter Env Vars

- Results ingestion:
  - `BIOAGENT_BENCH_RESULTS_JSON`
  - `BIOCODER_RESULTS_JSON`
  - `BIXBENCH_RESULTS_JSON`
- Optional execution commands:
  - `BIOAGENT_BENCH_RUN_CMD`
  - `BIOCODER_RUN_CMD`
  - `BIXBENCH_RUN_CMD`
- Optional roots/catalogs:
  - `BIOAGENT_BENCH_ROOT`, `BIOAGENT_BENCH_TESTS_JSON`
  - `BIOCODER_ROOT`, `BIOCODER_TESTS_JSON`
  - `BIXBENCH_ROOT`, `BIXBENCH_TESTS_JSON`

## Phase 4/5 Scripts

```bash
# Replica calibration + flakiness/data audits
./scripts/run_phase4_calibration.sh

# Baseline matrix (without/with skills when BIO_SKILLS_PATH is set)
BIO_SKILLS_PATH=~/.claude/skills ./scripts/run_phase5_baselines.sh
```
