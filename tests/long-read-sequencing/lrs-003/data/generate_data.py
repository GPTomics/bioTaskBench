#!/usr/bin/env python3
'''Generate per-position consensus support values and expected segment summary.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 63
N_POS = 180
SEGMENT_ID = 'seg_001'


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    supports = []
    for i in range(N_POS):
        if i < 10:
            s = rng.uniform(0.60, 0.79)
        else:
            s = rng.uniform(0.90, 0.99)
        supports.append(s)

    inp = SCRIPT_DIR / 'consensus_support.tsv'
    with inp.open('w') as f:
        f.write('segment_id\tposition\tsupport\n')
        for i, s in enumerate(supports, 1):
            f.write(f'{SEGMENT_ID}\t{i}\t{s:.6f}\n')

    mean_support = sum(supports) / len(supports)
    low_count = sum(1 for s in supports if s < 0.80)
    passed = 'TRUE' if (mean_support >= 0.90 and low_count <= 12) else 'FALSE'

    exp = EXPECTED_DIR / 'consensus_summary.tsv'
    with exp.open('w') as f:
        f.write('segment_id\tmean_support\tlow_support_count\tpass\n')
        f.write(f'{SEGMENT_ID}\t{mean_support:.6f}\t{low_count}\t{passed}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'mean_support={mean_support:.6f} low_support_count={low_count} pass={passed}')


if __name__ == '__main__':
    main()
