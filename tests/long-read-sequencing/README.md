# Long-read Sequencing Test Data

This directory contains initial Phase 2 long-read-sequencing benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All Long-read Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/long-read-sequencing/lrs-001/data/generate_data.py
python tests/long-read-sequencing/lrs-002/data/generate_data.py
python tests/long-read-sequencing/lrs-003/data/generate_data.py
```

## Per-test Outputs

### `lrs-001`

- Input: `tests/long-read-sequencing/lrs-001/data/read_lengths.tsv`
- Expected: `tests/long-read-sequencing/lrs-001/expected/read_stats.tsv`

### `lrs-002`

- Input: `tests/long-read-sequencing/lrs-002/data/read_alignment_summary.tsv`
- Expected: `tests/long-read-sequencing/lrs-002/expected/top25_indel_reads.tsv`

### `lrs-003`

- Input: `tests/long-read-sequencing/lrs-003/data/consensus_support.tsv`
- Expected: `tests/long-read-sequencing/lrs-003/expected/consensus_summary.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
