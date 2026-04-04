import gzip
import tempfile
import unittest
from pathlib import Path

from harness import grader


class ChipSeq005GradingTest(unittest.TestCase):
    def test_peak_count_jaccard_respects_significant_filter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / 'workspace'
            test_dir = root / 'test'
            workspace.mkdir()
            (test_dir / 'expected').mkdir(parents=True)

            (test_dir / 'expected' / 'significant_enhancers.bed').write_text(
                'chr21\t100\t200\ttrue1\n'
                'chr21\t500\t600\ttrue2\n'
            )
            (workspace / 'enhancer_diff.tsv').write_text(
                'peak_id\tchr\tstart\tend\tsignificant\n'
                'a\tchr21\t100\t200\tFALSE\n'
                'b\tchr21\t500\t600\tTRUE\n'
            )

            criterion = {
                'name': 'enhancer_recovery',
                'type': 'set_overlap',
                'description': 'd',
                'weight': 1.0,
                'expected_file': 'expected/significant_enhancers.bed',
                'target_file': 'enhancer_diff.tsv',
                'metric': 'peak_count_jaccard',
                'slop_bp': 0,
                'filter_field': 'significant',
                'filter_value': 'TRUE',
                'chrom_field': 'chr',
                'start_field': 'start',
                'end_field': 'end',
            }

            result = grader.grade_criterion(criterion, workspace, test_dir)
            self.assertLess(result['score'], 1.0)
            self.assertGreater(result['score'], 0.0)

    def test_distal_blacklist_and_cnv_custom_handlers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            test_dir = root / 'test'
            data_dir = test_dir / 'data'
            data_dir.mkdir(parents=True)
            workspace_file = root / 'enhancer_diff.tsv'

            with gzip.open(data_dir / 'genes.gtf.gz', 'wt') as f:
                f.write(
                    'chr21\ttest\ttranscript\t1000\t2000\t.\t+\t.\tgene_id "g1"; gene_name "GENE1";\n'
                    'chr21\ttest\ttranscript\t9000\t9800\t.\t-\t.\tgene_id "g2"; gene_name "GENE2";\n'
                )
            (data_dir / 'blacklist.bed').write_text('chr21\t7000\t7200\tblk\n')
            (data_dir / 'cnv_segments.bed').write_text('chr21\t11000\t11500\tcnv1\n')
            workspace_file.write_text(
                'peak_id\tchr\tstart\tend\tsignificant\tlog2fc\n'
                'p1\tchr21\t1300\t1500\tTRUE\t1.2\n'
                'p2\tchr21\t7000\t7150\tTRUE\t1.1\n'
                'p3\tchr21\t11200\t11400\tTRUE\t1.0\n'
                'p4\tchr21\t5000\t5200\tTRUE\t0.9\n'
            )

            self.assertAlmostEqual(grader.custom_distal_sig_pct(workspace_file, test_dir), 50.0)
            self.assertAlmostEqual(grader.custom_blacklist_free_sig_pct(workspace_file, test_dir), 75.0)
            self.assertAlmostEqual(grader.custom_cnv_free_sig_pct(workspace_file, test_dir), 75.0)

    def test_spikein_basis_pct(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'normalization.tsv'
            path.write_text(
                'sample_id\tgroup\tspikein_reads\tscale_factor\tnormalization_basis\n'
                's1\tcontrol\t50000\t1.0\tspikein\n'
                's2\ttreated\t32000\t1.56\tlibrary_size\n'
            )
            self.assertAlmostEqual(grader.custom_spikein_basis_pct(path), 50.0)


if __name__ == '__main__':
    unittest.main()
