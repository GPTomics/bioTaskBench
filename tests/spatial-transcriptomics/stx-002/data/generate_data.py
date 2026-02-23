#!/usr/bin/env python3
'''Generate long-format spatial expression matrix with planted hotspot genes.'''

import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 52
GENES = ['G_HOT_A', 'G_HOT_B', 'G_HOT_C', 'G_HOT_D', 'G_BG_1', 'G_BG_2', 'G_BG_3', 'G_BG_4', 'G_BG_5', 'G_BG_6']
HOT = {'G_HOT_A', 'G_HOT_B', 'G_HOT_C', 'G_HOT_D'}


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    spots = []
    for gx in range(10):
        for gy in range(10):
            x = gx + rng.uniform(-0.1, 0.1)
            y = gy + rng.uniform(-0.1, 0.1)
            spots.append((f'spot_{gx:02d}_{gy:02d}', x, y))

    center = (4.5, 4.5)

    matrix = SCRIPT_DIR / 'expression_matrix.tsv'
    per_gene = {g: [] for g in GENES}
    center_dists = []
    by_spot = {}
    with matrix.open('w') as f:
        f.write('spot_id\tx\ty\tgene\texpression\n')
        for spot_id, x, y in spots:
            dist = ((x - center[0]) ** 2 + (y - center[1]) ** 2) ** 0.5
            center_dists.append((spot_id, dist))
            for gene in GENES:
                if gene in HOT:
                    expr = max(0.0, 8.0 - 1.8 * dist + rng.gauss(0, 0.5))
                else:
                    expr = max(0.0, 2.0 + rng.gauss(0, 0.7))
                per_gene[gene].append((spot_id, expr))
                f.write(f'{spot_id}\t{x:.6f}\t{y:.6f}\t{gene}\t{expr:.6f}\n')

    expected = EXPECTED_DIR / 'hotspot_genes.tsv'
    with expected.open('w') as f:
        f.write('gene\n')
        for gene in sorted(HOT):
            f.write(f'{gene}\n')

    dists = sorted(d for _, d in center_dists)
    inner_cut = dists[len(dists) // 3]
    outer_cut = dists[(2 * len(dists)) // 3]
    spot_to_dist = {sid: d for sid, d in center_dists}

    scores = []
    for gene in GENES:
        vals = per_gene[gene]
        inner = [expr for sid, expr in vals if spot_to_dist[sid] <= inner_cut]
        outer = [expr for sid, expr in vals if spot_to_dist[sid] >= outer_cut]
        score = (sum(inner) / len(inner)) - (sum(outer) / len(outer))
        scores.append((gene, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    top10 = EXPECTED_DIR / 'top10_hotspots.tsv'
    with top10.open('w') as f:
        f.write('gene\thotspot_score\trank\n')
        for i, (gene, score) in enumerate(scores[:10], 1):
            f.write(f'{gene}\t{score:.6f}\t{i}\n')

    print(f'Wrote: {matrix}')
    print(f'Wrote: {expected}')
    print(f'Wrote: {top10}')


if __name__ == '__main__':
    main()
