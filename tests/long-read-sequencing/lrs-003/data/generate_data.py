#!/usr/bin/env python3
'''Generate simulated long-read alignments with extended CIGAR strings (=/X/I/D/S) for error profiling.

Uses =/X ops instead of M to distinguish sequence matches from mismatches, following PacBio BAM spec.
Error rate = (mismatch + insertion + deletion) / (seq_match + mismatch + insertion + deletion).
Soft-clips are reported separately but excluded from error rate.
'''

import random
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'
RANDOM_SEED = 63
N_READS = 150
N_HIGH_ERROR = 25
ERROR_THRESHOLD = 0.10


def build_cigar_from_ops(ops):
    return ''.join(f'{count}{op}' for count, op in ops if count > 0)


def generate_cigar_high_error(rng, target_length, target_error_rate):
    ops = []
    error_bp = int(target_length * target_error_rate)
    aligned_bp = target_length - error_bp

    sc_front = rng.randint(max(1, error_bp // 8), max(2, error_bp // 4))
    sc_back = rng.randint(max(1, error_bp // 8), max(2, error_bp // 4))

    core_error = error_bp - sc_front - sc_back
    if core_error < 3:
        core_error = 3
        sc_back = max(1, sc_back - 1)

    mismatch_frac = rng.uniform(0.3, 0.5)
    mismatch_bp = max(1, int(core_error * mismatch_frac))
    indel_budget = core_error - mismatch_bp
    if indel_budget < 1:
        indel_budget = 1
        mismatch_bp = core_error - 1

    ops.append((sc_front, 'S'))

    n_events = rng.randint(4, 8)
    event_sizes_mm = _distribute(rng, mismatch_bp, n_events)
    event_sizes_indel = _distribute(rng, indel_budget, n_events)
    match_segments = _distribute(rng, aligned_bp, n_events + 1)

    for i in range(n_events):
        if match_segments[i] > 0:
            ops.append((match_segments[i], '='))
        if event_sizes_mm[i] > 0:
            ops.append((event_sizes_mm[i], 'X'))
        if event_sizes_indel[i] > 0:
            ops.append((event_sizes_indel[i], rng.choice(['I', 'D'])))

    if match_segments[-1] > 0:
        ops.append((match_segments[-1], '='))

    ops.append((sc_back, 'S'))
    return build_cigar_from_ops(ops)


def generate_cigar_low_error(rng, target_length, target_error_rate):
    ops = []
    error_bp = max(2, int(target_length * target_error_rate))
    match_bp = target_length - error_bp

    mismatch_frac = rng.uniform(0.3, 0.5)
    mismatch_bp = max(1, int(error_bp * mismatch_frac))
    indel_budget = error_bp - mismatch_bp
    if indel_budget < 1:
        indel_budget = 1
        mismatch_bp = error_bp - 1

    n_events = rng.randint(2, 5)
    event_sizes_mm = _distribute(rng, mismatch_bp, n_events)
    event_sizes_indel = _distribute(rng, indel_budget, n_events)
    match_segments = _distribute(rng, match_bp, n_events + 1)

    for i in range(n_events):
        if match_segments[i] > 0:
            ops.append((match_segments[i], '='))
        if event_sizes_mm[i] > 0:
            ops.append((event_sizes_mm[i], 'X'))
        if event_sizes_indel[i] > 0:
            ops.append((event_sizes_indel[i], rng.choice(['I', 'D'])))

    if match_segments[-1] > 0:
        ops.append((match_segments[-1], '='))

    return build_cigar_from_ops(ops)


def _distribute(rng, total, n):
    if n <= 0 or total <= 0:
        return [0] * max(n, 0)
    sizes = [rng.randint(1, max(1, total // n * 2)) for _ in range(n)]
    s = sum(sizes)
    sizes = [max(1, int(x * total / s)) for x in sizes]
    diff = total - sum(sizes)
    sizes[-1] += diff
    if sizes[-1] < 0:
        sizes[-1] = 0
    return sizes


def parse_cigar(cigar):
    totals = {'=': 0, 'X': 0, 'I': 0, 'D': 0, 'S': 0}
    for count, op in re.findall(r'(\d+)([=XIDS])', cigar):
        totals[op] += int(count)
    return totals['='], totals['X'], totals['I'], totals['D'], totals['S']


def main():
    rng = random.Random(RANDOM_SEED)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    reads = []
    high_error_indices = set(rng.sample(range(N_READS), N_HIGH_ERROR))

    for i in range(N_READS):
        read_id = f'read_{i + 1:04d}'
        aligned_length = rng.randint(800, 15000)

        if i in high_error_indices:
            target_error = rng.uniform(0.12, 0.25)
            cigar = generate_cigar_high_error(rng, aligned_length, target_error)
        else:
            target_error = rng.uniform(0.02, 0.06)
            cigar = generate_cigar_low_error(rng, aligned_length, target_error)

        seq_match, mismatch, ins, d, s = parse_cigar(cigar)
        aligned_total = seq_match + mismatch + ins + d
        error_rate = (mismatch + ins + d) / aligned_total if aligned_total > 0 else 0.0
        high_error = 'TRUE' if error_rate >= ERROR_THRESHOLD else 'FALSE'

        reads.append({
            'read_id': read_id, 'cigar': cigar, 'aligned_length': aligned_length,
            'seq_match_bp': seq_match, 'mismatch_bp': mismatch, 'insertion_bp': ins,
            'deletion_bp': d, 'softclip_bp': s, 'error_rate': error_rate, 'high_error': high_error,
        })

    rng.shuffle(reads)

    input_file = SCRIPT_DIR / 'read_alignments.tsv'
    with input_file.open('w') as f:
        f.write('read_id\tcigar\taligned_length\n')
        for r in reads:
            f.write(f'{r["read_id"]}\t{r["cigar"]}\t{r["aligned_length"]}\n')

    reads_sorted = sorted(reads, key=lambda r: r['error_rate'], reverse=True)

    error_summary_file = EXPECTED_DIR / 'error_summary.tsv'
    with error_summary_file.open('w') as f:
        f.write('read_id\tseq_match_bp\tmismatch_bp\tinsertion_bp\tdeletion_bp\tsoftclip_bp\terror_rate\thigh_error\n')
        for r in reads_sorted:
            f.write(f'{r["read_id"]}\t{r["seq_match_bp"]}\t{r["mismatch_bp"]}\t{r["insertion_bp"]}\t{r["deletion_bp"]}\t{r["softclip_bp"]}\t{r["error_rate"]:.6f}\t{r["high_error"]}\n')

    high_error_reads = [r for r in reads_sorted if r['high_error'] == 'TRUE']
    high_error_file = EXPECTED_DIR / 'high_error_reads.tsv'
    with high_error_file.open('w') as f:
        f.write('read_id\n')
        for r in high_error_reads:
            f.write(f'{r["read_id"]}\n')

    n_high = sum(1 for r in reads if r['high_error'] == 'TRUE')
    n_low = N_READS - n_high
    error_rates = [r['error_rate'] for r in reads]
    high_rates = [r['error_rate'] for r in reads if r['high_error'] == 'TRUE']
    low_rates = [r['error_rate'] for r in reads if r['high_error'] == 'FALSE']

    print(f'Wrote: {input_file}')
    print(f'Wrote: {error_summary_file}')
    print(f'Wrote: {high_error_file}')
    print(f'Total reads: {N_READS}')
    print(f'High-error reads (>=10%): {n_high}')
    print(f'Normal reads (<10%): {n_low}')
    print(f'Overall error rate: mean={sum(error_rates)/len(error_rates):.4f}, min={min(error_rates):.4f}, max={max(error_rates):.4f}')
    if high_rates:
        print(f'High-error group: mean={sum(high_rates)/len(high_rates):.4f}, min={min(high_rates):.4f}, max={max(high_rates):.4f}')
    if low_rates:
        print(f'Normal group: mean={sum(low_rates)/len(low_rates):.4f}, min={min(low_rates):.4f}, max={max(low_rates):.4f}')


if __name__ == '__main__':
    main()
