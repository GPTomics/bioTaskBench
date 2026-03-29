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
        crispr003 = tests_root / 'crispr-screens' / 'crispr-003'
        essential = set()
        with (crispr003 / 'expected' / 'failing_sets.tsv').open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                essential.add(row['gene'])
        rows = []
        with (crispr003 / 'expected' / 'all_gene_lfc.tsv').open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                gene = row['gene']
                lfc = float(row['median_lfc'])
                is_ess = gene in essential
                rows.append((gene, lfc, 1e-6 if is_ess else 0.8, 1e-5 if is_ess else 0.9, 'TRUE' if is_ess else 'FALSE'))
        rows.sort(key=lambda r: r[1])
        with (out_dir / 'gene_essentiality.tsv').open('w') as g:
            g.write('gene\tmedian_lfc\tpvalue\tpadj\tessential\n')
            for gene, lfc, pv, pa, ess in rows:
                g.write(f'{gene}\t{lfc:.6f}\t{pv:.6e}\t{pa:.6e}\t{ess}\n')


if __name__ == '__main__':
    unittest.main()
