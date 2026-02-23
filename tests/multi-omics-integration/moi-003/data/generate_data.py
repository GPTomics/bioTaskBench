#!/usr/bin/env python3
'''Generate pathway signals from two omics layers and expected concordant pathways.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 123
N_PATHWAYS = 72
N_CONCORDANT = 11


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    concordant = []
    inp = SCRIPT_DIR / 'pathway_signals.tsv'
    with inp.open('w') as f:
        f.write('pathway_id\trna_signal\tprotein_signal\n')
        for i in range(N_PATHWAYS):
            pid = f'PATH_{i+1:04d}'
            if i < N_CONCORDANT:
                rna = rng.uniform(1.2, 3.2)
                prot = rng.uniform(1.1, 3.0)
            else:
                rna = rng.uniform(-1.5, 2.0)
                prot = rng.uniform(-1.5, 2.0)
            score = min(rna, prot)
            if score >= 1.0:
                concordant.append(pid)
            f.write(f'{pid}\t{rna:.6f}\t{prot:.6f}\n')

    exp = EXPECTED_DIR / 'concordant_pathways.tsv'
    with exp.open('w') as f:
        f.write('pathway_id\n')
        for pid in concordant:
            f.write(f'{pid}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'concordant_pathways={len(concordant)}')


if __name__ == '__main__':
    main()
