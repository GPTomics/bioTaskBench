#!/usr/bin/env python3
'''Generate differential binding test data: simulated H3K27ac ChIP-seq count
matrix with planted differentially bound regions.

Requirements: Python with numpy

Source: Fully simulated (no downloads needed)
'''

import numpy as np
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'

RANDOM_SEED = 42
NUM_PEAKS = 200
NUM_STRONG_DE = 20
NUM_MODERATE_DE = 20
NUM_REPLICATES = 3
CHR21_SIZE = 46709983


def generate_regions(rng):
    positions = sorted(rng.choice(CHR21_SIZE - 2_000_000, size=NUM_PEAKS, replace=False) + 1_000_000)
    return [('chr21', int(pos), int(pos) + int(rng.integers(300, 2000)), f'peak_{i + 1:03d}')
            for i, pos in enumerate(positions)]


def generate_counts(rng):
    base_means = rng.lognormal(mean=4.0, sigma=1.0, size=NUM_PEAKS).clip(20, 800)
    dispersions = 1.0 / rng.chisquare(df=20, size=NUM_PEAKS)

    true_log2fc = np.zeros(NUM_PEAKS)
    de_indices = rng.choice(NUM_PEAKS, size=NUM_STRONG_DE + NUM_MODERATE_DE, replace=False)
    strong_idx, moderate_idx = de_indices[:NUM_STRONG_DE], de_indices[NUM_STRONG_DE:]

    directions = rng.choice([-1, 1], size=len(de_indices))
    true_log2fc[strong_idx] = directions[:NUM_STRONG_DE] * rng.uniform(1.5, 3.0, size=NUM_STRONG_DE)
    true_log2fc[moderate_idx] = directions[NUM_STRONG_DE:] * rng.uniform(0.7, 1.5, size=NUM_MODERATE_DE)

    treated_means = base_means * (2.0 ** true_log2fc)
    control_means = base_means

    treated_counts = np.zeros((NUM_PEAKS, NUM_REPLICATES), dtype=int)
    control_counts = np.zeros((NUM_PEAKS, NUM_REPLICATES), dtype=int)
    for i in range(NUM_PEAKS):
        for counts, mu in [(treated_counts, treated_means[i]), (control_counts, control_means[i])]:
            r = 1.0 / dispersions[i]
            p = r / (r + mu)
            counts[i] = rng.negative_binomial(r, p, size=NUM_REPLICATES)

    return treated_counts, control_counts, true_log2fc, de_indices


def write_count_matrix(regions, treated, control, output_path):
    with open(output_path, 'w') as f:
        f.write('peak_id\ttreated_1\ttreated_2\ttreated_3\tcontrol_1\tcontrol_2\tcontrol_3\n')
        for i, (_, _, _, peak_id) in enumerate(regions):
            vals = '\t'.join(str(v) for v in list(treated[i]) + list(control[i]))
            f.write(f'{peak_id}\t{vals}\n')


def write_regions(regions, output_path):
    with open(output_path, 'w') as f:
        for chrom, start, end, peak_id in regions:
            f.write(f'{chrom}\t{start}\t{end}\t{peak_id}\t.\n')


def write_expected(regions, true_log2fc, de_indices):
    diff_path = EXPECTED_DIR / 'differential_peaks.tsv'
    with open(diff_path, 'w') as f:
        f.write('peak_id\n')
        for idx in sorted(de_indices):
            f.write(f'{regions[idx][3]}\n')

    log2fc_path = EXPECTED_DIR / 'true_log2fc.tsv'
    with open(log2fc_path, 'w') as f:
        f.write('peak_id\tlog2fc\n')
        for i, (_, _, _, peak_id) in enumerate(regions):
            f.write(f'{peak_id}\t{true_log2fc[i]:.6f}\n')

    print(f'  differential_peaks.tsv: {len(de_indices)} peaks')
    print(f'  true_log2fc.tsv: {len(regions)} peaks')


def main():
    print('=' * 60)
    print('chipseq-004: Differential Binding Data Generation')
    print('=' * 60 + '\n')

    rng = np.random.default_rng(RANDOM_SEED)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    print('Step 1: Generate peak regions')
    regions = generate_regions(rng)
    regions_path = SCRIPT_DIR / 'regions.bed'
    write_regions(regions, regions_path)
    print(f'  {len(regions)} peak regions on chr21')

    print('\nStep 2: Simulate count matrix')
    treated, control, true_log2fc, de_indices = generate_counts(rng)
    counts_path = SCRIPT_DIR / 'counts.tsv'
    write_count_matrix(regions, treated, control, counts_path)
    print(f'  {NUM_PEAKS} peaks, {NUM_REPLICATES} replicates per condition')
    print(f'  {NUM_STRONG_DE} strong DE (|log2FC| 1.5-3.0), {NUM_MODERATE_DE} moderate DE (|log2FC| 0.7-1.5)')

    all_means = np.concatenate([treated.mean(axis=1), control.mean(axis=1)])
    print(f'  Mean count range: {all_means.min():.0f}-{all_means.max():.0f}')

    print('\nStep 3: Write expected outputs')
    write_expected(regions, true_log2fc, de_indices)

    size_kb = counts_path.stat().st_size / 1024
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'  counts.tsv: {NUM_PEAKS} peaks x 6 samples, {size_kb:.0f} KB')
    print(f'  regions.bed: {NUM_PEAKS} peak regions')
    print(f'  {len(de_indices)} truly differential peaks ({len(de_indices) / NUM_PEAKS * 100:.0f}%)')
    print(f'  Suggested significant_count range: [{max(15, len(de_indices) - 15)}, {len(de_indices) + 30}]')


if __name__ == '__main__':
    main()
