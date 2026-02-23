import tempfile
import unittest
from pathlib import Path

from harness import runner


class LongReadGoldenIntegrationTests(unittest.TestCase):
    def test_longread_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_lrs001(workspace, tests_root)
            self._write_lrs002(workspace, tests_root)
            self._write_lrs003(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='long-read-sequencing',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']

            self.assertEqual(aggregate['tests_total'], 3)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_lrs001(self, workspace, tests_root):
        out_dir = workspace / 'lrs-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'long-read-sequencing' / 'lrs-001' / 'expected' / 'read_stats.tsv'
        (out_dir / 'read_stats.tsv').write_text(src.read_text())

    def _write_lrs002(self, workspace, tests_root):
        out_dir = workspace / 'lrs-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'long-read-sequencing' / 'lrs-002' / 'expected' / 'top25_indel_reads.tsv'
        (out_dir / 'high_indel_reads.tsv').write_text(src.read_text())

    def _write_lrs003(self, workspace, tests_root):
        out_dir = workspace / 'lrs-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'long-read-sequencing' / 'lrs-003' / 'expected' / 'consensus_summary.tsv'
        (out_dir / 'consensus.tsv').write_text(src.read_text())


if __name__ == '__main__':
    unittest.main()
