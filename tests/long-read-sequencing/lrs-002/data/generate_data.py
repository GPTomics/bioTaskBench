#!/usr/bin/env python3
'''Generate read-level insertion/deletion summaries and expected top-25 by indel burden.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 62
N_READS = 240
TOP_K = 25


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    inp = SCRIPT_DIR / 'read_alignment_summary.tsv'
    with inp.open('w') as f:
        f.write('read_id\tinsertion_count\tdeletion_count\n')
        for i in range(N_READS):
            rid = f'read_{i+1:04d}'
            if i < TOP_K:
                ins = rng.randint(18, 70)
                dele = rng.randint(18, 65)
            else:
                ins = rng.randint(0, 20)
                dele = rng.randint(0, 18)
            burden = ins + dele
            rows.append((rid, ins, dele, burden))
            f.write(f'{rid}\t{ins}\t{dele}\n')

    rows.sort(key=lambda x: x[3], reverse=True)
    exp = EXPECTED_DIR / 'top25_indel_reads.tsv'
    with exp.open('w') as f:
        f.write('read_id\tinsertion_count\tdeletion_count\tindel_burden\n')
        for rid, ins, dele, burden in rows[:TOP_K]:
            f.write(f'{rid}\t{ins}\t{dele}\t{burden}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')


if __name__ == '__main__':
    main()
