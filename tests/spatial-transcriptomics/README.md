# Spatial Transcriptomics Test Data

This directory contains initial Phase 2 spatial-transcriptomics benchmark tests.

## Environment

Use the `bioskills` environment (or equivalent) with Python available.

## Generate All Spatial Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/spatial-transcriptomics/stx-001/data/generate_data.py
python tests/spatial-transcriptomics/stx-002/data/generate_data.py
python tests/spatial-transcriptomics/stx-003/data/generate_data.py
python tests/spatial-transcriptomics/stx-004/data/generate_data.py
```

## Per-test Outputs

### `stx-001`

- Input: `tests/spatial-transcriptomics/stx-001/data/spots.tsv`
- Expected: `tests/spatial-transcriptomics/stx-001/expected/gradient_summary.tsv`

### `stx-002`

- Input: `tests/spatial-transcriptomics/stx-002/data/expression_matrix.tsv`
- Expected: `tests/spatial-transcriptomics/stx-002/expected/hotspot_genes.tsv`

### `stx-003`

- Input: `tests/spatial-transcriptomics/stx-003/data/spots_clustered.tsv`
- Expected: `tests/spatial-transcriptomics/stx-003/expected/enriched_clusters.tsv`

### `stx-004`

- Input: `tests/spatial-transcriptomics/stx-004/data/spots_celltypes.tsv`
- Expected: `tests/spatial-transcriptomics/stx-004/expected/hotspot_niches.tsv`

## Validation

```bash
python -m harness.cli validate --tests-root tests
```
