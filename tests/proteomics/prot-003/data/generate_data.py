#!/usr/bin/env python3
'''Generate simulated LC-MS/MS protein intensity matrix with planted DE proteins and batch effects.'''

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 93
N_PROTEINS = 200
N_SAMPLES = 8
N_CASE = 4
N_CONTROL = 4
N_DE = 30
FC_RANGE = (2.0, 4.0)
BASELINE_MU = 24.0
BASELINE_SIGMA = 1.8
NOISE_SIGMA = 0.2
BATCH_MAGNITUDES = [0.0, 0.5, -0.3, 0.2, 0.8, -0.6, 0.4, -0.2]


def main():
    rng = np.random.RandomState(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    sample_ids = [f'S{i+1}' for i in range(N_SAMPLES)]
    groups = ['case'] * N_CASE + ['control'] * N_CONTROL
    protein_ids = [f'PROT{i+1:04d}' for i in range(N_PROTEINS)]

    log2_baseline = rng.normal(BASELINE_MU, BASELINE_SIGMA, size=(N_PROTEINS, 1))
    noise = rng.normal(0, NOISE_SIGMA, size=(N_PROTEINS, N_SAMPLES))
    log2_matrix = log2_baseline + noise

    batch_effects = np.array(BATCH_MAGNITUDES).reshape(1, N_SAMPLES)
    log2_matrix += batch_effects

    de_indices = rng.choice(N_PROTEINS, size=N_DE, replace=False)
    true_log2fc = rng.uniform(np.log2(FC_RANGE[0]), np.log2(FC_RANGE[1]), size=N_DE)
    signs = rng.choice([-1, 1], size=N_DE)
    true_log2fc *= signs

    for i, idx in enumerate(de_indices):
        log2_matrix[idx, :N_CASE] += true_log2fc[i] / 2
        log2_matrix[idx, N_CASE:] -= true_log2fc[i] / 2

    raw_intensities = np.power(2, log2_matrix)

    intensity_df = pd.DataFrame(raw_intensities, index=protein_ids, columns=sample_ids)
    intensity_df.index.name = 'protein_id'
    intensity_path = SCRIPT_DIR / 'protein_intensities.tsv'
    intensity_df.to_csv(intensity_path, sep='\t', float_format='%.4f')

    groups_df = pd.DataFrame({'sample_id': sample_ids, 'group': groups})
    groups_path = SCRIPT_DIR / 'sample_groups.tsv'
    groups_df.to_csv(groups_path, sep='\t', index=False)

    log2_data = np.log2(raw_intensities)
    sample_medians = np.median(log2_data, axis=0)
    global_median = np.median(sample_medians)
    log2_norm = log2_data - sample_medians + global_median

    all_log2fc = []
    all_pvalues = []
    for pidx in range(N_PROTEINS):
        case_vals = log2_norm[pidx, :N_CASE]
        ctrl_vals = log2_norm[pidx, N_CASE:]
        fc = np.mean(case_vals) - np.mean(ctrl_vals)
        _, pval = stats.ttest_ind(case_vals, ctrl_vals, equal_var=False)
        all_log2fc.append(fc)
        all_pvalues.append(pval)

    all_log2fc = np.array(all_log2fc)
    all_pvalues = np.array(all_pvalues)

    n_tests = len(all_pvalues)
    sorted_indices = np.argsort(all_pvalues)
    padj = np.ones(n_tests)
    for rank, idx in enumerate(sorted_indices):
        padj[idx] = all_pvalues[idx] * n_tests / (rank + 1)
    for i in range(n_tests - 2, -1, -1):
        idx = sorted_indices[i]
        idx_next = sorted_indices[i + 1]
        padj[idx] = min(padj[idx], padj[idx_next])
    padj = np.clip(padj, 0, 1)

    true_fc_map = {}
    for i, idx in enumerate(de_indices):
        true_fc_map[protein_ids[idx]] = true_log2fc[i]

    all_results_df = pd.DataFrame({
        'protein_id': protein_ids,
        'log2fc': [true_fc_map.get(pid, 0.0) for pid in protein_ids]
    })
    all_results_path = EXPECTED_DIR / 'all_results.tsv'
    all_results_df.to_csv(all_results_path, sep='\t', index=False, float_format='%.6f')

    sig_mask = padj[de_indices] < 0.05
    sig_proteins = []
    for i, idx in enumerate(de_indices):
        if sig_mask[i]:
            sig_proteins.append({
                'protein_id': protein_ids[idx],
                'log2fc': true_log2fc[i],
                'padj': padj[idx]
            })

    sig_df = pd.DataFrame(sig_proteins)
    if len(sig_df) > 0:
        sig_df = sig_df.sort_values('padj').reset_index(drop=True)
    sig_path = EXPECTED_DIR / 'significant_proteins.tsv'
    sig_df.to_csv(sig_path, sep='\t', index=False, float_format='%.6f')

    print(f'Wrote: {intensity_path}')
    print(f'Wrote: {groups_path}')
    print(f'Wrote: {all_results_path}')
    print(f'Wrote: {sig_path}')
    print(f'Total proteins: {N_PROTEINS}')
    print(f'Planted DE proteins: {N_DE}')
    print(f'DE proteins significant at padj<0.05 (after normalization + Welch t-test): {sig_mask.sum()}')
    print(f'Batch effect magnitudes (log2): {BATCH_MAGNITUDES}')
    print(f'FC range: {FC_RANGE[0]}-{FC_RANGE[1]}x')
    n_false_pos = sum(1 for i in range(N_PROTEINS) if i not in de_indices and padj[i] < 0.05)
    print(f'False positives (non-DE with padj<0.05): {n_false_pos}')
    print(f'Spearman correlation (estimated vs true log2fc): {stats.spearmanr(all_log2fc, [true_fc_map.get(pid, 0.0) for pid in protein_ids]).correlation:.4f}')


if __name__ == '__main__':
    main()
