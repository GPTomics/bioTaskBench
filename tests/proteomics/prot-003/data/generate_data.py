#!/usr/bin/env python3
'''Generate synthetic protein matrix with sample-level missingness and expected high-missing sample IDs.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 93
N_PROT = 240
SAMPLES = ['S1','S2','S3','S4','S5','S6','S7','S8','S9']
RATES = {'S1':0.08,'S2':0.12,'S3':0.18,'S4':0.22,'S5':0.31,'S6':0.15,'S7':0.27,'S8':0.10,'S9':0.06}


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    inp = SCRIPT_DIR / 'protein_matrix.tsv'
    missing_counts = {s: 0 for s in SAMPLES}
    with inp.open('w') as f:
        f.write('protein_id\t' + '\t'.join(SAMPLES) + '\n')
        for i in range(N_PROT):
            vals = []
            for s in SAMPLES:
                if rng.random() < RATES[s]:
                    vals.append('NA')
                    missing_counts[s] += 1
                else:
                    vals.append(f'{rng.uniform(20.0,31.0):.4f}')
            f.write(f'P{i+1:05d}\t' + '\t'.join(vals) + '\n')

    high = [s for s in SAMPLES if (100.0 * missing_counts[s] / N_PROT) >= 20.0]
    exp = EXPECTED_DIR / 'high_missing_samples.tsv'
    with exp.open('w') as f:
        f.write('sample_id\n')
        for s in high:
            f.write(f'{s}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'high_missing_samples={len(high)}')


if __name__ == '__main__':
    main()
