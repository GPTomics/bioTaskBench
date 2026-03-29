# Methylation Analysis Test Data

This directory contains initial Phase 2 methylation-analysis benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All Methylation Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/methylation-analysis/meth-001/data/generate_data.py
python tests/methylation-analysis/meth-002/data/generate_data.py
python tests/methylation-analysis/meth-003/data/generate_data.py
```

## Per-test Outputs

### `meth-001`
- Input: `tests/methylation-analysis/meth-001/data/cpg_beta.tsv`
- Expected: `tests/methylation-analysis/meth-001/expected/methylation_summary.tsv`

### `meth-002`
- Input: `tests/methylation-analysis/meth-002/data/dmc_input.tsv`
- Expected: `tests/methylation-analysis/meth-002/expected/top30_dmc.tsv`

### `meth-003`
- Input: `tests/methylation-analysis/meth-003/data/region_methylation.tsv`
- Expected: `tests/methylation-analysis/meth-003/expected/hypermethylated_regions.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
