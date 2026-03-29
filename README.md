# Bio-Task Bench

Bio-Task Bench is both a benchmark and evaluation tool for evaluating how well AI coding agents perform bioinformatics tasks. It includes 33 original tests across 10 domains, a deterministic grading harness, and adapters for running external bioinformatics benchmarks under the same CLI.

## Quick Start

Install the harness, then run a benchmark suite against any agent:

```bash
pip install -e .

# Run BioTaskBench with Claude Code without skills
benchmarkAgentBfx run --suite biotaskbench \
  --agent-cmd "python $(pwd)/scripts/run_claude.py" \
  --model claude-sonnet-4-6 --effort medium \
  --output results/my-run

# Run with OpenAI Codex without skills
benchmarkAgentBfx run --suite biotaskbench \
  --agent-cmd "python $(pwd)/scripts/run_codex.py" \
  --model gpt-5.4-mini --effort medium \
  --output results/codex-run
  
# Run with OpenAI Codex with Skills (add the same pattern for claude)
benchmarkAgentBfx run --suite biotaskbench \
  --agent-cmd "python $(pwd)/scripts/run_codex.py" \
  --skills-path ~/path/to/skills/.agents/skills/ \
  --model gpt-5.4-mini --effort medium \
  --output results/codex-run
```

Compare two runs side by side:

```bash
benchmarkAgentBfx compare results/run-a/ results/run-b/
```

Regrade an existing run (re-evaluates all workspaces with the current grader):

```bash
benchmarkAgentBfx regrade results/run-a/
```

Generate a report across one or more runs:

```bash
benchmarkAgentBfx report results/run-a/ results/run-b/ --output report.md
```

### Run Options

| Flag | Description |
|---|---|
| `--suite` | `biotaskbench`, `bioagent-bench`, `bixbench`, or `all` |
| `--model` | Model name (e.g. `claude-sonnet-4-6`, `gpt-5.4`) |
| `--effort` | Reasoning effort passed to the agent (e.g. `high`, `medium`) |
| `--skills-path` | Path to a skills directory for A/B testing skill-augmented agents |
| `--agent-cmd` | Shell command to run per test |
| `--domain` | Run a single domain (e.g. `chip-seq`) |
| `--test-id` | Run a single test (e.g. `chipseq-001`) |
| `--output` | Results directory |
| `--workspace-root` | Grade precomputed outputs instead of running an agent |

## Datasets

### BioTaskBench (this repo)

33 tests across 10 bioinformatics domains that have little or no coverage in existing AI benchmarks:

| Domain | Tests | Difficulty |
|---|---|---|
| ChIP-seq | 4 | 1 basic, 3 intermediate |
| Spatial Transcriptomics | 4 | 2 basic, 2 intermediate |
| Population Genetics | 4 | 2 basic, 2 intermediate |
| Long-Read Sequencing | 3 | 2 basic, 1 intermediate |
| Proteomics | 3 | 2 basic, 1 intermediate |
| Metabolomics | 3 | 2 basic, 1 intermediate |
| Genome Assembly | 3 | 1 basic, 2 intermediate |
| Methylation Analysis | 3 | 2 basic, 1 intermediate |
| CRISPR Screens | 3 | 2 basic, 1 intermediate |
| Multi-Omics Integration | 3 | 1 basic, 2 intermediate |

**Basic** tests cover standard analysis workflows (peak calling, quality metrics, format conversion). **Intermediate** tests require domain-specific reasoning like CIGAR string parsing, bisulfite beta-value computation, FDR correction, or normalization workflows.

Tests are tool-agnostic: a MACS2 solution scores the same as a HOMER solution, Python the same as R. Each test ships with a `generate_data.py` script that creates input data and expected outputs from real public datasets (ENCODE, GEO, NCBI) or simulation.

#### Scoring

Each test defines one or more grading criteria, each with a type and a weight (weights sum to 1.0). The harness supports 7 deterministic grading types:

| Type | What it checks |
|---|---|
| `file_check` | Output file exists (and optionally has expected columns) |
| `column_check` | Output contains required columns |
| `exact_match` | A specific value appears in the output |
| `range_check` | A numeric value falls within an expected range |
| `set_overlap` | Overlap between output and reference sets (Jaccard, F1) |
| `numeric_correlation` | Correlation between output and reference vectors (Pearson, Spearman) |
| `code_executes` | Generated code runs without error |

A test's score is the weighted sum of its criteria scores (0.0 to 1.0). Results are aggregated at the domain, difficulty, and overall level. The harness tracks **coverage** (fraction of tests where the agent produced any output) separately from **score** (quality of that output), so you can distinguish "the agent didn't attempt it" from "the agent tried and got it wrong."

### External Benchmarks

The harness wraps external bioinformatics benchmarks under the same CLI so results can be compared directly.

#### BixBench

**[BixBench](https://github.com/Future-House/BixBench)**: 205 multiple-choice questions across 60 computational biology analysis capsules. The adapter indexes questions from BixBench's baseline evaluation data, runs agent answers through the grading pipeline, and normalizes scores to the same 0-1 scale.

```bash
benchmarkAgentBfx run --suite bixbench --agent-cmd "python $(pwd)/scripts/run_claude.py"
```

**Scoring:** Binary per question (correct answer or not), aggregated as questions correct / questions total.

#### BioAgent Bench

**(WIP) [BioAgent Bench](https://github.com/bioagent-bench/bioagent-bench)**: 10 end-to-end bioinformatics pipeline tasks. Scoring is based on pipeline steps completed / total steps. Adapter integration is a work in progress.
