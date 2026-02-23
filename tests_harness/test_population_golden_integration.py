import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class PopulationGoldenIntegrationTests(unittest.TestCase):
    def test_population_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_popgen001(workspace, tests_root)
            self._write_popgen002(workspace, tests_root)
            self._write_popgen003(workspace, tests_root)
            self._write_popgen004(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='population-genetics',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']

            self.assertEqual(aggregate['tests_total'], 4)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_popgen001(self, workspace, tests_root):
        out_dir = workspace / 'popgen-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'population-genetics' / 'popgen-001' / 'expected' / 'fst_summary.tsv'
        (out_dir / 'fst.tsv').write_text(src.read_text())

    def _write_popgen002(self, workspace, tests_root):
        out_dir = workspace / 'popgen-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'population-genetics' / 'popgen-002' / 'expected' / 'top20_snps.tsv'
        (out_dir / 'top_snps.tsv').write_text(src.read_text())

    def _write_popgen003(self, workspace, tests_root):
        out_dir = workspace / 'popgen-003'
        out_dir.mkdir(parents=True, exist_ok=True)

        sig = set()
        sig_path = tests_root / 'population-genetics' / 'popgen-003' / 'expected' / 'significant_snps.tsv'
        with sig_path.open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                sig.add(row['snp_id'])

        out = out_dir / 'hwe.tsv'
        with out.open('w') as f:
            f.write('snp_id\tpvalue\tsignificant\n')
            for snp_id in sorted(sig):
                f.write(f'{snp_id}\t1e-8\tTRUE\n')

    def _write_popgen004(self, workspace, tests_root):
        out_dir = workspace / 'popgen-004'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root.parents[0] / 'mock_outputs' / 'popgen-004' / 'pca_outliers.tsv'
        (out_dir / 'pca_outliers.tsv').write_text(src.read_text())


if __name__ == '__main__':
    unittest.main()
