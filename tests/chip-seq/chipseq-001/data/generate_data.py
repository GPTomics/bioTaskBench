#!/usr/bin/env python3
'''Download ENCODE H3K4me3 ChIP-seq data for K562, filter to chr21,
convert to tagAlign, and generate multi-caller consensus ground truth.

Requirements: curl, samtools, bedtools, macs3, HOMER (makeTagDirectory, findPeaks)

Source: ENCODE experiment ENCSR668LDD (H3K4me3 ChIP-seq, K562, GRCh38)
Control: ENCODE experiment ENCSR000AKY (input control, K562, GRCh38)
'''

import hashlib, subprocess, gzip, shutil, sys, tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'

TREATMENT_ACCESSION = 'ENCFF855ZMQ'  # H3K4me3 ChIP-seq rep1 BAM
CONTROL_ACCESSION = 'ENCFF226FKB'    # Input control rep1 BAM
ENCODE_URL = 'https://www.encodeproject.org/files/{acc}/@@download/{acc}.bam'
EXPECTED_MD5 = {
    'ENCFF855ZMQ': '008f6edc7e3bef6bd9eecb6cfeb29783',
    'ENCFF226FKB': '88b3b0d5259a43b442d81e529f5641e8',
}

MIN_READS = 400_000
CHR21_SIZE = 46709983


def run(cmd, **kwargs):
    print(f'  $ {cmd}')
    return subprocess.run(cmd, shell=True, check=True, **kwargs)


def md5sum(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def download_bam(accession):
    path = SCRIPT_DIR / f'{accession}.bam'
    if path.exists():
        print(f'  {path.name} already exists, skipping download')
    else:
        url = ENCODE_URL.format(acc=accession)
        print(f'  Downloading {accession}.bam...')
        run(f'curl -L --fail -o {path} {url}')
    if accession in EXPECTED_MD5:
        actual = md5sum(path)
        assert actual == EXPECTED_MD5[accession], f'MD5 mismatch for {accession}: expected {EXPECTED_MD5[accession]}, got {actual}'
        print(f'  MD5 verified: {actual}')
    run(f'samtools index {path}')
    return path


def bam_to_chr21_tagalign(bam_path, output_path):
    '''Extract chr21 reads from BAM, convert to tagAlign format.
    Uses all chr21 reads (no subsampling unless file size exceeds budget).
    '''
    cmd = f'samtools view -b -F 1804 {bam_path} chr21 | bedtools bamtobed -i stdin'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    raw_lines = [l for l in result.stdout.strip().split('\n') if l]
    n_total = len(raw_lines)
    print(f'  chr21 reads (filtered): {n_total}')

    if n_total < MIN_READS:
        print(f'  WARNING: {n_total} reads is below the {MIN_READS} floor')

    with gzip.open(output_path, 'wt') as f:
        for line in raw_lines:
            fields = line.split('\t')
            f.write(f'{fields[0]}\t{fields[1]}\t{fields[2]}\tN\t1000\t{fields[5]}\n')

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f'  Wrote {output_path.name}: {n_total} reads, {size_mb:.1f} MB')
    return n_total


