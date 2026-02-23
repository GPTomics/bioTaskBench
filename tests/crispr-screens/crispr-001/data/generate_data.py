#!/usr/bin/env python3
'''Generate synthetic guide-level LFC values and expected dropout summary.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 111
N_GUIDES = 320


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    lfcs = []
    inp = SCRIPT_DIR / 'guide_lfc.tsv'
    with inp.open('w') as f:
        f.write('guide_id\tlfc\n')
        for i in range(N_GUIDES):
            if i < 90:
                x = rng.uniform(-2.4, -1.0)
            elif i < 130:
                x = rng.uniform(0.6, 1.3)
            else:
                x = rng.uniform(-0.9, 0.5)
            lfcs.append(x)
            f.write(f'g{i+1:05d}\t{x:.6f}\n')

    mean_lfc = sum(lfcs) / len(lfcs)
    dropout_pct = 100.0 * sum(1 for x in lfcs if x <= -1.0) / len(lfcs)
    exp = EXPECTED_DIR / 'guide_summary.tsv'
    with exp.open('w') as f:
        f.write('sample_id\tguide_count\tmean_lfc\tstrong_dropout_pct\n')
        f.write(f'sample_A\t{len(lfcs)}\t{mean_lfc:.6f}\t{dropout_pct:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'mean_lfc={mean_lfc:.6f} strong_dropout_pct={dropout_pct:.6f}')


if __name__ == '__main__':
    main()
