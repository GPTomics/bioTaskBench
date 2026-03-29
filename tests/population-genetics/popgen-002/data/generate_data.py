#!/usr/bin/env python3
'''Generate synthetic two-population allele frequencies and expected top-20 SNPs by delta AF.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 43
N_SNPS = 200
TOP_K = 20


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    af_path = SCRIPT_DIR / 'allele_freq.tsv'
    with af_path.open('w') as f:
        f.write('snp_id\taf_popA\taf_popB\n')
        for i in range(N_SNPS):
            snp_id = f'rs{i+1:05d}'
            base = rng.uniform(0.05, 0.95)
            if i < TOP_K:
                delta = rng.uniform(0.58, 0.90)
            else:
                delta = rng.uniform(0.01, 0.35)
            sign = 1 if (i % 2 == 0) else -1
            p1 = min(0.99, max(0.01, base + sign * delta / 2.0))
            p2 = min(0.99, max(0.01, base - sign * delta / 2.0))
            d = abs(p1 - p2)
            rows.append((snp_id, p1, p2, d))
            f.write(f'{snp_id}\t{p1:.6f}\t{p2:.6f}\n')

    rows_sorted = sorted(rows, key=lambda x: x[3], reverse=True)
    top_path = EXPECTED_DIR / 'top20_snps.tsv'
    with top_path.open('w') as f:
        f.write('snp_id\taf_popA\taf_popB\tdelta_af\n')
        for snp_id, p1, p2, d in rows_sorted[:TOP_K]:
            f.write(f'{snp_id}\t{p1:.6f}\t{p2:.6f}\t{d:.6f}\n')

    print(f'Wrote: {af_path}')
    print(f'Wrote: {top_path}')


if __name__ == '__main__':
    main()
