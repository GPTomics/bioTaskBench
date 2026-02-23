#!/usr/bin/env python3
'''Generate synthetic differential metabolite feature means and expected top-30 list.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 102
N_FEATURES = 320
TOP_K = 30


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    inp = SCRIPT_DIR / 'differential_input.tsv'
    with inp.open('w') as f:
        f.write('feature_id\tcase_mean\tcontrol_mean\n')
        for i in range(N_FEATURES):
            fid = f'F{i+1:05d}'
            base = rng.uniform(8.0, 15.0)
            if i < TOP_K:
                delta = rng.uniform(2.0, 4.6)
            else:
                delta = rng.uniform(0.05, 1.4)
            sign = 1 if (i % 2 == 0) else -1
            case = base + sign * delta / 2.0
            ctrl = base - sign * delta / 2.0
            d = abs(case - ctrl)
            rows.append((fid, case, ctrl, d))
            f.write(f'{fid}\t{case:.6f}\t{ctrl:.6f}\n')

    rows.sort(key=lambda x: x[3], reverse=True)
    exp = EXPECTED_DIR / 'top30_features.tsv'
    with exp.open('w') as f:
        f.write('feature_id\tcase_mean\tcontrol_mean\tdelta_log2\n')
        for fid, case, ctrl, d in rows[:TOP_K]:
            f.write(f'{fid}\t{case:.6f}\t{ctrl:.6f}\t{d:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')


if __name__ == '__main__':
    main()
