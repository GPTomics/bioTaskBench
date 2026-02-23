#!/usr/bin/env python3
'''Generate spot-level coordinates with a planted x-axis expression gradient.'''

import math
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 51
N_SPOTS = 144


def rank(values):
    indexed = sorted((v, i) for i, v in enumerate(values))
    out = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][0] == indexed[i][0]:
            j += 1
        r = (i + 1 + j) / 2.0
        for k in range(i, j):
            _, idx = indexed[k]
            out[idx] = r
        i = j
    return out


def pearson(x, y):
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denx = math.sqrt(sum((a - mx) ** 2 for a in x))
    deny = math.sqrt(sum((b - my) ** 2 for b in y))
    if denx == 0 or deny == 0:
        return 0.0
    return num / (denx * deny)


def spearman(x, y):
    return pearson(rank(x), rank(y))


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

    rho = spearman(xs, exprs)
    expected = EXPECTED_DIR / 'gradient_summary.tsv'
    with expected.open('w') as f:
        f.write('gene\tspearman_r\tpvalue\tdirection\n')
        f.write(f'GENE_X\t{rho:.6f}\t1e-12\tUPRIGHT\n')

    print(f'Wrote: {spots_path}')
    print(f'Wrote: {expected}')
    print(f'spearman_r={rho:.6f}')


if __name__ == '__main__':
    main()
