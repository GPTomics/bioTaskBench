#!/usr/bin/env python3
'''Generate synthetic CpG beta values and expected global summary.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 81
N_CPG = 260


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    betas = []
    inp = SCRIPT_DIR / 'cpg_beta.tsv'
    with inp.open('w') as f:
        f.write('cpg_id\tbeta\n')
        for i in range(N_CPG):
            if i < 70:
                b = rng.uniform(0.8, 0.97)
            elif i < 120:
                b = rng.uniform(0.05, 0.25)
            else:
                b = rng.uniform(0.35, 0.75)
            betas.append(b)
            f.write(f'cg{i+1:06d}\t{b:.6f}\n')

    mean_beta = sum(betas) / len(betas)
    high_pct = 100.0 * sum(1 for b in betas if b >= 0.8) / len(betas)
    exp = EXPECTED_DIR / 'methylation_summary.tsv'
    with exp.open('w') as f:
        f.write('sample_id\tcpg_count\tmean_beta\thigh_methylation_pct\n')
        f.write(f'sample_A\t{len(betas)}\t{mean_beta:.6f}\t{high_pct:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'mean_beta={mean_beta:.6f} high_methylation_pct={high_pct:.3f}')


if __name__ == '__main__':
    main()
