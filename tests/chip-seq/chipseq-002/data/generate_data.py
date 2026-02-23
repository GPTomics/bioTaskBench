#!/usr/bin/env python3
'''Download ENCODE CTCF ChIP-seq peaks from K562, extract summit-centered
FASTA sequences via UCSC REST API.

Requirements: curl, Python requests library

Source: ENCODE experiment ENCSR000EGM (CTCF ChIP-seq, K562, GRCh38)
Peaks: ENCFF396BZQ (IDR optimal thresholded peaks, narrowPeak format)
'''

import gzip, hashlib, shutil, subprocess, sys, time
from pathlib import Path
import requests

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'

PEAKS_ACCESSION = 'ENCFF396BZQ'
PEAKS_URL = f'https://www.encodeproject.org/files/{PEAKS_ACCESSION}/@@download/{PEAKS_ACCESSION}.bed.gz'
EXPECTED_MD5 = 'ec6d58713b0306f762dbc4cab091df71'

NUM_PEAKS = 300
WINDOW_HALF = 250  # 500bp total centered on summit
UCSC_API = 'https://api.genome.ucsc.edu/getData/sequence'


def md5sum(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def download_peaks():
    gz_path = SCRIPT_DIR / f'{PEAKS_ACCESSION}.bed.gz'
    if not gz_path.exists():
        print(f'  Downloading {PEAKS_ACCESSION}.bed.gz...')
        subprocess.run(['curl', '-L', '--fail', '-o', str(gz_path), PEAKS_URL], check=True)
    actual = md5sum(gz_path)
    assert actual == EXPECTED_MD5, f'MD5 mismatch: expected {EXPECTED_MD5}, got {actual}'
    print(f'  MD5 verified: {actual}')
    return gz_path


def parse_narrowpeak(gz_path, n=NUM_PEAKS):
    '''Parse narrowPeak file, return top N peaks sorted by signal value (descending).'''
    peaks = []
    with gzip.open(gz_path, 'rt') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            fields = line.strip().split('\t')
            chrom = fields[0]
            start = int(fields[1])
            signal = float(fields[6])
            summit_offset = int(fields[9])
            summit = start + summit_offset
            peaks.append((chrom, summit, signal))

    peaks.sort(key=lambda x: -x[2])
    selected = peaks[:n]
    chroms = len(set(p[0] for p in selected))
    print(f'  Total peaks in file: {len(peaks)}')
    print(f'  Selected top {len(selected)} by signal, spanning {chroms} chromosomes')
    return selected


def fetch_sequences(peaks):
    '''Fetch FASTA sequences centered on summits from UCSC REST API.'''
    sequences = []
    for i, (chrom, summit, signal) in enumerate(peaks):
        start = max(0, summit - WINDOW_HALF)
        end = summit + WINDOW_HALF
        resp = requests.get(UCSC_API, params={'genome': 'hg38', 'chrom': chrom, 'start': start, 'end': end})
        resp.raise_for_status()
        seq = resp.json()['dna'].upper()
        sequences.append((f'{chrom}:{start}-{end}', seq))
        if (i + 1) % 50 == 0:
            print(f'  Fetched {i + 1}/{len(peaks)} sequences')
        time.sleep(0.05)
    return sequences


def write_fasta(sequences, output_path):
    with open(output_path, 'w') as f:
        for name, seq in sequences:
            f.write(f'>{name}\n{seq}\n')


def main():
    print('=' * 60)
    print('chipseq-002: CTCF Motif Analysis Data Generation')
    print('=' * 60 + '\n')

    missing = [t for t in ['curl'] if not shutil.which(t)]
    if missing:
        sys.exit(f'Missing required tools: {", ".join(missing)}')

    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    fasta_out = SCRIPT_DIR / 'peaks.fa'

    # Step 1: Download peaks
    print('Step 1: Download CTCF IDR optimal peaks')
    gz_path = download_peaks()

    # Step 2: Select top peaks
    print('\nStep 2: Select top peaks by signal value')
    peaks = parse_narrowpeak(gz_path, NUM_PEAKS)

    # Step 3: Fetch sequences
    print('\nStep 3: Fetch summit sequences from UCSC API')
    sequences = fetch_sequences(peaks)

    # Step 4: Write FASTA
    print('\nStep 4: Write peaks.fa')
    write_fasta(sequences, fasta_out)
    size_kb = fasta_out.stat().st_size / 1024
    print(f'  {len(sequences)} sequences, {size_kb:.0f} KB')

    # Cleanup
    gz_path.unlink()

    # Summary
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'  peaks.fa: {len(sequences)} sequences, {WINDOW_HALF * 2}bp each, {size_kb:.0f} KB')
    print(f'  Expected primary motif: CTCF (JASPAR MA0139.1)')
    print(f'  Expected target enrichment: >80% of sequences')


if __name__ == '__main__':
    main()
