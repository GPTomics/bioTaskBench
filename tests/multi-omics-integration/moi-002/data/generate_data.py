#!/usr/bin/env python3
'''Generate dual-modality effect table and expected top integrated features.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 122
N_FEATURES = 280
TOP_K = 25


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    inp = SCRIPT_DIR / 'integrated_features.tsv'
    with inp.open('w') as f:
        f.write('feature_id\trna_effect\tprotein_effect\n')
        for i in range(N_FEATURES):
            fid = f'F{i+1:05d}'
            if i < TOP_K:
                rna = rng.uniform(2.2, 4.8) * (1 if i % 2 == 0 else -1)
                prot = rng.uniform(2.1, 4.6) * (1 if i % 2 == 0 else -1)
            else:
                rna = rng.uniform(-1.6, 1.6)
                prot = rng.uniform(-1.6, 1.6)
            score = (abs(rna) + abs(prot)) / 2.0
            rows.append((fid, rna, prot, score))
            f.write(f'{fid}\t{rna:.6f}\t{prot:.6f}\n')

    rows.sort(key=lambda x: x[3], reverse=True)
    exp = EXPECTED_DIR / 'top25_features.tsv'
    with exp.open('w') as f:
        f.write('feature_id\trna_effect\tprotein_effect\tintegrated_score\n')
        for fid, rna, prot, score in rows[:TOP_K]:
            f.write(f'{fid}\t{rna:.6f}\t{prot:.6f}\t{score:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')


if __name__ == '__main__':
    main()
