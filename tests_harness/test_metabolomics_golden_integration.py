import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class MetabolomicsGoldenIntegrationTests(unittest.TestCase):
    def test_metabolomics_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_metab001(workspace, tests_root)
            self._write_metab002(workspace, tests_root)
            self._write_metab003(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='metabolomics',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']
            self.assertEqual(aggregate['tests_total'], 3)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_metab001(self, workspace, tests_root):
        out_dir = workspace / 'metab-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'metabolomics' / 'metab-001' / 'expected' / 'feature_summary.tsv'
        (out_dir / 'feature_summary.tsv').write_text(src.read_text())

    def _write_metab002(self, workspace, tests_root):
        out_dir = workspace / 'metab-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'metabolomics' / 'metab-002' / 'expected' / 'top30_features.tsv'
        (out_dir / 'top_diff_features.tsv').write_text(src.read_text())

    def _write_metab003(self, workspace, tests_root):
        out_dir = workspace / 'metab-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        metab003 = tests_root / 'metabolomics' / 'metab-003'
        sig = set()
        with (metab003 / 'expected' / 'significant_features.tsv').open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                sig.add(row['feature_id'])
        with (metab003 / 'expected' / 'all_foldchanges.tsv').open() as f, (out_dir / 'differential_features.tsv').open('w') as g:
            reader = csv.DictReader(f, delimiter='\t')
            g.write('feature_id\tlog2fc\tpvalue\tpadj\tsignificant\n')
            for row in reader:
                fid = row['feature_id']
                is_sig = fid in sig
                g.write(f'{fid}\t{row["log2fc"]}\t{0.001 if is_sig else 0.5}\t{0.01 if is_sig else 0.8}\t{"TRUE" if is_sig else "FALSE"}\n')


if __name__ == '__main__':
    unittest.main()
