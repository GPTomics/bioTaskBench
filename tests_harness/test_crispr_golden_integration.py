import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class CrisprGoldenIntegrationTests(unittest.TestCase):
    def test_crispr_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_crispr001(workspace, tests_root)
            self._write_crispr002(workspace, tests_root)
            self._write_crispr003(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='crispr-screens',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']
            self.assertEqual(aggregate['tests_total'], 3)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_crispr001(self, workspace, tests_root):
        out_dir = workspace / 'crispr-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'crispr-screens' / 'crispr-001' / 'expected' / 'guide_summary.tsv'
        (out_dir / 'guide_summary.tsv').write_text(src.read_text())

    def _write_crispr002(self, workspace, tests_root):
        out_dir = workspace / 'crispr-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'crispr-screens' / 'crispr-002' / 'expected' / 'top20_essential.tsv'
        (out_dir / 'essential_genes.tsv').write_text(src.read_text())

    def _write_crispr003(self, workspace, tests_root):
        out_dir = workspace / 'crispr-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        inp = tests_root / 'crispr-screens' / 'crispr-003' / 'data' / 'control_guides.tsv'
        out = out_dir / 'control_qc.tsv'
        values = {}
        with inp.open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                set_id = row['set_id']
                values.setdefault(set_id, []).append(float(row['lfc']))
        with out.open('w') as g:
            g.write('set_id\tguide_count\tmean_lfc\tunstable_pct\tfail\n')
            for set_id in sorted(values):
                arr = values[set_id]
                n = len(arr)
                mean_lfc = sum(arr) / n
                unstable = sum(1 for x in arr if abs(x) >= 1.0)
                pct = 100.0 * unstable / n
                fail = 'TRUE' if pct >= 20.0 else 'FALSE'
                g.write(f'{set_id}\t{n}\t{mean_lfc:.6f}\t{pct:.6f}\t{fail}\n')


if __name__ == '__main__':
    unittest.main()
