#!/usr/bin/env python3
'''Generate synthetic case/control CpG betas and expected top differential CpGs.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 82
N_CPG = 280
TOP_K = 30


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    inp = SCRIPT_DIR / 'dmc_input.tsv'
    with inp.open('w') as f:
        f.write('cpg_id\tbeta_case\tbeta_control\n')
        for i in range(N_CPG):
            cid = f'cg{i+1:06d}'
            base = rng.uniform(0.1, 0.9)
            if i < TOP_K:
                delta = rng.uniform(0.40, 0.70)
            else:
                delta = rng.uniform(0.01, 0.22)
            sign = 1 if (i % 2 == 0) else -1
            bc = min(0.99, max(0.01, base + sign * delta / 2.0))
            bt = min(0.99, max(0.01, base - sign * delta / 2.0))
            d = abs(bc - bt)
            rows.append((cid, bc, bt, d))
            f.write(f'{cid}\t{bc:.6f}\t{bt:.6f}\n')

    rows.sort(key=lambda x: x[3], reverse=True)
    exp = EXPECTED_DIR / 'top30_dmc.tsv'
    with exp.open('w') as f:
        f.write('cpg_id\tbeta_case\tbeta_control\tdelta_beta\n')
        for cid, bc, bt, d in rows[:TOP_K]:
            f.write(f'{cid}\t{bc:.6f}\t{bt:.6f}\t{d:.6f}\n')

    print(f'Wrote: {inp}')
    print(f'Wrote: {exp}')


if __name__ == '__main__':
    main()
