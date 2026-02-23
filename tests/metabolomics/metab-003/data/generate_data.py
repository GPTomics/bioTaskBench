#!/usr/bin/env python3
'''Generate synthetic pathway signal summaries and expected activated pathways.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 103
N_PATH = 70
N_ACT = 11


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    activated = []
    inp = SCRIPT_DIR / 'pathway_input.tsv'
    with inp.open('w') as f:
        f.write('pathway_id\tmean_case\tmean_control\n')
        for i in range(N_PATH):
            pid = f'PWY_{i+1:04d}'
            base = rng.uniform(5.0, 12.0)
            if i < N_ACT:
                delta = rng.uniform(1.6, 3.0)
            else:
                delta = rng.uniform(-1.2, 1.3)
            case = base + delta / 2.0
            ctrl = base - delta / 2.0
            if case - ctrl >= 1.5:
                activated.append(pid)
            f.write(f'{pid}\t{case:.6f}\t{ctrl:.6f}\n')

    exp = EXPECTED_DIR / 'activated_pathways.tsv'
    with exp.open('w') as f:
        f.write('pathway_id\n')
        for pid in activated:
            f.write(f'{pid}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'activated={len(activated)}')


if __name__ == '__main__':
    main()
