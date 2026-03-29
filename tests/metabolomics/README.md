# Metabolomics Test Data

This directory contains initial Phase 2 metabolomics benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All Metabolomics Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/metabolomics/metab-001/data/generate_data.py
python tests/metabolomics/metab-002/data/generate_data.py
python tests/metabolomics/metab-003/data/generate_data.py
```

## Per-test Outputs

### `metab-001`
- Input: `tests/metabolomics/metab-001/data/feature_intensity.tsv`
- Expected: `tests/metabolomics/metab-001/expected/feature_summary.tsv`

### `metab-002`
- Input: `tests/metabolomics/metab-002/data/differential_input.tsv`
- Expected: `tests/metabolomics/metab-002/expected/top30_features.tsv`

### `metab-003`
- Input: `tests/metabolomics/metab-003/data/pathway_input.tsv`
- Expected: `tests/metabolomics/metab-003/expected/activated_pathways.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
