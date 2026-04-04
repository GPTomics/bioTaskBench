import csv
import gzip
import shutil
import tempfile
import unittest
from pathlib import Path

from harness import runner


class ChipSeqGoldenIntegrationTests(unittest.TestCase):
    def test_chipseq_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as td:
            tests_root = Path(td) / 'tests'
            shutil.copytree(repo_root / 'tests' / 'chip-seq', tests_root / 'chip-seq')
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._seed_chipseq005_assets(tests_root)
            self._write_chipseq001(workspace, tests_root)
            self._write_chipseq002(workspace, tests_root)
            self._write_chipseq003(workspace, tests_root)
            self._write_chipseq004(workspace, tests_root)
            self._write_chipseq005(workspace)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='chip-seq',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']

            self.assertEqual(aggregate['tests_total'], 5)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)
            self.assertAlmostEqual(aggregate['score_overall'], 1.0)

    def _seed_chipseq005_assets(self, tests_root):
        test_dir = tests_root / 'chip-seq' / 'chipseq-005'
        data_dir = test_dir / 'data'
        expected_dir = test_dir / 'expected'
        data_dir.mkdir(parents=True, exist_ok=True)
        expected_dir.mkdir(parents=True, exist_ok=True)

        peak_rows = [
            ('chr21', 10000, 10400, 'enh_true_01', 1.10, 'GENE1', 9000, 2, 1),
            ('chr21', 13000, 13420, 'enh_true_02', 1.25, 'GENE1', 12000, 2, 1),
            ('chr21', 18000, 18410, 'enh_true_03', 1.40, 'GENE2', 7000, 2, 1),
            ('chr21', 23000, 23430, 'enh_true_04', 1.55, 'GENE2', 12000, 2, 1),
            ('chr21', 28000, 28420, 'enh_true_05', 1.70, 'GENE3', 8000, 2, 1),
            ('chr21', 33000, 33450, 'enh_true_06', 1.85, 'GENE3', 13000, 2, 1),
            ('chr21', 38000, 38400, 'enh_true_07', 2.00, 'GENE4', 9000, 2, 1),
            ('chr21', 43000, 43410, 'enh_true_08', 2.15, 'GENE4', 14000, 2, 1),
            ('chr21', 48000, 48420, 'enh_true_09', 2.30, 'GENE5', 10000, 2, 1),
            ('chr21', 53000, 53430, 'enh_true_10', 2.45, 'GENE5', 15000, 2, 1),
        ]

        with (expected_dir / 'significant_enhancers.bed').open('w') as f:
            for chrom, start, end, peak_id, *_ in peak_rows:
                f.write(f'{chrom}\t{start}\t{end}\t{peak_id}\n')

        with (expected_dir / 'true_enhancer_truth.tsv').open('w', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    'chr', 'start', 'end', 'peak_id', 'log2fc', 'nearest_gene',
                    'distance_to_tss', 'treated_support', 'control_support',
                ],
                delimiter='\t',
            )
            writer.writeheader()
            for chrom, start, end, peak_id, log2fc, gene, dist, treated, control in peak_rows:
                writer.writerow({
                    'chr': chrom,
                    'start': start,
                    'end': end,
                    'peak_id': peak_id,
                    'log2fc': f'{log2fc:.6f}',
                    'nearest_gene': gene,
                    'distance_to_tss': dist,
                    'treated_support': treated,
                    'control_support': control,
                })

        norm_rows = [
            ('control_rep1', 'control', 52000, 0.91, 'spikein'),
            ('control_rep2', 'control', 50000, 0.95, 'spikein'),
            ('treated_rep1', 'treated', 33500, 1.42, 'spikein+input'),
            ('treated_rep2', 'treated', 32000, 1.49, 'spikein+input'),
            ('control_input', 'control', 51000, 0.93, 'spikein'),
            ('treated_input', 'treated', 33000, 1.44, 'spikein'),
        ]
        with (expected_dir / 'normalization_truth.tsv').open('w', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['sample_id', 'group', 'spikein_reads', 'scale_factor', 'normalization_basis'],
                delimiter='\t',
            )
            writer.writeheader()
            for sample_id, group, spikein_reads, scale_factor, basis in norm_rows:
                writer.writerow({
                    'sample_id': sample_id,
                    'group': group,
                    'spikein_reads': spikein_reads,
                    'scale_factor': scale_factor,
                    'normalization_basis': basis,
                })

        genes_text = '\n'.join([
            'chr21\tgolden\ttranscript\t1000\t3000\t.\t+\t.\tgene_id "g1"; transcript_id "t1"; gene_name "GENE_A";',
            'chr21\tgolden\ttranscript\t80000\t82000\t.\t+\t.\tgene_id "g2"; transcript_id "t2"; gene_name "GENE_B";',
        ]) + '\n'
        with gzip.open(data_dir / 'genes.gtf.gz', 'wt') as f:
            f.write(genes_text)

        (data_dir / 'blacklist.bed').write_text('chr21\t70000\t71000\tblacklist_01\n')
        (data_dir / 'cnv_segments.bed').write_text('chr21\t75000\t76000\tcnv_01\n')

    def _write_chipseq001(self, workspace, tests_root):
        out_dir = workspace / 'chipseq-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        consensus = tests_root / 'chip-seq' / 'chipseq-001' / 'expected' / 'consensus_peaks.bed'
        peaks = out_dir / 'peaks.bed'
        with consensus.open() as f, peaks.open('w') as g:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                chrom, start, end = line.rstrip('\n').split('\t')[:3]
                g.write(f'{chrom}\t{start}\t{end}\tpeak_{i:04d}\t1000\n')

    def _write_chipseq002(self, workspace, tests_root):
        out_dir = workspace / 'chipseq-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        planted_path = tests_root / 'chip-seq' / 'chipseq-002' / 'expected' / 'planted_motifs.tsv'
        consensuses = []
        with planted_path.open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                consensuses.append((row['motif_consensus'], float(row['expected_pct'])))
        motifs = out_dir / 'motifs.tsv'
        with motifs.open('w') as f:
            f.write('motif_id\tconsensus\tp_value\tpct_target\n')
            for i, (cons, pct) in enumerate(consensuses):
                f.write(f'motif-{i + 1}\t{cons}\t{10 ** -(20 - i * 5):.0e}\t{pct:.1f}\n')
            f.write(f'motif-4\tACGTACGTAC\t1e-3\t15\n')
            f.write(f'motif-5\tGATCGATCGA\t1e-2\t8\n')

    def _write_chipseq003(self, workspace, tests_root):
        out_dir = workspace / 'chipseq-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'chip-seq' / 'chipseq-003' / 'expected' / 'annotations.tsv'
        (out_dir / 'annotations.tsv').write_text(src.read_text())

    def _write_chipseq004(self, workspace, tests_root):
        out_dir = workspace / 'chipseq-004'
        out_dir.mkdir(parents=True, exist_ok=True)
        true_log2fc = tests_root / 'chip-seq' / 'chipseq-004' / 'expected' / 'true_log2fc.tsv'
        differential = tests_root / 'chip-seq' / 'chipseq-004' / 'expected' / 'differential_peaks.tsv'
        output = out_dir / 'differential.tsv'

        true_de = set()
        with differential.open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                true_de.add(row['peak_id'])

        with true_log2fc.open() as f, output.open('w') as g:
            reader = csv.DictReader(f, delimiter='\t')
            g.write('peak_id\tlog2fc\tpvalue\tpadj\tsignificant\n')
            for row in reader:
                peak_id = row['peak_id']
                log2fc = float(row['log2fc'])
                significant = 'TRUE' if peak_id in true_de else 'FALSE'
                pvalue = '1e-6' if significant == 'TRUE' else '0.2'
                padj = '1e-4' if significant == 'TRUE' else '0.5'
                g.write(f'{peak_id}\t{log2fc:.6f}\t{pvalue}\t{padj}\t{significant}\n')

    def _write_chipseq005(self, workspace):
        out_dir = workspace / 'chipseq-005'
        out_dir.mkdir(parents=True, exist_ok=True)

        peak_rows = [
            ('enh_true_01', 'chr21', 10000, 10400, 1.10, 'GENE1', 9000, 2, 1),
            ('enh_true_02', 'chr21', 13000, 13420, 1.25, 'GENE1', 12000, 2, 1),
            ('enh_true_03', 'chr21', 18000, 18410, 1.40, 'GENE2', 7000, 2, 1),
            ('enh_true_04', 'chr21', 23000, 23430, 1.55, 'GENE2', 12000, 2, 1),
            ('enh_true_05', 'chr21', 28000, 28420, 1.70, 'GENE3', 8000, 2, 1),
            ('enh_true_06', 'chr21', 33000, 33450, 1.85, 'GENE3', 13000, 2, 1),
            ('enh_true_07', 'chr21', 38000, 38400, 2.00, 'GENE4', 9000, 2, 1),
            ('enh_true_08', 'chr21', 43000, 43410, 2.15, 'GENE4', 14000, 2, 1),
            ('enh_true_09', 'chr21', 48000, 48420, 2.30, 'GENE5', 10000, 2, 1),
            ('enh_true_10', 'chr21', 53000, 53430, 2.45, 'GENE5', 15000, 2, 1),
        ]
        with (out_dir / 'enhancer_diff.tsv').open('w') as f:
            f.write(
                'peak_id\tchr\tstart\tend\tlog2fc\tpvalue\tpadj\tsignificant\tnearest_gene\t'
                'distance_to_tss\ttreated_support\tcontrol_support\tnormalization_basis\n'
            )
            for peak_id, chrom, start, end, log2fc, gene, dist, treated, control in peak_rows:
                f.write(
                    f'{peak_id}\t{chrom}\t{start}\t{end}\t{log2fc:.6f}\t1e-6\t1e-4\tTRUE\t'
                    f'{gene}\t{dist}\t{treated}\t{control}\tspikein+input\n'
                )

        norm_rows = [
            ('control_rep1', 'control', 52000, 0.91, 'spikein'),
            ('control_rep2', 'control', 50000, 0.95, 'spikein'),
            ('treated_rep1', 'treated', 33500, 1.42, 'spikein+input'),
            ('treated_rep2', 'treated', 32000, 1.49, 'spikein+input'),
            ('control_input', 'control', 51000, 0.93, 'spikein'),
            ('treated_input', 'treated', 33000, 1.44, 'spikein'),
        ]
        with (out_dir / 'normalization.tsv').open('w') as f:
            f.write('sample_id\tgroup\tspikein_reads\tscale_factor\tnormalization_basis\n')
            for sample_id, group, spikein_reads, scale_factor, basis in norm_rows:
                f.write(f'{sample_id}\t{group}\t{spikein_reads}\t{scale_factor:.6f}\t{basis}\n')


if __name__ == '__main__':
    unittest.main()
