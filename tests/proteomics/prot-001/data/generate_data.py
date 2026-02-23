#!/usr/bin/env python3
'''Generate synthetic single-sample protein intensities and expected summary.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 91
N_PROT = 320


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    vals = []
    inp = SCRIPT_DIR / 'protein_intensity.tsv'
    with inp.open('w') as f:
        f.write('protein_id\tlog2_intensity\n')
        for i in range(N_PROT):
            if i < 90:
                x = rng.uniform(26.0, 31.0)
            elif i < 140:
                x = rng.uniform(20.0, 23.0)
            else:
                x = rng.uniform(23.5, 26.5)
            vals.append(x)
            f.write(f'P{i+1:05d}\t{x:.6f}\n')

    mean_x = sum(vals) / len(vals)
    high_pct = 100.0 * sum(1 for x in vals if x >= 26.0) / len(vals)
    exp = EXPECTED_DIR / 'intensity_summary.tsv'
    with exp.open('w') as f:
        f.write('sample_id\tprotein_count\tmean_log2_intensity\thigh_intensity_pct\n')
        f.write(f'sample_A\t{len(vals)}\t{mean_x:.6f}\t{high_pct:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'mean_log2_intensity={mean_x:.6f} high_intensity_pct={high_pct:.6f}')


if __name__ == '__main__':
    main()
