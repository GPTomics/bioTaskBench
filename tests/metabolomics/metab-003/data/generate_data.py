#!/usr/bin/env python3
'''Generate simulated LC-MS metabolomics intensity matrix with planted DE features.'''

import numpy as np
from scipy import stats
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 103
N_FEATURES = 150
N_SAMPLES = 10
N_CASE = 5
N_CONTROL = 5
N_DE = 20
FC_RANGE = (2.5, 5.0)


def main():
    rng = np.random.RandomState(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    sample_ids = [f'S{i+1:02d}' for i in range(N_SAMPLES)]
    case_idx = list(range(N_CASE))
    control_idx = list(range(N_CASE, N_SAMPLES))
    groups = ['case'] * N_CASE + ['control'] * N_CONTROL

    feature_ids = [f'FT_{i+1:04d}' for i in range(N_FEATURES)]
    intensities = np.zeros((N_FEATURES, N_SAMPLES))
    true_log2fc = np.zeros(N_FEATURES)
    planted_fc = {}

    for i in range(N_FEATURES):
        base_mu = rng.uniform(8.0, 14.0)
        base_sigma = rng.uniform(0.2, 0.5)

        if i < N_DE:
            raw_fc = rng.uniform(*FC_RANGE)
            direction = 1 if rng.random() < 0.7 else -1
            fc = raw_fc if direction == 1 else 1.0 / raw_fc
            log2fc_true = np.log2(fc)
            planted_fc[feature_ids[i]] = log2fc_true
            true_log2fc[i] = log2fc_true
            shift = log2fc_true / 2.0
            for j in case_idx:
                intensities[i, j] = 2.0 ** rng.normal(base_mu + shift, base_sigma)
            for j in control_idx:
                intensities[i, j] = 2.0 ** rng.normal(base_mu - shift, base_sigma)
        else:
            true_log2fc[i] = 0.0
            for j in range(N_SAMPLES):
                intensities[i, j] = 2.0 ** rng.normal(base_mu, base_sigma)

    intensities_path = SCRIPT_DIR / 'feature_intensities.tsv'
    with intensities_path.open('w') as f:
        f.write('feature_id\t' + '\t'.join(sample_ids) + '\n')
        for i in range(N_FEATURES):
            vals = '\t'.join(f'{intensities[i, j]:.4f}' for j in range(N_SAMPLES))
            f.write(f'{feature_ids[i]}\t{vals}\n')

    metadata_path = SCRIPT_DIR / 'sample_metadata.tsv'
    with metadata_path.open('w') as f:
        f.write('sample_id\tgroup\n')
        for sid, grp in zip(sample_ids, groups):
            f.write(f'{sid}\t{grp}\n')

    log2_intensities = np.log2(intensities)
    pvalues = np.zeros(N_FEATURES)
    observed_log2fc = np.zeros(N_FEATURES)

    for i in range(N_FEATURES):
        case_vals = log2_intensities[i, case_idx]
        ctrl_vals = log2_intensities[i, control_idx]
        observed_log2fc[i] = case_vals.mean() - ctrl_vals.mean()
        _, pvalues[i] = stats.ttest_ind(case_vals, ctrl_vals, equal_var=False)

    ranked_idx = np.argsort(pvalues)
    padj = np.ones(N_FEATURES)
    for rank, idx in enumerate(ranked_idx):
        padj[idx] = min(pvalues[idx] * N_FEATURES / (rank + 1), 1.0)
    for i in range(len(ranked_idx) - 2, -1, -1):
        idx = ranked_idx[i]
        next_idx = ranked_idx[i + 1]
        padj[idx] = min(padj[idx], padj[next_idx])

    significant_planted = [feature_ids[i] for i in range(N_DE) if padj[i] < 0.05]

    sig_path = EXPECTED_DIR / 'significant_features.tsv'
    with sig_path.open('w') as f:
        f.write('feature_id\n')
        for fid in significant_planted:
            f.write(f'{fid}\n')

    fc_path = EXPECTED_DIR / 'all_foldchanges.tsv'
    with fc_path.open('w') as f:
        f.write('feature_id\tlog2fc\n')
        for i in range(N_FEATURES):
            f.write(f'{feature_ids[i]}\t{true_log2fc[i]:.6f}\n')

    n_sig_total = sum(1 for p in padj if p < 0.05)
    n_sig_planted = len(significant_planted)
    n_false_pos = n_sig_total - n_sig_planted

    spearman_r, _ = stats.spearmanr(true_log2fc, observed_log2fc)

    print(f'Wrote: {intensities_path}')
    print(f'Wrote: {metadata_path}')
    print(f'Wrote: {sig_path}')
    print(f'Wrote: {fc_path}')
    print(f'Features: {N_FEATURES}, Samples: {N_SAMPLES} ({N_CASE} case, {N_CONTROL} control)')
    print(f'Planted DE: {N_DE}, Recovered at FDR<0.05: {n_sig_planted}/{N_DE}')
    print(f'Total significant (FDR<0.05): {n_sig_total} (false positives: {n_false_pos})')
    print(f'Spearman correlation (true vs observed log2FC): {spearman_r:.4f}')


if __name__ == '__main__':
    main()
