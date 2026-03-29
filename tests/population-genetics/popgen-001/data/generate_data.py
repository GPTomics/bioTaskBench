#!/usr/bin/env python3
'''Generate synthetic two-population allele frequencies with sample sizes and expected Fst summary.

Uses Weir & Cockerham (1984) Fst as ground truth -- the standard estimator when
sample sizes are known and unequal.
'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 42
N_SNPS = 120
N_POP_A = 50
N_POP_B = 30


def wc_fst_components(p1, p2, n1, n2):
    r = 2
    n_bar = (n1 + n2) / r
    p_bar = (n1 * p1 + n2 * p2) / (n1 + n2)
    s_sq = (n1 * (p1 - p_bar)**2 + n2 * (p2 - p_bar)**2) / ((r - 1) * n_bar)
    h_bar = (n1 * 2 * p1 * (1 - p1) / (2 * n1 - 1) + n2 * 2 * p2 * (1 - p2) / (2 * n2 - 1)) / r
    n_c = (r * n_bar - (n1**2 + n2**2) / (r * n_bar)) / (r - 1)
    a = n_bar / n_c * (s_sq - 1 / (n_bar - 1) * (p_bar * (1 - p_bar) - (r - 1) / r * s_sq - h_bar / 4))
    b = n_bar / (n_bar - 1) * (p_bar * (1 - p_bar) - (r - 1) / r * s_sq - (2 * n_bar - 1) / (4 * n_bar) * h_bar)
    c = h_bar / 2
    return a, b, c


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    af_path = SCRIPT_DIR / 'allele_freq.tsv'
    rows = []
    with af_path.open('w') as f:
        f.write('snp_id\taf_popA\taf_popB\tn_popA\tn_popB\n')
        for i in range(N_SNPS):
            snp_id = f'rs{i+1:05d}'
            base = rng.uniform(0.05, 0.95)
            if i < 26:
                delta = rng.uniform(0.38, 0.62)
            else:
                delta = rng.uniform(0.01, 0.22)
            sign = 1 if (i % 2 == 0) else -1
            p1 = min(0.99, max(0.01, base + sign * delta / 2.0))
            p2 = min(0.99, max(0.01, base - sign * delta / 2.0))
            rows.append((snp_id, p1, p2))
            f.write(f'{snp_id}\t{p1:.6f}\t{p2:.6f}\t{N_POP_A}\t{N_POP_B}\n')

    nums, dens = [], []
    for _, p1, p2 in rows:
        a, b, c = wc_fst_components(p1, p2, N_POP_A, N_POP_B)
        nums.append(a)
        dens.append(a + b + c)

    mean_fst = sum(nums) / sum(dens)
    per_snp = [n / d if d > 0 else 0 for n, d in zip(nums, dens)]
    high_count = sum(1 for f in per_snp if f >= 0.25)

    summary = EXPECTED_DIR / 'fst_summary.tsv'
    with summary.open('w') as f:
        f.write('population_1\tpopulation_2\tmean_fst\thigh_fst_snp_count\n')
        f.write(f'popA\tpopB\t{mean_fst:.6f}\t{high_count}\n')

    print(f'Wrote: {af_path}')
    print(f'Wrote: {summary}')
    print(f'mean_fst={mean_fst:.6f}, high_fst_snp_count={high_count}')


if __name__ == '__main__':
    main()
