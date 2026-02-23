import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class AssemblyGoldenIntegrationTests(unittest.TestCase):
    def test_assembly_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_assembly001(workspace, tests_root)
            self._write_assembly002(workspace, tests_root)
            self._write_assembly003(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='genome-assembly',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']

            self.assertEqual(aggregate['tests_total'], 3)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_assembly001(self, workspace, tests_root):
        out_dir = workspace / 'assembly-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'genome-assembly' / 'assembly-001' / 'expected' / 'assembly_stats.tsv'
        (out_dir / 'assembly_stats.tsv').write_text(src.read_text())

    def _write_assembly002(self, workspace, tests_root):
        out_dir = workspace / 'assembly-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'genome-assembly' / 'assembly-002' / 'expected' / 'top15_joins.tsv'
        (out_dir / 'joins.tsv').write_text(src.read_text())

    def _write_assembly003(self, workspace, tests_root):
        out_dir = workspace / 'assembly-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        inp = tests_root / 'genome-assembly' / 'assembly-003' / 'data' / 'contig_errors.tsv'
        out = out_dir / 'errors.tsv'
        with inp.open() as f, out.open('w') as g:
            reader = csv.DictReader(f, delimiter='\t')
            g.write('contig_id\tmismatches\taligned_bases\tmismatch_rate\thigh_error\n')
            for row in reader:
                mismatches = int(row['mismatches'])
                aligned = int(row['aligned_bases'])
                rate = mismatches / aligned
                high_error = 'TRUE' if rate >= 0.015 else 'FALSE'
                g.write(f"{row['contig_id']}\t{mismatches}\t{aligned}\t{rate:.8f}\t{high_error}\n")


if __name__ == '__main__':
    unittest.main()
