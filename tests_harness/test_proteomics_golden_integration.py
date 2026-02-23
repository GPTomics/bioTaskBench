import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class ProteomicsGoldenIntegrationTests(unittest.TestCase):
    def test_proteomics_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_prot001(workspace, tests_root)
            self._write_prot002(workspace, tests_root)
            self._write_prot003(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='proteomics',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']
            self.assertEqual(aggregate['tests_total'], 3)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_prot001(self, workspace, tests_root):
        out_dir = workspace / 'prot-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'proteomics' / 'prot-001' / 'expected' / 'intensity_summary.tsv'
        (out_dir / 'intensity_summary.tsv').write_text(src.read_text())

    def _write_prot002(self, workspace, tests_root):
        out_dir = workspace / 'prot-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'proteomics' / 'prot-002' / 'expected' / 'top25_proteins.tsv'
        (out_dir / 'top_diff_proteins.tsv').write_text(src.read_text())

    def _write_prot003(self, workspace, tests_root):
        out_dir = workspace / 'prot-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        inp = tests_root / 'proteomics' / 'prot-003' / 'data' / 'protein_matrix.tsv'
        out = out_dir / 'missingness.tsv'
        with inp.open() as f:
            rows = list(csv.reader(f, delimiter='\t'))
        header = rows[0]
        samples = header[1:]
        body = rows[1:]
        with out.open('w') as g:
            g.write('sample_id\tprotein_count\tmissing_count\tmissing_pct\thigh_missing\n')
            total = len(body)
            for idx, sample in enumerate(samples, start=1):
                missing = sum(1 for r in body if r[idx] == 'NA')
                pct = 100.0 * missing / total
                high = 'TRUE' if pct >= 20.0 else 'FALSE'
                g.write(f'{sample}\t{total}\t{missing}\t{pct:.6f}\t{high}\n')


if __name__ == '__main__':
    unittest.main()
