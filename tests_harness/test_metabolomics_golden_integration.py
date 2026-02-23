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
        inp = tests_root / 'metabolomics' / 'metab-003' / 'data' / 'pathway_input.tsv'
        out = out_dir / 'pathway_summary.tsv'
        with inp.open() as f, out.open('w') as g:
            reader = csv.DictReader(f, delimiter='\t')
            g.write('pathway_id\tmean_case\tmean_control\tdelta_signal\tactivated\n')
            for row in reader:
                mean_case = float(row['mean_case'])
                mean_control = float(row['mean_control'])
                delta = mean_case - mean_control
                activated = 'TRUE' if delta >= 1.5 else 'FALSE'
                g.write(f"{row['pathway_id']}\t{mean_case:.6f}\t{mean_control:.6f}\t{delta:.6f}\t{activated}\n")


if __name__ == '__main__':
    unittest.main()
