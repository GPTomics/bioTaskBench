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
        prot003 = tests_root / 'proteomics' / 'prot-003'
        sig = set()
        with (prot003 / 'expected' / 'significant_proteins.tsv').open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                sig.add(row['protein_id'])
        with (prot003 / 'expected' / 'all_results.tsv').open() as f, (out_dir / 'de_proteins.tsv').open('w') as g:
            reader = csv.DictReader(f, delimiter='\t')
            g.write('protein_id\tlog2fc\tpvalue\tpadj\tsignificant\n')
            for row in reader:
                pid = row['protein_id']
                is_sig = pid in sig
                g.write(f'{pid}\t{row["log2fc"]}\t{0.001 if is_sig else 0.5}\t{0.01 if is_sig else 0.8}\t{"TRUE" if is_sig else "FALSE"}\n')


if __name__ == '__main__':
    unittest.main()
