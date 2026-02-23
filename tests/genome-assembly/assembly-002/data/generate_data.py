#!/usr/bin/env python3
'''Generate synthetic overlap candidates and expected top join list.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 72
N_ROWS = 160
TOP_K = 15


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    inp = SCRIPT_DIR / 'overlap_candidates.tsv'
    with inp.open('w') as f:
        f.write('join_id\tleft_contig\tright_contig\toverlap_length\tidentity\n')
        for i in range(N_ROWS):
            join_id = f'join_{i+1:04d}'
            left = f'contig_{rng.randint(1,80):03d}'
            right = f'contig_{rng.randint(1,80):03d}'
            if i < TOP_K:
                overlap = rng.randint(26000, 70000)
                identity = rng.uniform(0.94, 0.995)
            else:
                overlap = rng.randint(4000, 26000)
                identity = rng.uniform(0.75, 0.96)
            score = overlap * identity
            rows.append((join_id, left, right, overlap, identity, score))
            f.write(f'{join_id}\t{left}\t{right}\t{overlap}\t{identity:.6f}\n')

    rows.sort(key=lambda x: x[5], reverse=True)
    exp = EXPECTED_DIR / 'top15_joins.tsv'
    with exp.open('w') as f:
        f.write('join_id\tleft_contig\tright_contig\toverlap_length\tidentity\tjoin_score\n')
        for join_id, left, right, overlap, identity, score in rows[:TOP_K]:
            f.write(f'{join_id}\t{left}\t{right}\t{overlap}\t{identity:.6f}\t{score:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')


if __name__ == '__main__':
    main()
