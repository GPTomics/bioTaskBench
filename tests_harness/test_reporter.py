import unittest

from harness import reporter


class ReporterTests(unittest.TestCase):
    def test_domain_score_uses_attempted_only(self):
        results = [
            {'domain': 'd', 'difficulty': 'basic', 'attempted': True, 'score': 0.8},
            {'domain': 'd', 'difficulty': 'intermediate', 'attempted': False, 'score': 0.0},
        ]
        agg = reporter.aggregate_results(results)
        self.assertAlmostEqual(agg['domains']['d']['score'], 0.8)
        self.assertAlmostEqual(agg['domains']['d']['score_overall'], 0.4)
        self.assertAlmostEqual(agg['completion_rate'], 0.5)
        self.assertIn('basic', agg['difficulty'])
        self.assertIn('intermediate', agg['difficulty'])

    def test_compare_includes_domain_deltas(self):
        a = {
            'aggregate': {
                'coverage': 0.2,
                'completion_rate': 0.1,
                'score': 0.3,
                'score_overall': 0.1,
                'domains': {'chip-seq': {'coverage': 0.2, 'completion_rate': 0.1, 'score': 0.3, 'score_overall': 0.1}},
                'difficulty': {'basic': {'score_overall': 0.1, 'tests_total': 1}},
            }
        }
        b = {
            'aggregate': {
                'coverage': 0.5,
                'completion_rate': 0.4,
                'score': 0.6,
                'score_overall': 0.4,
                'domains': {'chip-seq': {'coverage': 0.5, 'completion_rate': 0.4, 'score': 0.6, 'score_overall': 0.4}},
                'difficulty': {'basic': {'score_overall': 0.4, 'tests_total': 1}},
            }
        }

        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            pa = Path(td) / 'a.json'
            pb = Path(td) / 'b.json'
            pa.write_text(json.dumps(a))
            pb.write_text(json.dumps(b))
            delta = reporter.compare_runs(pa, pb)
            self.assertAlmostEqual(delta['coverage_delta'], 0.3)
            self.assertAlmostEqual(delta['completion_rate_delta'], 0.3)
            self.assertAlmostEqual(delta['domains']['chip-seq']['score_delta'], 0.3)
            self.assertAlmostEqual(delta['domains']['chip-seq']['completion_rate_delta'], 0.3)
            self.assertAlmostEqual(delta['difficulty']['basic']['score_overall_delta'], 0.3)

    def test_format_summary_uses_suite_name_for_external(self):
        payload = {
            'suite': 'bioagent-bench',
            'aggregate': {
                'tests_total': 0,
                'tests_attempted': 0,
                'coverage': 0.0,
                'completion_rate': 0.0,
                'score': 0.0,
                'score_overall': 0.0,
                'domains': {},
                'difficulty': {},
            },
        }
        text = reporter.format_summary(payload)
        self.assertIn('bioagent-bench Run Summary', text)

    def test_load_run_accepts_parent_output_directory(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'results'
            run_dir = root / 'run-20260101-010101'
            run_dir.mkdir(parents=True)
            (run_dir / 'run.json').write_text(json.dumps({'aggregate': {'coverage': 0.0}}))
            loaded = reporter.load_run(root)
            self.assertIn('aggregate', loaded)


if __name__ == '__main__':
    unittest.main()
