#!/usr/bin/env python3
'''Download GENCODE v44 gene annotations, generate synthetic H3K4me3 peaks
at known genomic positions, compute ground truth annotations.

Requirements: curl, Python only (no bioinformatics tools needed)

Source: GENCODE v44 basic annotation (GRCh38/hg38)
'''

import gzip, random, shutil, subprocess, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPECTED_DIR = SCRIPT_DIR.parent / 'expected'

GENCODE_URL = 'https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_44/gencode.v44.basic.annotation.gtf.gz'
RANDOM_SEED = 42
PROMOTER_WINDOW = 2000
PEAK_WIDTH_RANGE = (200, 800)
NUM_PROMOTER = 85
NUM_EXONIC = 5
NUM_INTRONIC = 15
NUM_INTERGENIC = 15


def download_gtf():
    gz_path = SCRIPT_DIR / 'gencode.v44.basic.annotation.gtf.gz'
    if not gz_path.exists():
        print('  Downloading GENCODE v44 basic annotation...')
        subprocess.run(['curl', '-L', '--fail', '-o', str(gz_path), GENCODE_URL], check=True)
    size_mb = gz_path.stat().st_size / 1024 / 1024
    print(f'  Downloaded: {size_mb:.1f} MB')
    return gz_path


def parse_gtf_attrs(attr_string):
    attrs = {}
    for item in attr_string.strip().split(';'):
        item = item.strip()
        if not item:
            continue
        key, _, val = item.partition(' ')
        attrs[key] = val.strip('"')
    return attrs


def parse_chr21_genes(gtf_gz_path):
    genes = {}
    with gzip.open(gtf_gz_path, 'rt') as f:
        for line in f:
            if line.startswith('#'):
                continue
            fields = line.strip().split('\t')
            if fields[0] != 'chr21':
                continue
            attrs = parse_gtf_attrs(fields[8])
            if attrs.get('gene_type') != 'protein_coding':
                continue
            gene_id = attrs.get('gene_id', '').split('.')[0]
            gene_name = attrs.get('gene_name', '')
            strand = fields[6]
            start, end = int(fields[3]) - 1, int(fields[4])
            if fields[2] == 'gene':
                genes[gene_id] = {'symbol': gene_name, 'strand': strand, 'start': start, 'end': end,
                                  'tss': start if strand == '+' else end, 'exons': []}
            elif fields[2] == 'exon' and gene_id in genes:
                genes[gene_id]['exons'].append((start, end))
    print(f'  chr21 protein-coding genes: {len(genes)}')
    return genes


def write_chr21_gtf(gtf_gz_path, output_path):
    with gzip.open(gtf_gz_path, 'rt') as fin, gzip.open(output_path, 'wt') as fout:
        for line in fin:
            if line.startswith('#'):
                fout.write(line)
                continue
            if not line.startswith('chr21\t'):
                continue
            attrs = parse_gtf_attrs(line.split('\t')[8])
            if attrs.get('gene_type') == 'protein_coding':
                fout.write(line)
    size_kb = output_path.stat().st_size / 1024
    print(f'  chr21 protein-coding GTF: {size_kb:.0f} KB')


def signed_distance(peak_center, tss, strand):
    dist = peak_center - tss
    return -dist if strand == '-' else dist


