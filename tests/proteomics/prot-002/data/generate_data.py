#!/usr/bin/env python3
'''Generate synthetic differential protein means and expected top-25 list.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 92
N_PROT = 300
TOP_K = 25


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    inp = SCRIPT_DIR / 'differential_input.tsv'
    with inp.open('w') as f:
        f.write('protein_id\tcase_mean\tcontrol_mean\n')
        for i in range(N_PROT):
            pid = f'P{i+1:05d}'
            base = rng.uniform(21.0, 30.0)
            if i < TOP_K:
                delta = rng.uniform(2.8, 5.2)
            else:
                delta = rng.uniform(0.05, 1.6)
            sign = 1 if (i % 2 == 0) else -1
            case = base + sign * delta / 2.0
            ctrl = base - sign * delta / 2.0
            d = abs(case - ctrl)
            rows.append((pid, case, ctrl, d))
            f.write(f'{pid}\t{case:.6f}\t{ctrl:.6f}\n')

    rows.sort(key=lambda x: x[3], reverse=True)
    exp = EXPECTED_DIR / 'top25_proteins.tsv'
    with exp.open('w') as f:
        f.write('protein_id\tcase_mean\tcontrol_mean\tdelta_log2\n')
        for pid, case, ctrl, d in rows[:TOP_K]:
            f.write(f'{pid}\t{case:.6f}\t{ctrl:.6f}\t{d:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')


if __name__ == '__main__':
    main()
