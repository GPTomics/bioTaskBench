#!/usr/bin/env python3
'''Generate per-CpG bisulfite count data and expected DMC results.'''

import random
from pathlib import Path

import numpy as np
from scipy import stats

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 83
N_CPG = 200
N_SAMPLES_PER_GROUP = 6
N_DMC = 30
MIN_COVERAGE = 10


def bh_adjust(pvals):
    n = len(pvals)
    sorted_idx = sorted(range(n), key=lambda k: pvals[k])
    padj = [0.0] * n
    for rank_i, idx in enumerate(sorted_idx):
        padj[idx] = min(1.0, pvals[idx] * n / (rank_i + 1))
    for j in range(n - 2, -1, -1):
        padj[sorted_idx[j]] = min(padj[sorted_idx[j]], padj[sorted_idx[j + 1]])
    return padj


def main():
    rng = random.Random(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    case_samples = [f'case_{i+1}' for i in range(N_SAMPLES_PER_GROUP)]
    ctrl_samples = [f'ctrl_{i+1}' for i in range(N_SAMPLES_PER_GROUP)]
    all_samples = case_samples + ctrl_samples

    true_base_beta = [rng.uniform(0.20, 0.80) for _ in range(N_CPG)]
    true_delta = [0.0] * N_CPG
    for i in range(N_DMC):
        true_delta[i] = rng.uniform(0.30, 0.50) * (1 if rng.random() < 0.7 else -1)

    rows = []
    for i in range(N_CPG):
        cpg_id = f'cpg_{i+1:04d}'
        row = {'cpg_id': cpg_id}
        for s in all_samples:
            is_case = s.startswith('case')
            shift = true_delta[i] / 2.0 if is_case else -true_delta[i] / 2.0
            true_p = max(0.02, min(0.98, true_base_beta[i] + shift))
            coverage = rng.randint(20, 80)
            if rng.random() < 0.04:
                coverage = rng.randint(2, 7)
            meth_count = np.random.binomial(coverage, true_p)
            row[f'{s}_meth'] = int(meth_count)
            row[f'{s}_total'] = coverage
        rows.append(row)

    inp = SCRIPT_DIR / 'bisulfite_counts.tsv'
    header_cols = ['cpg_id']
    for s in all_samples:
        header_cols.extend([f'{s}_meth', f'{s}_total'])
    with inp.open('w') as f:
        f.write('\t'.join(header_cols) + '\n')
        for row in rows:
            f.write('\t'.join(str(row[c]) for c in header_cols) + '\n')

    passing = []
    for i in range(N_CPG):
        cpg_id = f'cpg_{i+1:04d}'
        row = rows[i]
        case_betas, ctrl_betas = [], []
        skip = False
        for s in case_samples:
            if row[f'{s}_total'] < MIN_COVERAGE:
                skip = True
                break
            case_betas.append(row[f'{s}_meth'] / row[f'{s}_total'])
        if skip:
            continue
        for s in ctrl_samples:
            if row[f'{s}_total'] < MIN_COVERAGE:
                skip = True
                break
            ctrl_betas.append(row[f'{s}_meth'] / row[f'{s}_total'])
        if skip:
            continue
        _, pval = stats.ttest_ind(case_betas, ctrl_betas, equal_var=False)
        delta_beta = float(np.mean(case_betas) - np.mean(ctrl_betas))
        passing.append((cpg_id, delta_beta, pval, i))

    pvals = [p for _, _, p, _ in passing]
    padj = bh_adjust(pvals)

    sig_dmc = [cpg_id for k, (cpg_id, _, _, orig_i) in enumerate(passing) if padj[k] < 0.05 and orig_i < N_DMC]

    all_fc = EXPECTED_DIR / 'all_delta_beta.tsv'
    with all_fc.open('w') as f:
        f.write('cpg_id\tdelta_beta\n')
        for i in range(N_CPG):
            f.write(f'cpg_{i+1:04d}\t{true_delta[i]:.6f}\n')

    exp = EXPECTED_DIR / 'significant_dmcs.tsv'
    with exp.open('w') as f:
        f.write('cpg_id\n')
        for cpg_id in sig_dmc:
            f.write(f'{cpg_id}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {all_fc}')
    print(f'Wrote: {exp}')
    print(f'Total CpGs: {N_CPG}, passing coverage filter: {len(passing)}')
    print(f'Planted DMCs: {N_DMC}, significant after BH: {len(sig_dmc)}')
    false_pos = sum(1 for k, (_, _, _, orig_i) in enumerate(passing) if padj[k] < 0.05 and orig_i >= N_DMC)
    print(f'False positives: {false_pos}')


if __name__ == '__main__':
    main()
