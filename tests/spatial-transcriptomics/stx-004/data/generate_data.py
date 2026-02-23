#!/usr/bin/env python3
'''Generate spatial spot cell-types with one immune-rich quadrant and expected hotspot niche set.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 54
SPOTS_PER_QUADRANT = 40

# Planted immune probabilities by quadrant.
IMMUNE_PROB = {
    'NE': 0.78,
    'NW': 0.30,
    'SE': 0.24,
    'SW': 0.18,
}


def _rand_coord(rng, positive):
    base = rng.uniform(0.2, 5.0)
    return base if positive else -base


def _niche(x, y):
    if x >= 0 and y >= 0:
        return 'NE'
    if x < 0 and y >= 0:
        return 'NW'
    if x >= 0 and y < 0:
        return 'SE'
    return 'SW'


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    out = SCRIPT_DIR / 'spots_celltypes.tsv'
    by_niche = {'NE': [0, 0], 'NW': [0, 0], 'SE': [0, 0], 'SW': [0, 0]}  # immune_count, total

    with out.open('w') as f:
        f.write('spot_id\tx\ty\tcell_type\n')
        idx = 0
        for niche in ['NE', 'NW', 'SE', 'SW']:
            for _ in range(SPOTS_PER_QUADRANT):
                idx += 1
                x = _rand_coord(rng, positive=(niche in {'NE', 'SE'})) + rng.uniform(-0.15, 0.15)
                y = _rand_coord(rng, positive=(niche in {'NE', 'NW'})) + rng.uniform(-0.15, 0.15)
                true_niche = _niche(x, y)
                is_immune = rng.random() < IMMUNE_PROB[true_niche]
                cell_type = 'Immune' if is_immune else 'Stromal'

                by_niche[true_niche][1] += 1
                if is_immune:
                    by_niche[true_niche][0] += 1

                f.write(f'spot_{idx:03d}\t{x:.6f}\t{y:.6f}\t{cell_type}\n')

    hotspots = []
    for niche in ['NE', 'NW', 'SE', 'SW']:
        immune_count, total = by_niche[niche]
        frac = (immune_count / total) if total else 0.0
        if frac >= 0.55:
            hotspots.append(niche)

    expected = EXPECTED_DIR / 'hotspot_niches.tsv'
    with expected.open('w') as f:
        f.write('niche\n')
        for niche in hotspots:
            f.write(f'{niche}\n')

    print(f'Wrote: {out}')
    print(f'Wrote: {expected}')
    print('immune fractions:')
    for niche in ['NE', 'NW', 'SE', 'SW']:
        immune_count, total = by_niche[niche]
        frac = (immune_count / total) if total else 0.0
        print(f'  {niche}: {immune_count}/{total} = {frac:.3f}')


if __name__ == '__main__':
    main()
