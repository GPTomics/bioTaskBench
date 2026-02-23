#!/usr/bin/env python3
'''Generate synthetic region-level methylation and expected hypermethylated region IDs.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 83
N_REGIONS = 75
N_HYPER = 12


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    hyper = []
    inp = SCRIPT_DIR / 'region_methylation.tsv'
    with inp.open('w') as f:
        f.write('region_id\tmean_case\tmean_control\n')
        for i in range(N_REGIONS):
            rid = f'region_{i+1:04d}'
            base = rng.uniform(0.15, 0.75)
            if i < N_HYPER:
                delta = rng.uniform(0.22, 0.40)
            else:
                delta = rng.uniform(-0.12, 0.16)
            mean_case = min(0.99, max(0.01, base + delta / 2.0))
            mean_control = min(0.99, max(0.01, base - delta / 2.0))
            if mean_case - mean_control >= 0.20:
                hyper.append(rid)
            f.write(f'{rid}\t{mean_case:.6f}\t{mean_control:.6f}\n')

    exp = EXPECTED_DIR / 'hypermethylated_regions.tsv'
    with exp.open('w') as f:
        f.write('region_id\n')
        for rid in hyper:
            f.write(f'{rid}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'hypermethylated_regions={len(hyper)}')


if __name__ == '__main__':
    main()
