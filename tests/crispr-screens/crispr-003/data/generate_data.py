#!/usr/bin/env python3
'''Generate guide-level raw counts with gene mapping and expected essential genes.'''

import random
from pathlib import Path

import numpy as np
from scipy import stats

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 113
N_GENES = 80
GUIDES_PER_GENE = 4
N_ESSENTIAL = 15
N_REPLICATES = 3


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

    genes = [f'GENE_{i+1:04d}' for i in range(N_GENES)]
    essential = set(genes[:N_ESSENTIAL])

    guide_library = SCRIPT_DIR / 'guide_library.tsv'
    guide_counts = SCRIPT_DIR / 'guide_counts.tsv'

    guides = []
    for gene in genes:
        for g in range(GUIDES_PER_GENE):
            guides.append((f'{gene}_sg{g+1}', gene))

    with guide_library.open('w') as f:
        f.write('guide_id\tgene\n')
        for gid, gene in guides:
            f.write(f'{gid}\t{gene}\n')

    ctrl_cols = [f'ctrl_rep{r+1}' for r in range(N_REPLICATES)]
    treat_cols = [f'treat_rep{r+1}' for r in range(N_REPLICATES)]
    all_cols = ctrl_cols + treat_cols

    guide_data = {}
    with guide_counts.open('w') as f:
        f.write('guide_id\t' + '\t'.join(all_cols) + '\n')
        for gid, gene in guides:
            base_count = rng.randint(200, 1200)
            counts = {}
            for col in ctrl_cols:
                counts[col] = max(1, int(np.random.poisson(base_count)))
            if gene in essential:
                depletion = rng.uniform(0.15, 0.45)
                treat_mean = base_count * depletion
            else:
                treat_mean = base_count * rng.uniform(0.8, 1.2)
            for col in treat_cols:
                counts[col] = max(1, int(np.random.poisson(treat_mean)))
            guide_data[gid] = (gene, counts)
            vals = [str(counts[c]) for c in all_cols]
            f.write(f'{gid}\t' + '\t'.join(vals) + '\n')

    gene_lfcs = {}
    for gene in genes:
        gene_guides = [(gid, data) for gid, data in guide_data.items() if data[0] == gene]
        guide_lfcs = []
        for gid, (g, counts) in gene_guides:
            ctrl_mean = np.mean([counts[c] for c in ctrl_cols])
            treat_mean = np.mean([counts[c] for c in treat_cols])
            lfc = np.log2((treat_mean + 0.5) / (ctrl_mean + 0.5))
            guide_lfcs.append(lfc)
        gene_lfcs[gene] = np.median(guide_lfcs)

    gene_pvals = {}
    for gene in genes:
        gene_guides = [(gid, data) for gid, data in guide_data.items() if data[0] == gene]
        ctrl_vals, treat_vals = [], []
        for gid, (g, counts) in gene_guides:
            ctrl_vals.extend([counts[c] for c in ctrl_cols])
            treat_vals.extend([counts[c] for c in treat_cols])
        _, pval = stats.mannwhitneyu(treat_vals, ctrl_vals, alternative='less')
        gene_pvals[gene] = pval

    pval_list = [gene_pvals[g] for g in genes]
    padj_list = bh_adjust(pval_list)

    sig_essential = [g for i, g in enumerate(genes) if padj_list[i] < 0.05 and g in essential]

    all_results = EXPECTED_DIR / 'all_gene_lfc.tsv'
    with all_results.open('w') as f:
        f.write('gene\tmedian_lfc\n')
        for gene in genes:
            f.write(f'{gene}\t{gene_lfcs[gene]:.6f}\n')

    exp = EXPECTED_DIR / 'failing_sets.tsv'
    with exp.open('w') as f:
        f.write('gene\n')
        for gene in sig_essential:
            f.write(f'{gene}\n')

    print(f'Wrote: {guide_library}')
    print(f'Wrote: {guide_counts}')
    print(f'Wrote: {all_results}')
    print(f'Wrote: {exp}')
    print(f'Total genes: {N_GENES}, planted essential: {N_ESSENTIAL}')
    print(f'Significant essential after BH: {len(sig_essential)}')
    false_pos = sum(1 for i, g in enumerate(genes) if padj_list[i] < 0.05 and g not in essential)
    print(f'False positives: {false_pos}')


if __name__ == '__main__':
    main()
