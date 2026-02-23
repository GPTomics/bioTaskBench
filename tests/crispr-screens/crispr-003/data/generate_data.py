#!/usr/bin/env python3
'''Generate synthetic control-guide LFC values and expected failing set IDs.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 113
SETS = ['CTRL_A','CTRL_B','CTRL_C','CTRL_D','CTRL_E','CTRL_F','CTRL_G']
GUIDES_PER_SET = 60
INSTABILITY = {'CTRL_A':0.10,'CTRL_B':0.14,'CTRL_C':0.22,'CTRL_D':0.28,'CTRL_E':0.12,'CTRL_F':0.33,'CTRL_G':0.09}


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    unstable_counts = {s: 0 for s in SETS}
    inp = SCRIPT_DIR / 'control_guides.tsv'
    with inp.open('w') as f:
        f.write('set_id\tguide_id\tlfc\n')
        for s in SETS:
            for i in range(GUIDES_PER_SET):
                gid = f'{s}_g{i+1:03d}'
                if rng.random() < INSTABILITY[s]:
                    mag = rng.uniform(1.0, 2.4)
                    sign = -1 if rng.random() < 0.7 else 1
                    lfc = sign * mag
                    unstable_counts[s] += 1
                else:
                    lfc = rng.uniform(-0.7, 0.7)
                f.write(f'{s}\t{gid}\t{lfc:.6f}\n')

    failing = [s for s in SETS if (100.0 * unstable_counts[s] / GUIDES_PER_SET) >= 20.0]
    exp = EXPECTED_DIR / 'failing_sets.tsv'
    with exp.open('w') as f:
        f.write('set_id\n')
        for s in failing:
            f.write(f'{s}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')
    print(f'failing_sets={len(failing)}')


if __name__ == '__main__':
    main()
