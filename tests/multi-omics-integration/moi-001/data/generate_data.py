#!/usr/bin/env python3
'''Generate paired expression/methylation values and expected inverse association summary.'''

import math
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 121
N_GENES = 220


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

    expr, meth = [], []
    inp = SCRIPT_DIR / 'paired_gene_values.tsv'
    with inp.open('w') as f:
        f.write('gene_id\texpression\tmethylation\n')
        for i in range(N_GENES):
            e = rng.uniform(4.0, 14.0)
            m = max(0.01, min(0.99, 1.05 - 0.065 * e + rng.gauss(0, 0.06)))
            expr.append(e)
            meth.append(m)
            f.write(f'G{i+1:05d}\t{e:.6f}\t{m:.6f}\n')

    rho = spearman(expr, meth)
    exp = EXPECTED_DIR / 'association_summary.tsv'
    with exp.open('w') as f:
        f.write('feature_pair\tspearman_r\tpvalue\tdirection\n')
        f.write(f'expression_vs_methylation\t{rho:.6f}\t1e-12\tINVERSE\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'spearman_r={rho:.6f}')


if __name__ == '__main__':
    main()
