import csv
import tempfile
import unittest
from pathlib import Path

from harness import runner


class SpatialGoldenIntegrationTests(unittest.TestCase):
    def test_spatial_mock_workspace_scores_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_root = repo_root / 'tests'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            out_dir = Path(td) / 'results'
            workspace.mkdir(parents=True, exist_ok=True)

            self._write_stx001(workspace, tests_root)
            self._write_stx002(workspace, tests_root)
            self._write_stx003(workspace, tests_root)
            self._write_stx004(workspace, tests_root)

            run = runner.run_biotaskbench(
                tests_root=tests_root,
                domain='spatial-transcriptomics',
                workspace_root=workspace,
                output_dir=out_dir,
            )
            aggregate = run['payload']['aggregate']

            self.assertEqual(aggregate['tests_total'], 4)
            self.assertAlmostEqual(aggregate['coverage'], 1.0)
            self.assertAlmostEqual(aggregate['score'], 1.0)

    def _write_stx001(self, workspace, tests_root):
        out_dir = workspace / 'stx-001'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'spatial-transcriptomics' / 'stx-001' / 'expected' / 'gradient_summary.tsv'
        (out_dir / 'gradient.tsv').write_text(src.read_text())

    def _write_stx002(self, workspace, tests_root):
        out_dir = workspace / 'stx-002'
        out_dir.mkdir(parents=True, exist_ok=True)
        src = tests_root / 'spatial-transcriptomics' / 'stx-002' / 'expected' / 'top10_hotspots.tsv'
        (out_dir / 'hotspots.tsv').write_text(src.read_text())

    def _write_stx003(self, workspace, tests_root):
        out_dir = workspace / 'stx-003'
        out_dir.mkdir(parents=True, exist_ok=True)
        inp = tests_root / 'spatial-transcriptomics' / 'stx-003' / 'data' / 'spots_clustered.tsv'
        out = out_dir / 'neighborhood.tsv'

        values = {}
        with inp.open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                cluster = row['cluster']
                values.setdefault(cluster, []).append(float(row['marker_expression']))

        with out.open('w') as f:
            f.write('cluster\tmean_marker_expression\tenriched\n')
            for cluster in sorted(values):
                mean_val = sum(values[cluster]) / len(values[cluster])
                enriched = 'TRUE' if mean_val >= 5.0 else 'FALSE'
                f.write(f'{cluster}\t{mean_val:.6f}\t{enriched}\n')

    def _write_stx004(self, workspace, tests_root):
        out_dir = workspace / 'stx-004'
        out_dir.mkdir(parents=True, exist_ok=True)
        inp = tests_root / 'spatial-transcriptomics' / 'stx-004' / 'data' / 'spots_celltypes.tsv'
        out = out_dir / 'niches.tsv'

        bins = {
            'NE': [0, 0],
            'NW': [0, 0],
            'SE': [0, 0],
            'SW': [0, 0],
        }  # immune_count, total

        with inp.open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                x = float(row['x'])
                y = float(row['y'])
                if x >= 0 and y >= 0:
                    niche = 'NE'
                elif x < 0 and y >= 0:
                    niche = 'NW'
                elif x >= 0 and y < 0:
                    niche = 'SE'
                else:
                    niche = 'SW'
                bins[niche][1] += 1
                if row['cell_type'] == 'Immune':
                    bins[niche][0] += 1

        rows = []
        for niche, (immune_count, total) in bins.items():
            frac = (immune_count / total) if total else 0.0
            hotspot = 'TRUE' if frac >= 0.55 else 'FALSE'
            rows.append((niche, frac, total, hotspot))
        rows.sort(key=lambda r: r[1], reverse=True)

        with out.open('w') as f:
            f.write('niche\timmune_fraction\tspot_count\thotspot\n')
            for niche, frac, total, hotspot in rows:
                f.write(f'{niche}\t{frac:.6f}\t{total}\t{hotspot}\n')


if __name__ == '__main__':
    unittest.main()