def call_peaks_macs3(treatment, control, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    run(
        f'macs3 callpeak -t {treatment} -c {control} '
        f'--format BED --gsize {CHR21_SIZE} '
        f'--name macs3 --outdir {outdir} --qvalue 0.05 '
        f'--nomodel --extsize 147'
    )
    peaks = outdir / 'macs3_peaks.narrowPeak'
    with open(peaks) as f:
        n = sum(1 for _ in f)
    print(f'  MACS3: {n} peaks')
    return peaks


def call_peaks_homer(treatment, control, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    tag_t, tag_c = outdir / 'tags_treatment', outdir / 'tags_control'
    run(f'makeTagDirectory {tag_t} {treatment} -format bed')
    run(f'makeTagDirectory {tag_c} {control} -format bed')

    peaks_txt = outdir / 'peaks.txt'
    run(f'findPeaks {tag_t} -i {tag_c} -style histone -gsize {CHR21_SIZE} -o {peaks_txt}')

    bed_path = outdir / 'homer_peaks.bed'
    with open(peaks_txt) as fin, open(bed_path, 'w') as fout:
        for line in fin:
            if line.startswith('#') or not line.strip():
                continue
            fields = line.strip().split('\t')
            if len(fields) < 5:
                continue
            score = fields[7] if len(fields) > 7 else '0'
            fout.write(f'{fields[1]}\t{fields[2]}\t{fields[3]}\t{fields[0]}\t{score}\n')

    with open(bed_path) as f:
        n = sum(1 for _ in f)
    print(f'  HOMER: {n} peaks')
    return bed_path


def build_consensus(macs3_peaks, homer_peaks, output_path, slop=500):
    '''Find peaks called by both MACS3 and HOMER within {slop}bp.'''
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        chromsizes = tmpdir / 'chromsizes'
        chromsizes.write_text(f'chr21\t{CHR21_SIZE}\n')

        macs3_bed = tmpdir / 'macs3.bed'
        homer_bed = tmpdir / 'homer.bed'
        run(f'cut -f1-3 {macs3_peaks} | bedtools sort -i stdin > {macs3_bed}')
        run(f'cut -f1-3 {homer_peaks} | bedtools sort -i stdin > {homer_bed}')

        # MACS3 peaks within {slop}bp of any HOMER peak (consensus = both callers agree)
        run(f'bedtools window -a {macs3_bed} -b {homer_bed} -w {slop} | cut -f1-3 | sort -k1,1 -k2,2n | uniq > {output_path}')

    with open(output_path) as f:
        n = sum(1 for _ in f)
    print(f'  Consensus (MACS3 peaks with HOMER support): {n} peaks')
    return n


def main():
    print('=' * 60)
    print('chipseq-001: H3K4me3 Peak Calling Data Generation')
    print('=' * 60 + '\n')

    required = ['samtools', 'bedtools', 'macs3', 'makeTagDirectory', 'findPeaks']
    missing = [t for t in required if not shutil.which(t)]
    if missing:
        sys.exit(f'Missing required tools: {", ".join(missing)}')

    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    treatment_out = SCRIPT_DIR / 'treatment.tagAlign.gz'
    control_out = SCRIPT_DIR / 'control.tagAlign.gz'
    consensus_out = EXPECTED_DIR / 'consensus_peaks.bed'

    # Step 1: Download
    print('Step 1: Download ENCODE BAMs')
    treatment_bam = download_bam(TREATMENT_ACCESSION)
    control_bam = download_bam(CONTROL_ACCESSION)

    # Step 2: Convert to chr21 tagAlign
    print('\nStep 2: Extract chr21 reads -> tagAlign')
    n_treatment = bam_to_chr21_tagalign(treatment_bam, treatment_out)
    n_control = bam_to_chr21_tagalign(control_bam, control_out)

    t_size = treatment_out.stat().st_size / 1024 / 1024
    c_size = control_out.stat().st_size / 1024 / 1024
    if t_size + c_size > 10:
        print(f'\n  WARNING: combined size {t_size + c_size:.1f} MB exceeds 10MB budget')

    # Step 3: Ground truth
    print('\nStep 3: Ground truth (MACS3 + HOMER consensus)')
    gt_dir = SCRIPT_DIR / '_ground_truth'
    gt_dir.mkdir(exist_ok=True)

    print('\n  --- MACS3 ---')
    macs3_peaks = call_peaks_macs3(treatment_out, control_out, gt_dir / 'macs3')

    print('\n  --- HOMER ---')
    homer_peaks = call_peaks_homer(treatment_out, control_out, gt_dir / 'homer')

    print('\n  --- Consensus ---')
    n_consensus = build_consensus(macs3_peaks, homer_peaks, consensus_out)

    # Step 4: Cleanup
    print('\nStep 4: Cleanup')
    for bam in [treatment_bam, control_bam]:
        bam.unlink()
        Path(str(bam) + '.bai').unlink(missing_ok=True)
    shutil.rmtree(gt_dir)
    print('  Removed BAMs and intermediate files')

    # Summary
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'  treatment.tagAlign.gz : {n_treatment:,} reads, {t_size:.1f} MB')
    print(f'  control.tagAlign.gz   : {n_control:,} reads, {c_size:.1f} MB')
    print(f'  consensus_peaks.bed   : {n_consensus} peaks')
    lo, hi = max(10, int(n_consensus * 0.3)), int(n_consensus * 3)
    print(f'\n  Suggested peak_count range for task.json: [{lo}, {hi}]')
    print('  Update the range after reviewing the consensus peaks.')


if __name__ == '__main__':
    main()