def generate_peaks(genes):
    rng = random.Random(RANDOM_SEED)
    gene_list = [g for g in genes.values() if g['exons']]
    peaks = []
    used_genes = set()

    promoter_pool = rng.sample(gene_list, min(NUM_PROMOTER, len(gene_list)))
    for gene in promoter_pool:
        offset = rng.randint(-500, 500)
        center = gene['tss'] + offset
        width = rng.randint(*PEAK_WIDTH_RANGE)
        start = max(0, center - width // 2)
        peaks.append(('chr21', start, start + width, gene['symbol'], 'promoter', gene['tss'], gene['strand']))
        used_genes.add(gene['symbol'])

    exon_candidates = [g for g in gene_list if g['symbol'] not in used_genes]
    rng.shuffle(exon_candidates)
    exon_count = 0
    for gene in exon_candidates:
        if exon_count >= NUM_EXONIC:
            break
        far_exons = [(s, e) for s, e in gene['exons']
                     if min(abs(s - gene['tss']), abs(e - gene['tss'])) > PROMOTER_WINDOW + 500 and e - s > 300]
        if not far_exons:
            continue
        exon = rng.choice(far_exons)
        center = rng.randint(exon[0] + 100, exon[1] - 100)
        width = rng.randint(*PEAK_WIDTH_RANGE)
        start = max(0, center - width // 2)
        peaks.append(('chr21', start, start + width, gene['symbol'], 'exon', gene['tss'], gene['strand']))
        used_genes.add(gene['symbol'])
        exon_count += 1

    intron_candidates = [g for g in gene_list if g['symbol'] not in used_genes and len(g['exons']) > 1]
    rng.shuffle(intron_candidates)
    intron_count = 0
    for gene in intron_candidates:
        if intron_count >= NUM_INTRONIC:
            break
        sorted_exons = sorted(gene['exons'])
        introns = [(sorted_exons[i][1], sorted_exons[i + 1][0]) for i in range(len(sorted_exons) - 1)]
        far_introns = [(s, e) for s, e in introns
                       if e - s > 1000 and min(abs(s - gene['tss']), abs(e - gene['tss'])) > PROMOTER_WINDOW + 500]
        if not far_introns:
            continue
        intron = rng.choice(far_introns)
        center = rng.randint(intron[0] + 200, intron[1] - 200)
        width = rng.randint(*PEAK_WIDTH_RANGE)
        start = max(0, center - width // 2)
        peaks.append(('chr21', start, start + width, gene['symbol'], 'intron', gene['tss'], gene['strand']))
        intron_count += 1

    all_intervals = sorted([(g['start'], g['end']) for g in gene_list])
    gaps = [(all_intervals[i][1], all_intervals[i + 1][0]) for i in range(len(all_intervals) - 1)
            if all_intervals[i + 1][0] - all_intervals[i][1] > 20000]
    intergenic_gaps = rng.sample(gaps, min(NUM_INTERGENIC, len(gaps)))
    for gap_start, gap_end in intergenic_gaps:
        center = rng.randint(gap_start + 5000, gap_end - 5000)
        nearest = min(gene_list, key=lambda g: abs(center - g['tss']))
        width = rng.randint(*PEAK_WIDTH_RANGE)
        start = max(0, center - width // 2)
        peaks.append(('chr21', start, start + width, nearest['symbol'], 'intergenic', nearest['tss'], nearest['strand']))

    peaks.sort(key=lambda p: p[1])
    counts = {f: sum(1 for p in peaks if p[4] == f) for f in ['promoter', 'exon', 'intron', 'intergenic']}
    print(f'  Generated {len(peaks)} peaks: ' + ', '.join(f'{c} {f}' for f, c in counts.items()))
    targets = {'exon': NUM_EXONIC, 'intron': NUM_INTRONIC, 'intergenic': NUM_INTERGENIC}
    for feat, target in targets.items():
        if counts.get(feat, 0) < target:
            print(f'  WARNING: only {counts.get(feat, 0)} {feat} peaks (target: {target})')
    return peaks


def write_outputs(peaks):
    peaks_bed = SCRIPT_DIR / 'peaks.bed'
    annotations_tsv = EXPECTED_DIR / 'annotations.tsv'

    with open(peaks_bed, 'w') as f:
        for i, (chrom, start, end, *_) in enumerate(peaks):
            f.write(f'{chrom}\t{start}\t{end}\tpeak_{i + 1:03d}\t0\n')

    with open(annotations_tsv, 'w') as f:
        f.write('chr\tstart\tend\tnearest_gene\tdistance_to_tss\tfeature\n')
        for chrom, start, end, gene, feature, tss, strand in peaks:
            center = (start + end) // 2
            dist = signed_distance(center, tss, strand)
            f.write(f'{chrom}\t{start}\t{end}\t{gene}\t{dist}\t{feature}\n')

    print(f'  peaks.bed: {len(peaks)} peaks')
    print(f'  annotations.tsv: {len(peaks)} rows')


def main():
    print('=' * 60)
    print('chipseq-003: Peak Annotation Data Generation')
    print('=' * 60 + '\n')

    missing = [t for t in ['curl'] if not shutil.which(t)]
    if missing:
        sys.exit(f'Missing required tools: {", ".join(missing)}')

    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    print('Step 1: Download GENCODE annotation')
    gtf_gz = download_gtf()

    print('\nStep 2: Parse chr21 genes')
    genes = parse_chr21_genes(gtf_gz)

    print('\nStep 3: Write chr21 GTF')
    chr21_gtf = SCRIPT_DIR / 'genes.gtf.gz'
    write_chr21_gtf(gtf_gz, chr21_gtf)

    print('\nStep 4: Generate synthetic peaks')
    peaks = generate_peaks(genes)

    print('\nStep 5: Write outputs')
    write_outputs(peaks)

    gtf_gz.unlink()

    promoter_pct = sum(1 for p in peaks if p[4] == 'promoter') / len(peaks) * 100
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'  peaks.bed: {len(peaks)} peaks')
    print(f'  genes.gtf.gz: chr21 protein-coding genes')
    print(f'  annotations.tsv: ground truth ({promoter_pct:.0f}% promoter)')


if __name__ == '__main__':
    main()
