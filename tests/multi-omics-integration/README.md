# Multi-omics Integration Test Data

This directory contains initial Phase 2 multi-omics integration benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All Multi-omics Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/multi-omics-integration/moi-001/data/generate_data.py
python tests/multi-omics-integration/moi-002/data/generate_data.py
python tests/multi-omics-integration/moi-003/data/generate_data.py
```

## Per-test Outputs

### `moi-001`
- Input: `tests/multi-omics-integration/moi-001/data/paired_gene_values.tsv`
- Expected: `tests/multi-omics-integration/moi-001/expected/association_summary.tsv`

### `moi-002`
- Input: `tests/multi-omics-integration/moi-002/data/integrated_features.tsv`
- Expected: `tests/multi-omics-integration/moi-002/expected/top25_features.tsv`

### `moi-003`
- Input: `tests/multi-omics-integration/moi-003/data/pathway_signals.tsv`
- Expected: `tests/multi-omics-integration/moi-003/expected/concordant_pathways.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
