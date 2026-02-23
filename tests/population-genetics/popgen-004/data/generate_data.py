#!/usr/bin/env python3
'''Generate synthetic genotype matrix with planted ancestry outlier samples.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 45
N_SNPS = 60


def _clamp01(x):
    return max(0.01, min(0.99, x))


def _sample_dosage(rng, p):
    a1 = 1 if rng.random() < p else 0
    a2 = 1 if rng.random() < p else 0
    return a1 + a2


def _sample_ids(prefix, n):
    return [f'{prefix}_{i+1:03d}' for i in range(n)]


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    group_a = _sample_ids('POP_A', 22)
    group_b = _sample_ids('POP_B', 22)
    group_c = _sample_ids('POP_C', 22)
    outliers = _sample_ids('OUT', 6)

    samples = []
    for sid in group_a:
        samples.append((sid, -0.85))
    for sid in group_b:
        samples.append((sid, 0.00))
    for sid in group_c:
        samples.append((sid, 0.85))
    for i, sid in enumerate(outliers):
        samples.append((sid, 1.65 if i < 3 else -1.65))

    snp_ids = [f'snp_{i+1:04d}' for i in range(N_SNPS)]

    base = [rng.uniform(0.15, 0.85) for _ in snp_ids]
    load = [rng.uniform(-0.18, 0.18) for _ in snp_ids]

    out_path = SCRIPT_DIR / 'genotype_matrix.tsv'
    with out_path.open('w') as f:
        f.write('sample_id\t' + '\t'.join(snp_ids) + '\n')
        for sample_id, latent in samples:
            vals = []
            for b, l in zip(base, load):
                p = _clamp01(b + l * latent)
                vals.append(str(_sample_dosage(rng, p)))
            f.write(sample_id + '\t' + '\t'.join(vals) + '\n')

    exp_path = EXPECTED_DIR / 'outlier_samples.tsv'
    with exp_path.open('w') as f:
        f.write('sample_id\n')
        for sid in outliers:
            f.write(f'{sid}\n')

    print(f'Wrote: {out_path}')
    print(f'Wrote: {exp_path}')
    print(f'samples={len(samples)}, snps={len(snp_ids)}, planted_outliers={len(outliers)}')


if __name__ == '__main__':
    main()
