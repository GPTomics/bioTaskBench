#!/usr/bin/env python3
'''Generate clustered spots with planted marker enrichment in selected clusters.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 53
CLUSTERS = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7']
ENRICHED = {'C2', 'C5'}


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    out = SCRIPT_DIR / 'spots_clustered.tsv'
    with out.open('w') as f:
        f.write('spot_id\tx\ty\tcluster\tmarker_expression\n')
        idx = 0
        for c_i, cluster in enumerate(CLUSTERS):
            cx = (c_i % 4) * 4.0
            cy = (c_i // 4) * 4.0
            for _ in range(18):
                idx += 1
                x = cx + rng.uniform(-0.8, 0.8)
                y = cy + rng.uniform(-0.8, 0.8)
                if cluster in ENRICHED:
                    expr = max(0.0, 6.7 + rng.gauss(0, 0.8))
                else:
                    expr = max(0.0, 2.2 + rng.gauss(0, 0.7))
                f.write(f'spot_{idx:03d}\t{x:.6f}\t{y:.6f}\t{cluster}\t{expr:.6f}\n')

    expected = EXPECTED_DIR / 'enriched_clusters.tsv'
    with expected.open('w') as f:
        f.write('cluster\n')
        for cluster in sorted(ENRICHED):
            f.write(f'{cluster}\n')

    print(f'Wrote: {out}')
    print(f'Wrote: {expected}')


if __name__ == '__main__':
    main()
