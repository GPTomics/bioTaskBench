import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class MethylationGoldenIntegrationTests(unittest.TestCase):
    def test_methylation_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_meth001(workspace, tests_root)
            self._write_meth002(workspace, tests_root)
            self._write_meth003(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='methylation-analysis',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']
            self.assertEqual(aggregate['tests_total'], 3)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_meth001(self, workspace, tests_root):
        out_dir = workspace / 'meth-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'methylation-analysis' / 'meth-001' / 'expected' / 'methylation_summary.tsv'
        (out_dir / 'methylation_summary.tsv').write_text(src.read_text())

    def _write_meth002(self, workspace, tests_root):
        out_dir = workspace / 'meth-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'methylation-analysis' / 'meth-002' / 'expected' / 'top30_dmc.tsv'
        (out_dir / 'top_dmc.tsv').write_text(src.read_text())

    def _write_meth003(self, workspace, tests_root):
        out_dir = workspace / 'meth-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        inp = tests_root / 'methylation-analysis' / 'meth-003' / 'data' / 'region_methylation.tsv'
        out = out_dir / 'dmr.tsv'
        with inp.open() as f, out.open('w') as g:
            reader = csv.DictReader(f, delimiter='\t')
            g.write('region_id\tmean_case\tmean_control\tdelta_beta\thypermethylated\n')
            for row in reader:
                mean_case = float(row['mean_case'])
                mean_control = float(row['mean_control'])
                delta = mean_case - mean_control
                hyper = 'TRUE' if delta >= 0.20 else 'FALSE'
                g.write(f"{row['region_id']}\t{mean_case:.6f}\t{mean_control:.6f}\t{delta:.6f}\t{hyper}\n")


if __name__ == '__main__':
    unittest.main()
