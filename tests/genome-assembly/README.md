# Genome Assembly Test Data

This directory contains initial Phase 2 genome-assembly benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All Assembly Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/genome-assembly/assembly-001/data/generate_data.py
python tests/genome-assembly/assembly-002/data/generate_data.py
python tests/genome-assembly/assembly-003/data/generate_data.py
```

## Per-test Outputs

### `assembly-001`
- Input: `tests/genome-assembly/assembly-001/data/contig_lengths.tsv`
- Expected: `tests/genome-assembly/assembly-001/expected/assembly_stats.tsv`

### `assembly-002`
- Input: `tests/genome-assembly/assembly-002/data/overlap_candidates.tsv`
- Expected: `tests/genome-assembly/assembly-002/expected/top15_joins.tsv`

### `assembly-003`
- Input: `tests/genome-assembly/assembly-003/data/contig_errors.tsv`
- Expected: `tests/genome-assembly/assembly-003/expected/high_error_contigs.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
