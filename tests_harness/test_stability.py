import json
import tempfile
import unittest
from pathlib import Path

from harness import stability


class StabilityTests(unittest.TestCase):
    def test_analyze_flakiness_detects_spread(self):
        run1 = {'results': [{'test_id': 't1', 'domain': 'd', 'score': 0.1, 'attempted': True}]}
        run2 = {'results': [{'test_id': 't1', 'domain': 'd', 'score': 0.8, 'attempted': True}]}
        run3 = {'results': [{'test_id': 't1', 'domain': 'd', 'score': 0.6, 'attempted': True}]}

        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / 'r1.json'
            p2 = Path(td) / 'r2.json'
            p3 = Path(td) / 'r3.json'
            p1.write_text(json.dumps(run1))
            p2.write_text(json.dumps(run2))
            p3.write_text(json.dumps(run3))

            report = stability.analyze_flakiness([p1, p2, p3], threshold=0.3)
            self.assertEqual(report['runs_compared'], 3)
            self.assertEqual(report['flaky_count'], 1)
            self.assertEqual(report['flaky_tests'][0]['test_id'], 't1')

    def test_analyze_flakiness_supports_suite_all_payload(self):
        run_all = {
            'suite': 'all',
            'runs': [
                {'suite': 'biotaskbench', 'results': [{'test_id': 't2', 'domain': 'd', 'score': 0.7, 'attempted': True}]},
                {'suite': 'bixbench', 'results': []},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'all.json'
            p.write_text(json.dumps(run_all))
            report = stability.analyze_flakiness([p], threshold=0.3)
            self.assertEqual(report['tests_analyzed'], 1)
            self.assertEqual(report['per_test'][0]['test_id'], 't2')


if __name__ == '__main__':
    unittest.main()
