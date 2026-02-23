import json
import os
import tempfile
import unittest
from pathlib import Path

from harness.adapters.bioagent_bench import BioAgentBenchAdapter
from harness.adapters.biocoder import BioCoderAdapter
from harness.adapters.bixbench import BixBenchAdapter


class AdapterTests(unittest.TestCase):
    def test_bioagent_normalize(self):
        adapter = BioAgentBenchAdapter(root='.', tests_catalog='missing.json')
        self.assertAlmostEqual(adapter.normalize_score({'steps_completed': 7, 'steps_to_completion': 10}), 0.7)
        self.assertAlmostEqual(adapter.normalize_score(1.2), 1.0)

    def test_biocoder_normalize(self):
        adapter = BioCoderAdapter(root='.', tests_catalog='missing.json')
        self.assertAlmostEqual(adapter.normalize_score({'tests_passed': 5, 'tests_total': 20}), 0.25)
        self.assertEqual(adapter.normalize_score(0), 0.0)
        self.assertEqual(adapter.normalize_score(1), 1.0)

    def test_bixbench_normalize(self):
        adapter = BixBenchAdapter(root='.', tests_catalog='missing.json')
        self.assertAlmostEqual(adapter.normalize_score({'questions_correct': 17, 'questions_total': 34}), 0.5)

    def test_list_tests_from_catalog(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = Path(td) / 'tests.json'
            catalog.write_text(json.dumps({'tests': [{'test_id': 'x1'}, {'test_id': 'x2'}]}))
            adapter = BixBenchAdapter(root=td, tests_catalog=catalog)
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 2)

    def test_load_run_results(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'results.json'
            out.write_text(json.dumps({'results': [{'test_id': 'a', 'steps_completed': 2, 'steps_to_completion': 4}]}))
            old = os.environ.get('BIOAGENT_BENCH_RESULTS_JSON')
            os.environ['BIOAGENT_BENCH_RESULTS_JSON'] = str(out)
            try:
                adapter = BioAgentBenchAdapter(root=td, tests_catalog='missing.json')
                results = adapter.load_run_results()
                self.assertEqual(len(results), 1)
                self.assertAlmostEqual(results[0]['score'], 0.5)
                self.assertTrue(results[0]['attempted'])
            finally:
                if old is None:
                    del os.environ['BIOAGENT_BENCH_RESULTS_JSON']
                else:
                    os.environ['BIOAGENT_BENCH_RESULTS_JSON'] = old


if __name__ == '__main__':
    unittest.main()
