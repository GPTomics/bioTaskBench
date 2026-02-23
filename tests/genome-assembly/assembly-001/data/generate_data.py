#!/usr/bin/env python3
'''Generate synthetic contig lengths and expected assembly summary stats.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 71
N_CONTIGS = 60


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
    for i in range(N_CONTIGS):
        L = int(max(3000, min(90000, rng.lognormvariate(10.2, 0.6))))
        lengths.append(L)

    inp = SCRIPT_DIR / 'contig_lengths.tsv'
    with inp.open('w') as f:
        f.write('contig_id\tlength\n')
        for i, L in enumerate(lengths, 1):
            f.write(f'contig_{i:03d}\t{L}\n')

    total = sum(lengths)
    n50_val = n50(lengths)
    exp = EXPECTED_DIR / 'assembly_stats.tsv'
    with exp.open('w') as f:
        f.write('assembly_id\tcontig_count\ttotal_length\tn50\n')
        f.write(f'asm_A\t{len(lengths)}\t{total}\t{n50_val}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'contig_count={len(lengths)} total_length={total} n50={n50_val}')


if __name__ == '__main__':
    main()
