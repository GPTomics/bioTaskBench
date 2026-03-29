#!/usr/bin/env python3
'''Generate spot-level coordinates with a planted x-axis expression gradient.'''

import random
from pathlib import Path

from scipy import stats

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 51
N_SPOTS = 144


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    spots_path = SCRIPT_DIR / 'spots.tsv'
    xs, exprs = [], []

    with spots_path.open('w') as f:
        f.write('spot_id\tx\ty\texpression\n')
        idx = 0
        for gx in range(12):
            for gy in range(12):
                idx += 1
                x = gx + rng.uniform(-0.1, 0.1)
                y = gy + rng.uniform(-0.1, 0.1)
                expr = 1.5 + 0.9 * gx + rng.gauss(0, 0.6)
                expr = max(0.0, expr)
                xs.append(x)
                exprs.append(expr)
                f.write(f'spot_{idx:03d}\t{x:.6f}\t{y:.6f}\t{expr:.6f}\n')

    result = stats.spearmanr(xs, exprs)
    rho, pval = result.statistic, result.pvalue
    expected = EXPECTED_DIR / 'gradient_summary.tsv'
    with expected.open('w') as f:
        f.write('gene\tspearman_r\tpvalue\tdirection\n')
        f.write(f'GENE_X\t{rho:.6f}\t{pval:.6e}\tUPRIGHT\n')

    print(f'Wrote: {spots_path}')
    print(f'Wrote: {expected}')
    print(f'spearman_r={rho:.6f} pvalue={pval:.6e}')


if __name__ == '__main__':
    main()
