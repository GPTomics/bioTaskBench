# CRISPR Screens Test Data

This directory contains initial Phase 2 CRISPR-screen benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All CRISPR Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/crispr-screens/crispr-001/data/generate_data.py
python tests/crispr-screens/crispr-002/data/generate_data.py
python tests/crispr-screens/crispr-003/data/generate_data.py
```

## Per-test Outputs

### `crispr-001`
- Input: `tests/crispr-screens/crispr-001/data/guide_lfc.tsv`
- Expected: `tests/crispr-screens/crispr-001/expected/guide_summary.tsv`

### `crispr-002`
- Input: `tests/crispr-screens/crispr-002/data/gene_scores.tsv`
- Expected: `tests/crispr-screens/crispr-002/expected/top20_essential.tsv`

### `crispr-003`
- Input: `tests/crispr-screens/crispr-003/data/control_guides.tsv`
- Expected: `tests/crispr-screens/crispr-003/expected/failing_sets.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
