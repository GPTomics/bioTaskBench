#!/usr/bin/env python3
'''Generate synthetic single-sample metabolite feature intensities and expected summary.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 101
N_FEATURES = 300


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    vals = []
    inp = SCRIPT_DIR / 'feature_intensity.tsv'
    with inp.open('w') as f:
        f.write('feature_id\tlog2_intensity\n')
        for i in range(N_FEATURES):
            if i < 80:
                x = rng.uniform(13.0, 16.0)
            elif i < 130:
                x = rng.uniform(7.5, 9.8)
            else:
                x = rng.uniform(9.8, 13.0)
            vals.append(x)
            f.write(f'F{i+1:05d}\t{x:.6f}\n')

    mean_x = sum(vals) / len(vals)
    high_pct = 100.0 * sum(1 for x in vals if x >= 13.0) / len(vals)
    exp = EXPECTED_DIR / 'feature_summary.tsv'
    with exp.open('w') as f:
        f.write('sample_id\tfeature_count\tmean_log2_intensity\thigh_intensity_pct\n')
        f.write(f'sample_A\t{len(vals)}\t{mean_x:.6f}\t{high_pct:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'mean={mean_x:.6f} high_pct={high_pct:.6f}')


if __name__ == '__main__':
    main()
