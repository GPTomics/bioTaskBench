import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class MultiOmicsGoldenIntegrationTests(unittest.TestCase):
    def test_multiomics_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_moi001(workspace, tests_root)
            self._write_moi002(workspace, tests_root)
            self._write_moi003(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='multi-omics-integration',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']
            self.assertEqual(aggregate['tests_total'], 3)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_moi001(self, workspace, tests_root):
        out_dir = workspace / 'moi-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'multi-omics-integration' / 'moi-001' / 'expected' / 'association_summary.tsv'
        (out_dir / 'association.tsv').write_text(src.read_text())

    def _write_moi002(self, workspace, tests_root):
        out_dir = workspace / 'moi-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'multi-omics-integration' / 'moi-002' / 'expected' / 'top25_features.tsv'
        (out_dir / 'integrated_top.tsv').write_text(src.read_text())

    def _write_moi003(self, workspace, tests_root):
        out_dir = workspace / 'moi-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        inp = tests_root / 'multi-omics-integration' / 'moi-003' / 'data' / 'pathway_signals.tsv'
        out = out_dir / 'pathway_concordance.tsv'
        with inp.open() as f, out.open('w') as g:
            reader = csv.DictReader(f, delimiter='\t')
            g.write('pathway_id\trna_signal\tprotein_signal\tconcordance_score\tconcordant\n')
            for row in reader:
                rna = float(row['rna_signal'])
                prot = float(row['protein_signal'])
                score = min(rna, prot)
                concordant = 'TRUE' if score >= 1.0 else 'FALSE'
                g.write(f"{row['pathway_id']}\t{rna:.6f}\t{prot:.6f}\t{score:.6f}\t{concordant}\n")


if __name__ == '__main__':
    unittest.main()
