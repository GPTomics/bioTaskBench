#!/usr/bin/env python3
'''Generate synthetic ChIP-seq-like sequences with planted motifs for motif discovery benchmarking.

Uses deterministic random seeds so planted motifs are reproducible but unique to this benchmark.
Both HOMER and MEME reliably discover planted motifs in synthetic backgrounds (DREAM challenge approach).

Planted instances use the exact consensus with small per-base noise (10% mismatch per position)
to create realistic variability while keeping the consensus scannable.
'''

import random
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 4202
N_SEQUENCES = 300
SEQ_LENGTH = 500

MOTIF_SPECS = [
    {'name': 'primary', 'length': 12, 'n_planted': 250},
    {'name': 'secondary', 'length': 10, 'n_planted': 105},
    {'name': 'tertiary', 'length': 8, 'n_planted': 60},
]

BASE_FREQS = [0.29, 0.21, 0.21, 0.29]
BASES = 'ACGT'
MISMATCH_RATE = 0.02


def generate_consensus(rng, length):
    '''Generate a random consensus sequence avoiding low-complexity runs.'''
    seq = []
    for i in range(length):
        choices = list(BASES)
        if i >= 2 and seq[-1] == seq[-2]:
            choices = [b for b in choices if b != seq[-1]]
        seq.append(rng.choice(choices))
    return ''.join(seq)


def plant_instance(rng, consensus):
    '''Create a motif instance with small per-base noise.'''
    instance = list(consensus)
    for i in range(len(instance)):
        if rng.random() < MISMATCH_RATE:
            alts = [b for b in BASES if b != instance[i]]
            instance[i] = rng.choice(alts)
    return ''.join(instance)


def generate_background_seq(rng, length):
    return ''.join(rng.choices(BASES, weights=BASE_FREQS, k=length))


def reverse_complement(seq):
    comp = str.maketrans('ACGT', 'TGCA')
    return seq[::-1].translate(comp)


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    motifs = []
    for spec in MOTIF_SPECS:
        consensus = generate_consensus(rng, spec['length'])
        motifs.append({'consensus': consensus, 'n_planted': spec['n_planted'], 'name': spec['name'], 'length': spec['length']})
        print(f'  Motif {spec["name"]}: {consensus} (length={spec["length"]}, planted in {spec["n_planted"]}/{N_SEQUENCES})')

    sequences = [list(generate_background_seq(rng, SEQ_LENGTH)) for _ in range(N_SEQUENCES)]

    for motif in motifs:
        indices = rng.sample(range(N_SEQUENCES), motif['n_planted'])
        for idx in indices:
            instance = plant_instance(rng, motif['consensus'])
            if rng.random() < 0.3:
                instance = reverse_complement(instance)
            max_pos = SEQ_LENGTH - motif['length']
            pos = rng.randint(50, max_pos - 50)
            for j, base in enumerate(instance):
                sequences[idx][pos + j] = base

    fasta_path = SCRIPT_DIR / 'peaks.fa'
    with fasta_path.open('w') as f:
        for i, seq in enumerate(sequences):
            f.write(f'>seq_{i + 1:04d}\n{"".join(seq)}\n')

    planted_path = EXPECTED_DIR / 'planted_motifs.tsv'
    with planted_path.open('w') as f:
        f.write('motif_consensus\texpected_pct\n')
        for motif in motifs:
            pct = motif['n_planted'] / N_SEQUENCES * 100.0
            f.write(f'{motif["consensus"]}\t{pct:.1f}\n')

    for motif in motifs:
        cons = motif['consensus']
        rc = reverse_complement(cons)
        count = sum(1 for seq in sequences if cons in ''.join(seq) or rc in ''.join(seq))
        actual_pct = count / N_SEQUENCES * 100.0
        print(f'  Validation - {motif["name"]}: planted={motif["n_planted"]}, exact consensus scan={count} ({actual_pct:.1f}%)')

    size_kb = fasta_path.stat().st_size / 1024
    print(f'\nWrote: {fasta_path} ({N_SEQUENCES} sequences, {size_kb:.0f} KB)')
    print(f'Wrote: {planted_path}')


if __name__ == '__main__':
    main()
