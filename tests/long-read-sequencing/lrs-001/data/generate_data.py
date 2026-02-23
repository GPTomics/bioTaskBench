#!/usr/bin/env python3
'''Generate synthetic long-read lengths and expected summary statistics.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 61
N_READS = 200


def n50(lengths):
    total = sum(lengths)
    half = total / 2.0
    running = 0
    for L in sorted(lengths, reverse=True):
        running += L
        if running >= half:
            return L
    return 0


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    lengths = []
    for i in range(N_READS):
        base = rng.lognormvariate(9.2, 0.45)
        L = int(max(1500, min(50000, base)))
        lengths.append(L)

    inp = SCRIPT_DIR / 'read_lengths.tsv'
    with inp.open('w') as f:
        f.write('read_id\tlength\n')
        for i, L in enumerate(lengths, 1):
            f.write(f'read_{i:04d}\t{L}\n')

    mean_len = sum(lengths) / len(lengths)
    n50_val = n50(lengths)
    exp = EXPECTED_DIR / 'read_stats.tsv'
    with exp.open('w') as f:
        f.write('sample_id\tread_count\tmean_read_length\tn50\n')
        f.write(f'sample_A\t{len(lengths)}\t{mean_len:.6f}\t{n50_val}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'read_count={len(lengths)} mean={mean_len:.2f} n50={n50_val}')


if __name__ == '__main__':
    main()
