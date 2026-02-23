#!/usr/bin/env python3
'''Generate synthetic two-population allele frequencies and expected Fst summary.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 42
N_SNPS = 120


def fst_from_af(p1, p2):
    p_bar = (p1 + p2) / 2.0
    hs = (2 * p1 * (1 - p1) + 2 * p2 * (1 - p2)) / 2.0
    ht = 2 * p_bar * (1 - p_bar)
    if ht <= 0:
        return 0.0
    return max(0.0, (ht - hs) / ht)


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    af_path = SCRIPT_DIR / 'allele_freq.tsv'
    rows = []
    with af_path.open('w') as f:
        f.write('snp_id\taf_popA\taf_popB\n')
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
            f.write(f'{snp_id}\t{p1:.6f}\t{p2:.6f}\n')

    fsts = [fst_from_af(p1, p2) for _, p1, p2 in rows]
    mean_fst = sum(fsts) / len(fsts)
    high_count = sum(1 for x in fsts if x >= 0.25)

    summary = EXPECTED_DIR / 'fst_summary.tsv'
    with summary.open('w') as f:
        f.write('population_1\tpopulation_2\tmean_fst\thigh_fst_snp_count\n')
        f.write(f'popA\tpopB\t{mean_fst:.6f}\t{high_count}\n')

    print(f'Wrote: {af_path}')
    print(f'Wrote: {summary}')
    print(f'mean_fst={mean_fst:.6f}, high_fst_snp_count={high_count}')


if __name__ == '__main__':
    main()
