# ChIP-seq Test Data

This directory contains the Phase 1 ChIP-seq benchmark tests and their data generation scripts.

## Environment

Use the `bioskills` environment (or equivalent) with:

- CLI tools: `curl`, `samtools`, `bedtools`, `macs3`, `makeTagDirectory`, `findPeaks`
- Python deps: `numpy`, `requests`

## Generate All ChIP-seq Data

Run from repository root:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate bioskills

python tests/chip-seq/chipseq-001/data/generate_data.py
python tests/chip-seq/chipseq-002/data/generate_data.py
python tests/chip-seq/chipseq-003/data/generate_data.py
python tests/chip-seq/chipseq-004/data/generate_data.py
python tests/chip-seq/chipseq-005/data/generate_data.py
```

## Per-test Outputs

### `chipseq-001`

- Inputs generated:
  - `tests/chip-seq/chipseq-001/data/treatment.tagAlign.gz`
  - `tests/chip-seq/chipseq-001/data/control.tagAlign.gz`
- Expected generated:
  - `tests/chip-seq/chipseq-001/expected/consensus_peaks.bed`

Note: MACS3 uses `--nomodel --extsize 147` for this chr21-only dataset.

### `chipseq-002`

- Input generated:
  - `tests/chip-seq/chipseq-002/data/peaks.fa`

### `chipseq-003`

- Inputs generated:
  - `tests/chip-seq/chipseq-003/data/genes.gtf.gz`
  - `tests/chip-seq/chipseq-003/data/peaks.bed`
- Expected generated:
  - `tests/chip-seq/chipseq-003/expected/annotations.tsv`

### `chipseq-004`

- Inputs generated:
  - `tests/chip-seq/chipseq-004/data/counts.tsv`
  - `tests/chip-seq/chipseq-004/data/regions.bed`
- Expected generated:
  - `tests/chip-seq/chipseq-004/expected/differential_peaks.tsv`
  - `tests/chip-seq/chipseq-004/expected/true_log2fc.tsv`

### `chipseq-005`

- Inputs generated:
  - `tests/chip-seq/chipseq-005/data/control_rep1.tagAlign.gz`
  - `tests/chip-seq/chipseq-005/data/control_rep2.tagAlign.gz`
  - `tests/chip-seq/chipseq-005/data/treated_rep1.tagAlign.gz`
  - `tests/chip-seq/chipseq-005/data/treated_rep2.tagAlign.gz`
  - `tests/chip-seq/chipseq-005/data/control_input.tagAlign.gz`
  - `tests/chip-seq/chipseq-005/data/treated_input.tagAlign.gz`
  - `tests/chip-seq/chipseq-005/data/spikein_counts.tsv`
  - `tests/chip-seq/chipseq-005/data/genes.gtf.gz`
  - `tests/chip-seq/chipseq-005/data/blacklist.bed`
  - `tests/chip-seq/chipseq-005/data/cnv_segments.bed`
- Expected generated:
  - `tests/chip-seq/chipseq-005/expected/significant_enhancers.bed`
  - `tests/chip-seq/chipseq-005/expected/normalization_truth.tsv`
  - `tests/chip-seq/chipseq-005/expected/true_enhancer_truth.tsv`

Note: `chipseq-005` is a hybrid benchmark. It uses public ENCODE K562 H3K27ac/input reads as the substrate, then applies deterministic benchmark-specific perturbations to create a global H3K27ac shift, true distal enhancer gains, promoter decoys, and CNV-confounded loci. Data generation requires internet access.

## Validation

After data generation:

```bash
python -m harness.cli validate --tests-root tests
```
