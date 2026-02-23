#!/usr/bin/env python3
'''Generate synthetic gene essentiality scores and expected top-20 essential genes.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 112
N_GENES = 260
TOP_K = 20


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    inp = SCRIPT_DIR / 'gene_scores.tsv'
    with inp.open('w') as f:
        f.write('gene\tscore\n')
        for i in range(N_GENES):
            gene = f'GENE_{i+1:04d}'
            if i < TOP_K:
                score = rng.uniform(-5.3, -2.4)
            else:
                score = rng.uniform(-1.6, 2.2)
            rows.append((gene, score))
            f.write(f'{gene}\t{score:.6f}\n')

    rows.sort(key=lambda x: x[1])
    exp = EXPECTED_DIR / 'top20_essential.tsv'
    with exp.open('w') as f:
        f.write('gene\tscore\trank\n')
        for rank, (gene, score) in enumerate(rows[:TOP_K], 1):
            f.write(f'{gene}\t{score:.6f}\t{rank}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')


if __name__ == '__main__':
    main()
