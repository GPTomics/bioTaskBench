#!/usr/bin/env python3
'''Generate chipseq-005 benchmark data.

Hybrid design:
- Public substrate: ENCODE K562 H3K27ac ChIP-seq and matched input controls
  on hg19 chr21, discovered dynamically through the ENCODE API.
- Benchmark perturbations: deterministic read injection to create
  1) a global treated-condition H3K27ac shift,
  2) true distal enhancer gains,
  3) promoter-proximal decoys, and
  4) CNV-confounded loci boosted in both ChIP and input.

Generated benchmark inputs:
- control_rep1.tagAlign.gz
- control_rep2.tagAlign.gz
- treated_rep1.tagAlign.gz
- treated_rep2.tagAlign.gz
- control_input.tagAlign.gz
- treated_input.tagAlign.gz
- spikein_counts.tsv
- genes.gtf.gz
- blacklist.bed
- cnv_segments.bed

Generated expected outputs:
- expected/significant_enhancers.bed
- expected/normalization_truth.tsv
- expected/true_enhancer_truth.tsv

This script is intentionally deterministic and uses benchmark-defined truth
for the advanced task. The public data supplies realistic background read
distributions; the benchmark perturbations supply the hard quantitative traps.
'''

import csv
import gzip
import hashlib
import math
import random
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests


SCRIPT_DIR = Path(__file__).parent
TEST_DIR = SCRIPT_DIR.parent
EXPECTED_DIR = TEST_DIR / 'expected'

ASSEMBLY = 'hg19'
CHROM = 'chr21'
CHROM_SIZE = 48129895
EXPERIMENT_CHIP = 'ENCSR000AKP'
EXPERIMENT_INPUT = 'ENCSR000AKY'
GENCODE_URL = 'https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_19/gencode.v19.annotation.gtf.gz'
BLACKLIST_URL = 'https://raw.githubusercontent.com/Boyle-Lab/Blacklist/master/lists/hg19-blacklist.v2.bed.gz'
ENCODE_HOST = 'https://www.encodeproject.org'

RANDOM_SEED = 20260403
CONTROL_CHIP_READS = 180_000
TREATED_CHIP_READS = 140_000
CONTROL_INPUT_READS = 80_000
TREATED_INPUT_READS = 52_000

NUM_TRUE_ENHANCERS = 18
NUM_PROMOTER_DECOYS = 8
NUM_CNV_DECOYS = 6
NUM_BOUNDARY_ENHANCERS = 4
NUM_BOUNDARY_DECOYS = 4
GLOBAL_SHIFT_PEAKS = 180

GLOBAL_SHIFT_READS_PER_PEAK = 160
TRUE_ENHANCER_READS_PER_REP = 120
PROMOTER_DECOY_READS_PER_REP = 90
CNV_DECOY_CHIP_READS_PER_REP = 110
CNV_DECOY_INPUT_READS_PER_CONDITION = 220

SPIKEIN_READS = {
    'control_rep1': 52000,
    'control_rep2': 50000,
    'treated_rep1': 33500,
    'treated_rep2': 32000,
    'control_input': 51000,
    'treated_input': 33000,
}


def run(cmd, **kwargs):
    print(f'  $ {cmd}')
    return subprocess.run(cmd, shell=True, check=True, **kwargs)


