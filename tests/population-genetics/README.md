# Population Genetics Test Data

This directory contains initial Phase 2 population-genetics benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

Required Python packages for generation scripts:

- Standard library only (no external dependencies required)

## Generate All Population-genetics Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/population-genetics/popgen-001/data/generate_data.py
python tests/population-genetics/popgen-002/data/generate_data.py
python tests/population-genetics/popgen-003/data/generate_data.py
python tests/population-genetics/popgen-004/data/generate_data.py
```

## Per-test Outputs

### `popgen-001`

- Input generated:
  - `tests/population-genetics/popgen-001/data/allele_freq.tsv`
- Expected generated:
  - `tests/population-genetics/popgen-001/expected/fst_summary.tsv`

### `popgen-002`

- Input generated:
  - `tests/population-genetics/popgen-002/data/allele_freq.tsv`
- Expected generated:
  - `tests/population-genetics/popgen-002/expected/top20_snps.tsv`

### `popgen-003`

- Input generated:
  - `tests/population-genetics/popgen-003/data/genotype_counts.tsv`
- Expected generated:
  - `tests/population-genetics/popgen-003/expected/significant_snps.tsv`

### `popgen-004`

- Input generated:
  - `tests/population-genetics/popgen-004/data/genotype_matrix.tsv`
- Expected generated:
  - `tests/population-genetics/popgen-004/expected/outlier_samples.tsv`

## Validation

After data generation:

```bash
python -m harness.cli validate --tests-root tests
```
