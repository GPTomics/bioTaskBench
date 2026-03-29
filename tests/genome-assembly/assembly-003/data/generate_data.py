#!/usr/bin/env python3
'''Generate synthetic contig error counts and expected high-error contig list.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 73
N_CONTIGS = 70
N_HIGH = 11


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    high = []
    inp = SCRIPT_DIR / 'contig_errors.tsv'
    with inp.open('w') as f:
        f.write('contig_id\tmismatches\taligned_bases\n')
        for i in range(N_CONTIGS):
            cid = f'contig_{i+1:03d}'
            aligned = rng.randint(15000, 90000)
            if i < N_HIGH:
                rate = rng.uniform(0.017, 0.032)
            else:
                rate = rng.uniform(0.002, 0.013)
            mismatches = max(1, int(aligned * rate))
            if mismatches / aligned >= 0.015:
                high.append(cid)
            f.write(f'{cid}\t{mismatches}\t{aligned}\n')

    exp = EXPECTED_DIR / 'high_error_contigs.tsv'
    with exp.open('w') as f:
        f.write('contig_id\n')
        for cid in high:
            f.write(f'{cid}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'high_error_contigs={len(high)}')


if __name__ == '__main__':
    main()