def md5sum(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch_json(url, *, headers=None):
    resp = requests.get(url, headers=headers or {'accept': 'application/json'}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def select_encode_bams(experiment_accession, replicates):
    query = urlencode({
        'type': 'File',
        'dataset': f'/experiments/{experiment_accession}/',
        'file_format': 'bam',
        'output_type': 'unfiltered alignments',
        'assembly': ASSEMBLY,
        'status': 'released',
        'limit': 'all',
        'format': 'json',
    })
    payload = fetch_json(f'{ENCODE_HOST}/search/?{query}')
    files = payload.get('@graph', [])
    selected = {}
    for rep in replicates:
        for item in files:
            bioreps = item.get('biological_replicates') or []
            if bioreps != [rep]:
                continue
            href = item.get('href')
            if not href:
                continue
            selected[rep] = {
                'accession': item.get('accession', f'{experiment_accession}_rep{rep}'),
                'url': f'{ENCODE_HOST}{href}',
                'md5': item.get('md5sum'),
            }
            break
    missing = [str(rep) for rep in replicates if rep not in selected]
    if missing:
        raise RuntimeError(f'Could not resolve BAMs for {experiment_accession} replicates: {", ".join(missing)}')
    return selected


def download_file(url, path, expected_md5=None):
    if path.exists():
        print(f'  {path.name} already exists, skipping download')
    else:
        print(f'  Downloading {path.name}...')
        with requests.get(url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
    if expected_md5:
        actual = md5sum(path)
        if actual != expected_md5:
            raise RuntimeError(f'MD5 mismatch for {path.name}: expected {expected_md5}, got {actual}')


def bam_to_chr_tagalign(bam_path):
    cmd = f'samtools view -b -F 1804 {bam_path} {CHROM} | bedtools bamtobed -i stdin'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    reads = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 6:
            continue
        reads.append((parts[0], int(parts[1]), int(parts[2]), 'N', '1000', parts[5]))
    return reads


def deterministic_subsample(reads, n, rng):
    if len(reads) <= n:
        return list(reads)
    indices = sorted(rng.sample(range(len(reads)), n))
    return [reads[i] for i in indices]


def write_tagalign_gz(reads, path):
    with gzip.open(path, 'wt') as f:
        for chrom, start, end, name, score, strand in reads:
            f.write(f'{chrom}\t{start}\t{end}\t{name}\t{score}\t{strand}\n')


def call_macs3(tagalign_path, input_path, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    run(
        f'macs3 callpeak -t {tagalign_path} -c {input_path} '
        f'--format BED --gsize {CHROM_SIZE} --name baseline '
        f'--outdir {outdir} --qvalue 0.05 --nomodel --extsize 147'
    )
    return outdir / 'baseline_peaks.narrowPeak'


def read_bed(path):
    intervals = []
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            intervals.append((parts[0], int(parts[1]), int(parts[2]), parts[3:] if len(parts) > 3 else []))
    return intervals


def parse_gtf_tss(gtf_path):
    tss = {}
    gene_names = {}
    with gzip.open(gtf_path, 'rt') as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 9 or parts[2] != 'transcript' or parts[0] != CHROM:
                continue
            attrs = parts[8]
            gene_name = extract_attr(attrs, 'gene_name') or extract_attr(attrs, 'gene_id')
            if not gene_name:
                continue
            start = int(parts[3])
            end = int(parts[4])
            strand = parts[6]
            pos = start if strand == '+' else end
            tss.setdefault(parts[0], []).append(pos)
            gene_names.setdefault(parts[0], []).append((pos, gene_name))
    for chrom in tss:
        tss[chrom].sort()
        gene_names[chrom].sort()
    return tss, gene_names


def subset_chr21_gtf(src_path, dest_path):
    kept = 0
    with gzip.open(src_path, 'rt') as fin, gzip.open(dest_path, 'wt') as fout:
        for line in fin:
            if line.startswith('#'):
                fout.write(line)
                continue
            if line.startswith(CHROM + '\t'):
                fout.write(line)
                kept += 1
    return kept


def extract_attr(attrs, key):
    marker = f'{key} "'
    if marker not in attrs:
        return None
    tail = attrs.split(marker, 1)[1]
    return tail.split('"', 1)[0]


def overlaps(interval, forbidden):
    chrom, start, end = interval[:3]
    for f_chrom, f_start, f_end, _ in forbidden:
        if f_chrom != chrom:
            continue
        if not (end <= f_start or f_end <= start):
            return True
    return False


def count_overlaps(reads, chrom, start, end):
    return sum(1 for r_chrom, r_start, r_end, *_ in reads if r_chrom == chrom and not (r_end <= start or end <= r_start))


def median(values):
    vals = sorted(values)
    n = len(vals)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0


def compute_scale_factors():
    med = median(SPIKEIN_READS.values())
    return {sample_id: med / reads for sample_id, reads in SPIKEIN_READS.items()}


def distance_to_nearest_tss(interval, tss_positions):
    chrom, start, end = interval[:3]
    center = (start + end) / 2.0
    positions = tss_positions.get(chrom, [])
    if not positions:
        return None
    return min(abs(center - pos) for pos in positions)


def nearest_gene(interval, gene_tss):
    chrom, start, end = interval[:3]
    center = (start + end) / 2.0
    candidates = gene_tss.get(chrom, [])
    if not candidates:
        return 'NA', None
    pos, gene = min(candidates, key=lambda item: abs(center - item[0]))
    signed = int(round(center - pos))
    return gene, signed


def choose_peak_sets(peaks, blacklist, tss_positions, rng):
    eligible = []
    boundary = []
    promoters = []
    promoter_boundary = []
    for idx, peak in enumerate(peaks):
        chrom, start, end, extra = peak
        if chrom != CHROM or overlaps(peak, blacklist):
            continue
        width = end - start
        if width < 200 or width > 4000:
            continue
        dist = distance_to_nearest_tss(peak, tss_positions)
        score = float(extra[6]) if len(extra) > 6 else 10.0
        record = {'peak_id': f'pk_{idx + 1:04d}', 'chrom': chrom, 'start': start, 'end': end, 'score': score, 'dist': dist}
        if dist is not None and dist > 5000:
            eligible.append(record)
        elif dist is not None and 2000 < dist <= 5000:
            boundary.append(record)
        elif dist is not None and dist <= 1500:
            promoters.append(record)
        elif dist is not None and 1500 < dist <= 2000:
            promoter_boundary.append(record)

    eligible.sort(key=lambda x: x['score'], reverse=True)
    boundary.sort(key=lambda x: x['score'], reverse=True)
    promoters.sort(key=lambda x: x['score'], reverse=True)
    promoter_boundary.sort(key=lambda x: x['score'], reverse=True)
    if len(eligible) < (NUM_TRUE_ENHANCERS - NUM_BOUNDARY_ENHANCERS) + GLOBAL_SHIFT_PEAKS + NUM_CNV_DECOYS:
        raise RuntimeError('Not enough distal peaks to build chipseq-005 truth set')
    if len(boundary) < NUM_BOUNDARY_ENHANCERS:
        raise RuntimeError('Not enough 2-5 kb boundary peaks to build chipseq-005 truth set')
    if len(promoters) < (NUM_PROMOTER_DECOYS - NUM_BOUNDARY_DECOYS):
        raise RuntimeError('Not enough promoter peaks to build chipseq-005 promoter decoys')
    if len(promoter_boundary) < NUM_BOUNDARY_DECOYS:
        raise RuntimeError('Not enough 1.5-2 kb promoter-boundary peaks to build chipseq-005 decoys')

    true_enhancers = eligible[:NUM_TRUE_ENHANCERS - NUM_BOUNDARY_ENHANCERS] + boundary[:NUM_BOUNDARY_ENHANCERS]
    cnv_decoys = eligible[NUM_TRUE_ENHANCERS - NUM_BOUNDARY_ENHANCERS:NUM_TRUE_ENHANCERS - NUM_BOUNDARY_ENHANCERS + NUM_CNV_DECOYS]
    global_background = eligible[
        NUM_TRUE_ENHANCERS - NUM_BOUNDARY_ENHANCERS + NUM_CNV_DECOYS:
        NUM_TRUE_ENHANCERS - NUM_BOUNDARY_ENHANCERS + NUM_CNV_DECOYS + GLOBAL_SHIFT_PEAKS
    ]
    promoter_decoys = promoters[:NUM_PROMOTER_DECOYS - NUM_BOUNDARY_DECOYS] + promoter_boundary[:NUM_BOUNDARY_DECOYS]

    rng.shuffle(true_enhancers)
    rng.shuffle(cnv_decoys)
    rng.shuffle(global_background)
    rng.shuffle(promoter_decoys)
    return true_enhancers, promoter_decoys, cnv_decoys, global_background


def make_cnv_segments(cnv_peaks):
    segments = []
    for i, peak in enumerate(cnv_peaks, start=1):
        start = max(0, peak['start'] - 8000)
        end = min(CHROM_SIZE, peak['end'] + 8000)
        segments.append((CHROM, start, end, f'cnv_segment_{i:02d}'))
    return segments


def sample_read_within_peak(peak, rng):
    width = max(36, min(150, peak['end'] - peak['start']))
    max_start = max(peak['start'], peak['end'] - width)
    start = rng.randint(peak['start'], max_start)
    end = start + width
    strand = '+' if rng.random() < 0.5 else '-'
    return (peak['chrom'], start, end, 'N', '1000', strand)


def inject_reads(reads, peaks, reads_per_peak, rng):
    augmented = list(reads)
    for peak in peaks:
        for _ in range(reads_per_peak):
            augmented.append(sample_read_within_peak(peak, rng))
    return augmented


def write_simple_bed(intervals, path):
    with open(path, 'w') as f:
        for chrom, start, end, name in intervals:
            f.write(f'{chrom}\t{start}\t{end}\t{name}\n')


def write_spikein_counts(path):
    rows = []
    scale_factors = compute_scale_factors()
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['sample_id', 'group', 'spikein_reads'], delimiter='\t')
        writer.writeheader()
        for sample_id, reads in SPIKEIN_READS.items():
            group = 'treated' if sample_id.startswith('treated') else 'control'
            writer.writerow({'sample_id': sample_id, 'group': group, 'spikein_reads': reads})
            rows.append({
                'sample_id': sample_id,
                'group': group,
                'spikein_reads': reads,
                'scale_factor': scale_factors[sample_id],
                'normalization_basis': 'spikein'
            })
    truth_path = EXPECTED_DIR / 'normalization_truth.tsv'
    with open(truth_path, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=['sample_id', 'group', 'spikein_reads', 'scale_factor', 'normalization_basis'],
            delimiter='\t'
        )
        writer.writeheader()
        writer.writerows(rows)


def compute_peak_truth_metrics(peaks, chip_reads, input_reads):
    scale_factors = compute_scale_factors()
    metrics = {}
    for peak in peaks:
        chrom = peak['chrom']
        start = peak['start']
        end = peak['end']
        chip_counts = {sample: count_overlaps(reads, chrom, start, end) for sample, reads in chip_reads.items()}
        input_counts = {sample: count_overlaps(reads, chrom, start, end) for sample, reads in input_reads.items()}
        control_norm = [
            chip_counts['control_rep1'] * scale_factors['control_rep1'] - input_counts['control_input'] * scale_factors['control_input'],
            chip_counts['control_rep2'] * scale_factors['control_rep2'] - input_counts['control_input'] * scale_factors['control_input'],
        ]
        treated_norm = [
            chip_counts['treated_rep1'] * scale_factors['treated_rep1'] - input_counts['treated_input'] * scale_factors['treated_input'],
            chip_counts['treated_rep2'] * scale_factors['treated_rep2'] - input_counts['treated_input'] * scale_factors['treated_input'],
        ]
        treated_mean = max(sum(treated_norm) / len(treated_norm) + 0.5, 0.5)
        control_mean = max(sum(control_norm) / len(control_norm) + 0.5, 0.5)
        log2fc = math.log2(treated_mean / control_mean)
        metrics[(chrom, start, end)] = {
            'chip_counts': chip_counts,
            'input_counts': input_counts,
            'log2fc': log2fc,
            'treated_support': sum(1 for sample in ('treated_rep1', 'treated_rep2') if chip_counts[sample] > 0),
            'control_support': sum(1 for sample in ('control_rep1', 'control_rep2') if chip_counts[sample] > 0),
        }
    return metrics


def write_truth_outputs(true_enhancers, gene_tss, chip_reads, input_reads):
    sig_bed = EXPECTED_DIR / 'significant_enhancers.bed'
    truth_tsv = EXPECTED_DIR / 'true_enhancer_truth.tsv'
    truth_metrics = compute_peak_truth_metrics(true_enhancers, chip_reads, input_reads)

    with open(sig_bed, 'w') as bed, open(truth_tsv, 'w', newline='') as truth:
        truth_writer = csv.DictWriter(
            truth,
            fieldnames=['chr', 'start', 'end', 'peak_id', 'log2fc', 'nearest_gene', 'distance_to_tss', 'treated_support', 'control_support'],
            delimiter='\t'
        )
        truth_writer.writeheader()

        for i, peak in enumerate(true_enhancers, start=1):
            peak_id = f'enh_true_{i:02d}'
            gene, signed_dist = nearest_gene((peak['chrom'], peak['start'], peak['end']), gene_tss)
            metric = truth_metrics[(peak['chrom'], peak['start'], peak['end'])]
            bed.write(f"{peak['chrom']}\t{peak['start']}\t{peak['end']}\t{peak_id}\n")
            truth_writer.writerow({
                'chr': peak['chrom'],
                'start': peak['start'],
                'end': peak['end'],
                'peak_id': peak_id,
                'log2fc': f'{metric["log2fc"]:.6f}',
                'nearest_gene': gene,
                'distance_to_tss': signed_dist,
                'treated_support': metric['treated_support'],
                'control_support': metric['control_support'],
            })

def main():
    print('=' * 60)
    print('chipseq-005: Advanced H3K27ac Differential Enhancer Data Generation')
    print('=' * 60 + '\n')

    required = ['samtools', 'bedtools', 'macs3']
    missing = [tool for tool in required if not shutil.which(tool)]
    if missing:
        sys.exit(f'Missing required tools: {", ".join(missing)}')

    rng = random.Random(RANDOM_SEED)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    print('Step 1: Resolve public ENCODE BAMs')
    chip_files = select_encode_bams(EXPERIMENT_CHIP, [1, 2])
    input_files = select_encode_bams(EXPERIMENT_INPUT, [1, 2])

    print('\nStep 2: Download source BAMs')
    bam_dir = SCRIPT_DIR / '_downloads'
    bam_dir.mkdir(exist_ok=True)
    resolved = {}
    for label, meta in {
        'chip_rep1': chip_files[1],
        'chip_rep2': chip_files[2],
        'input_rep1': input_files[1],
        'input_rep2': input_files[2],
    }.items():
        bam_path = bam_dir / f'{meta["accession"]}.bam'
        download_file(meta['url'], bam_path, meta.get('md5'))
        resolved[label] = bam_path

    print('\nStep 3: Download benchmark support files')
    genes_path = SCRIPT_DIR / 'genes.gtf.gz'
    genes_full_path = SCRIPT_DIR / '_gencode_full.gtf.gz'
    blacklist_gz = SCRIPT_DIR / 'blacklist.bed.gz'
    download_file(GENCODE_URL, genes_full_path)
    download_file(BLACKLIST_URL, blacklist_gz)
    kept_gtf_lines = subset_chr21_gtf(genes_full_path, genes_path)
    with gzip.open(blacklist_gz, 'rt') as fin, open(SCRIPT_DIR / 'blacklist.bed', 'w') as fout:
        for line in fin:
            if line.startswith(CHROM + '\t'):
                fout.write(line)
    blacklist_gz.unlink(missing_ok=True)
    genes_full_path.unlink(missing_ok=True)

    print('\nStep 4: Extract chr21 tagAlign from public substrate')
    chip_rep1_reads = bam_to_chr_tagalign(resolved['chip_rep1'])
    chip_rep2_reads = bam_to_chr_tagalign(resolved['chip_rep2'])
    input_rep1_reads = bam_to_chr_tagalign(resolved['input_rep1'])
    input_rep2_reads = bam_to_chr_tagalign(resolved['input_rep2'])

    control_rep1 = deterministic_subsample(chip_rep1_reads, CONTROL_CHIP_READS, rng)
    control_rep2 = deterministic_subsample(chip_rep2_reads, CONTROL_CHIP_READS, rng)
    control_input = deterministic_subsample(input_rep1_reads, CONTROL_INPUT_READS, rng)

    pooled_control = SCRIPT_DIR / '_pooled_control.tagAlign.gz'
    pooled_input = SCRIPT_DIR / '_pooled_input.tagAlign.gz'
    write_tagalign_gz(control_rep1 + control_rep2, pooled_control)
    write_tagalign_gz(control_input + deterministic_subsample(input_rep2_reads, CONTROL_INPUT_READS, rng), pooled_input)

    print('\nStep 5: Call baseline peaks and choose truth regions')
    peak_path = call_macs3(pooled_control, pooled_input, SCRIPT_DIR / '_baseline_peaks')
    baseline_peaks = read_bed(peak_path)
    blacklist = read_bed(SCRIPT_DIR / 'blacklist.bed')
    tss_positions, gene_tss = parse_gtf_tss(genes_path)
    true_enhancers, promoter_decoys, cnv_decoys, global_background = choose_peak_sets(
        baseline_peaks, blacklist, tss_positions, rng
    )

    print('\nStep 6: Synthesize benchmark treatment effects')
    treated_rep1 = deterministic_subsample(chip_rep1_reads, TREATED_CHIP_READS, rng)
    treated_rep2 = deterministic_subsample(chip_rep2_reads, TREATED_CHIP_READS, rng)
    treated_input = deterministic_subsample(input_rep2_reads, TREATED_INPUT_READS, rng)

    treated_rep1 = inject_reads(treated_rep1, global_background, GLOBAL_SHIFT_READS_PER_PEAK, rng)
    treated_rep2 = inject_reads(treated_rep2, global_background, GLOBAL_SHIFT_READS_PER_PEAK, rng)
    treated_rep1 = inject_reads(treated_rep1, true_enhancers, TRUE_ENHANCER_READS_PER_REP, rng)
    treated_rep2 = inject_reads(treated_rep2, true_enhancers, TRUE_ENHANCER_READS_PER_REP, rng)
    treated_rep1 = inject_reads(treated_rep1, promoter_decoys, PROMOTER_DECOY_READS_PER_REP, rng)
    treated_rep2 = inject_reads(treated_rep2, promoter_decoys, PROMOTER_DECOY_READS_PER_REP, rng)
    treated_rep1 = inject_reads(treated_rep1, cnv_decoys, CNV_DECOY_CHIP_READS_PER_REP, rng)
    treated_rep2 = inject_reads(treated_rep2, cnv_decoys, CNV_DECOY_CHIP_READS_PER_REP, rng)
    treated_input = inject_reads(treated_input, cnv_decoys, CNV_DECOY_INPUT_READS_PER_CONDITION, rng)

    print('\nStep 7: Write benchmark inputs')
    write_tagalign_gz(control_rep1, SCRIPT_DIR / 'control_rep1.tagAlign.gz')
    write_tagalign_gz(control_rep2, SCRIPT_DIR / 'control_rep2.tagAlign.gz')
    write_tagalign_gz(treated_rep1, SCRIPT_DIR / 'treated_rep1.tagAlign.gz')
    write_tagalign_gz(treated_rep2, SCRIPT_DIR / 'treated_rep2.tagAlign.gz')
    write_tagalign_gz(control_input, SCRIPT_DIR / 'control_input.tagAlign.gz')
    write_tagalign_gz(treated_input, SCRIPT_DIR / 'treated_input.tagAlign.gz')

    cnv_segments = make_cnv_segments(cnv_decoys)
    write_simple_bed(cnv_segments, SCRIPT_DIR / 'cnv_segments.bed')
    write_spikein_counts(SCRIPT_DIR / 'spikein_counts.tsv')

    print('\nStep 8: Write benchmark truth files')
    chip_reads = {
        'control_rep1': control_rep1,
        'control_rep2': control_rep2,
        'treated_rep1': treated_rep1,
        'treated_rep2': treated_rep2,
    }
    input_reads = {
        'control_input': control_input,
        'treated_input': treated_input,
    }
    write_truth_outputs(true_enhancers, gene_tss, chip_reads, input_reads)

    print('\nStep 9: Cleanup large intermediates')
    pooled_control.unlink(missing_ok=True)
    pooled_input.unlink(missing_ok=True)
    shutil.rmtree(SCRIPT_DIR / '_baseline_peaks', ignore_errors=True)
    shutil.rmtree(bam_dir, ignore_errors=True)

    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'  True distal enhancers : {NUM_TRUE_ENHANCERS}')
    print(f'  Promoter decoys       : {NUM_PROMOTER_DECOYS}')
    print(f'  CNV decoys            : {NUM_CNV_DECOYS}')
    print(f'  Global-shift peaks    : {GLOBAL_SHIFT_PEAKS}')
    print(f'  chr21 GTF lines kept  : {kept_gtf_lines}')
    print('  Expected truth files  : significant_enhancers.bed, normalization_truth.tsv, true_enhancer_truth.tsv')


if __name__ == '__main__':
    main()
