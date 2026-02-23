import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class ChipSeqGoldenIntegrationTests(unittest.TestCase):
    def test_chipseq_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_chipseq001(workspace, tests_root)
            self._write_chipseq002(workspace)
            self._write_chipseq003(workspace, tests_root)
            self._write_chipseq004(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='chip-seq',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']

            self.assertEqual(aggregate['tests_total'], 4)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)
            self.assertAlmostEqual(aggregate['score_overall'], 1.0)

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

    def _write_chipseq002(self, workspace):
        out_dir = workspace / 'chipseq-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        motifs = out_dir / 'motifs.tsv'
        motifs.write_text(
            'motif_name\tp_value\tpct_target\n'
            'CTCF\t1e-20\t85\n'
            'ZNF143\t1e-8\t41\n'
            'SP1\t2e-7\t35\n'
            'MAX\t8e-6\t29\n'
            'ATF3\t1e-4\t21\n'
        )

    def _write_chipseq003(self, workspace, tests_root):
        out_dir = workspace / 'chipseq-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        truth = tests_root / 'chip-seq' / 'chipseq-003' / 'expected' / 'annotations.tsv'
        (out_dir / 'annotations.tsv').write_text(truth.read_text())

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


if __name__ == '__main__':
    unittest.main()
