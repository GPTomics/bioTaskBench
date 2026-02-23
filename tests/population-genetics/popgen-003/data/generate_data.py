#!/usr/bin/env python3
'''Generate synthetic genotype counts and expected significant HWE-violation SNPs.'''

import math
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 44
N_SNPS = 150
N_INDIV = 100
N_VIOLATING = 14


def hwe_chisq_pvalue(nAA, nAB, nBB):
    n = nAA + nAB + nBB
    if n == 0:
        return 1.0
    p = (2 * nAA + nAB) / (2 * n)
    q = 1 - p
    eAA = n * p * p
    eAB = 2 * n * p * q
    eBB = n * q * q
    eps = 1e-12
    chisq = ((nAA - eAA) ** 2) / max(eAA, eps) + ((nAB - eAB) ** 2) / max(eAB, eps) + ((nBB - eBB) ** 2) / max(eBB, eps)
    # df=1 chi-square survival function
    return math.erfc(math.sqrt(max(chisq, 0.0) / 2.0))


def multinomial_hw(rng, p, n):
    probs = [p * p, 2 * p * (1 - p), (1 - p) * (1 - p)]
    counts = [0, 0, 0]
    for _ in range(n):
        x = rng.random()
        if x < probs[0]:
            counts[0] += 1
        elif x < probs[0] + probs[1]:
            counts[1] += 1
        else:
            counts[2] += 1
    return counts


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    geno_path = SCRIPT_DIR / 'genotype_counts.tsv'
    sig_path = EXPECTED_DIR / 'significant_snps.tsv'

    significant = []
    with geno_path.open('w') as f:
        f.write('snp_id\tnAA\tnAB\tnBB\n')
        for i in range(N_SNPS):
            snp_id = f'rs{i+1:05d}'
            p = rng.uniform(0.08, 0.92)
            if i < N_VIOLATING:
                nAA, _, nBB = multinomial_hw(rng, p, N_INDIV)
                nAB = 0
            else:
                nAA, nAB, nBB = multinomial_hw(rng, p, N_INDIV)
            pval = hwe_chisq_pvalue(nAA, nAB, nBB)
            if pval < 0.01:
                significant.append((snp_id, pval))
            f.write(f'{snp_id}\t{nAA}\t{nAB}\t{nBB}\n')

    with sig_path.open('w') as f:
        f.write('snp_id\n')
        for snp_id, _ in significant:
            f.write(f'{snp_id}\n')

    print(f'Wrote: {geno_path}')
    print(f'Wrote: {sig_path}')
    print(f'significant={len(significant)}')


if __name__ == '__main__':
    main()
