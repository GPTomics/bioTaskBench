#!/usr/bin/env python3
'''Generate synthetic genotype matrix with planted ancestry outlier samples.

Validates that planted outliers are actually detectable via PCA with Patterson
et al. 2006 standardization.
'''

import math
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 45
N_SNPS = 500
N_PER_POP = 22
N_OUTLIERS = 6


def _clamp01(x):
    return max(0.01, min(0.99, x))


def _sample_dosage(rng, p):
    a1 = 1 if rng.random() < p else 0
    a2 = 1 if rng.random() < p else 0
    return a1 + a2


def _sample_ids(prefix, n):
    return [f'{prefix}_{i+1:03d}' for i in range(n)]


def _compute_pc1(matrix, n_samples, n_snps):
    '''Patterson et al. 2006 standardized PCA via power iteration.'''
    means = [sum(matrix[s][j] for s in range(n_samples)) / n_samples for j in range(n_snps)]
    p_vals = [m / 2.0 for m in means]
    scales = [math.sqrt(max(p * (1 - p), 1e-10)) for p in p_vals]

    std = [[0.0] * n_snps for _ in range(n_samples)]
    for s in range(n_samples):
        for j in range(n_snps):
            std[s][j] = (matrix[s][j] - means[j]) / scales[j]

    vec = [1.0 / math.sqrt(n_snps)] * n_snps
    for _ in range(100):
        proj = [sum(std[s][j] * vec[j] for j in range(n_snps)) for s in range(n_samples)]
        new_vec = [sum(std[s][j] * proj[s] for s in range(n_samples)) for j in range(n_snps)]
        norm = math.sqrt(sum(v * v for v in new_vec))
        vec = [v / norm for v in new_vec]

    pc1 = [sum(std[s][j] * vec[j] for j in range(n_snps)) for s in range(n_samples)]
    return pc1


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    group_a = _sample_ids('POP_A', N_PER_POP)
    group_b = _sample_ids('POP_B', N_PER_POP)
    group_c = _sample_ids('POP_C', N_PER_POP)
    outlier_ids = _sample_ids('OUT', N_OUTLIERS)

    samples = []
    for sid in group_a:
        samples.append((sid, -1.0))
    for sid in group_b:
        samples.append((sid, 0.00))
    for sid in group_c:
        samples.append((sid, 1.0))
    for i, sid in enumerate(outlier_ids):
        samples.append((sid, 5.5 if i < 3 else -5.5))

    snp_ids = [f'snp_{i+1:04d}' for i in range(N_SNPS)]
    base = [rng.uniform(0.15, 0.85) for _ in snp_ids]
    load = [rng.uniform(-0.30, 0.30) for _ in snp_ids]

    matrix = []
    out_path = SCRIPT_DIR / 'genotype_matrix.tsv'
    with out_path.open('w') as f:
        f.write('sample_id\t' + '\t'.join(snp_ids) + '\n')
        for sample_id, latent in samples:
            row = []
            for b, l in zip(base, load):
                p = _clamp01(b + l * latent)
                row.append(_sample_dosage(rng, p))
            matrix.append(row)
            f.write(sample_id + '\t' + '\t'.join(str(v) for v in row) + '\n')

    n_samples = len(samples)
    pc1 = _compute_pc1(matrix, n_samples, N_SNPS)
    mean_pc1 = sum(pc1) / n_samples
    std_pc1 = math.sqrt(sum((v - mean_pc1) ** 2 for v in pc1) / (n_samples - 1))
    z_scores = [(v - mean_pc1) / std_pc1 for v in pc1]
    abs_z = [abs(z) for z in z_scores]

    outlier_set = set(outlier_ids)
    detected = sum(1 for i, (sid, _) in enumerate(samples) if sid in outlier_set and abs_z[i] >= 2.0)
    total_flagged = sum(1 for z in abs_z if z >= 2.0)
    max_abs_z = max(abs_z)

    exp_path = EXPECTED_DIR / 'outlier_samples.tsv'
    with exp_path.open('w') as f:
        f.write('sample_id\n')
        for i, (sid, _) in enumerate(samples):
            if sid in outlier_set and abs_z[i] >= 2.0:
                f.write(f'{sid}\n')

    print(f'Wrote: {out_path}')
    print(f'Wrote: {exp_path}')
    print(f'samples={n_samples}, snps={N_SNPS}, planted_outliers={N_OUTLIERS}')
    print(f'PC1 validation: {detected}/{N_OUTLIERS} planted outliers detected at |z|>=2.0')
    print(f'Total flagged: {total_flagged}, max |z|: {max_abs_z:.2f}')
    assert detected >= 4, f'Only {detected} planted outliers detectable -- increase signal strength'
    assert max_abs_z >= 2.3, f'Max |z|={max_abs_z:.2f} too low -- increase signal strength'


if __name__ == '__main__':
    main()
