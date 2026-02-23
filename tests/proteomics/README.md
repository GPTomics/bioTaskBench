# Proteomics Test Data

This directory contains initial Phase 2 proteomics benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All Proteomics Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/proteomics/prot-001/data/generate_data.py
python tests/proteomics/prot-002/data/generate_data.py
python tests/proteomics/prot-003/data/generate_data.py
```

## Per-test Outputs

### `prot-001`
- Input: `tests/proteomics/prot-001/data/protein_intensity.tsv`
- Expected: `tests/proteomics/prot-001/expected/intensity_summary.tsv`

### `prot-002`
- Input: `tests/proteomics/prot-002/data/differential_input.tsv`
- Expected: `tests/proteomics/prot-002/expected/top25_proteins.tsv`

### `prot-003`
- Input: `tests/proteomics/prot-003/data/protein_matrix.tsv`
- Expected: `tests/proteomics/prot-003/expected/high_missing_samples.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
