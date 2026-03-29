import json
import os
import tempfile
import unittest
from pathlib import Path

from harness.adapters.bioagent_bench import BioAgentBenchAdapter
from harness.adapters.bixbench import BixBenchAdapter


class AdapterTests(unittest.TestCase):
    def test_bioagent_normalize(self):
        adapter = BioAgentBenchAdapter(root='.', tests_catalog='missing.json')
        self.assertAlmostEqual(adapter.normalize_score({'steps_completed': 7, 'steps_to_completion': 10}), 0.7)
        self.assertAlmostEqual(adapter.normalize_score(1.2), 1.0)

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

    def test_bioagent_list_tests_from_task_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            src_dir = Path(td) / 'src'
            src_dir.mkdir()
            metadata = [{'task_id': 't1', 'name': 'Task 1'}, {'task_id': 't2', 'name': 'Task 2'}, {'task_id': 't3', 'name': 'Task 3'}]
            (src_dir / 'task_metadata.json').write_text(json.dumps(metadata))
            adapter = BioAgentBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 3)
            self.assertEqual(tests[0]['task_id'], 't1')
            self.assertEqual(tests[1]['task_id'], 't2')
            self.assertEqual(tests[2]['task_id'], 't3')
            self.assertEqual(tests[0]['name'], 'Task 1')

    def test_bioagent_list_tests_metadata_preserves_fields(self):
        with tempfile.TemporaryDirectory() as td:
            src_dir = Path(td) / 'src'
            src_dir.mkdir()
            metadata = [{'task_id': 'alzheimer-mouse', 'name': 'Alzheimer', 'task_prompt': 'Analyze data', 'download_urls': {'data': []}}]
            (src_dir / 'task_metadata.json').write_text(json.dumps(metadata))
            adapter = BioAgentBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 1)
            self.assertEqual(tests[0]['task_id'], 'alzheimer-mouse')
            self.assertEqual(tests[0]['name'], 'Alzheimer')
            self.assertEqual(tests[0]['task_prompt'], 'Analyze data')
            self.assertEqual(tests[0]['download_urls'], {'data': []})


    def test_bioagent_list_tests_prefers_tests_json_over_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = Path(td) / 'tests.json'
            catalog.write_text(json.dumps({'tests': [{'test_id': 'x1'}, {'test_id': 'x2'}]}))
            src_dir = Path(td) / 'src'
            src_dir.mkdir()
            (src_dir / 'task_metadata.json').write_text(json.dumps([{'task_id': 't1'}, {'task_id': 't2'}, {'task_id': 't3'}]))
            adapter = BioAgentBenchAdapter(root=td, tests_catalog=str(catalog))
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 2)
            self.assertEqual(tests[0]['test_id'], 'x1')
            self.assertEqual(tests[1]['test_id'], 'x2')


    def test_bixbench_list_tests_from_csv(self):
        with tempfile.TemporaryDirectory() as td:
            csv_dir = Path(td) / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            csv_content = 'uuid,short_qid,question,choices,unsure,target,llm_response,predicted,grade,correct,sure\na,qid-1,Q1,,,,,R1,1,True,True\nb,qid-1,Q1,,,,,R2,0,False,True\nc,qid-2,Q2,,,,,R3,1,True,True\nd,qid-2,Q2,,,,,R4,1,True,True\n'
            (csv_dir / 'test.csv').write_text(csv_content)
            adapter = BixBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 2)
            self.assertEqual(tests[0]['test_id'], 'qid-1')
            self.assertEqual(tests[1]['test_id'], 'qid-2')

    def test_bixbench_list_tests_deduplicates_across_csvs(self):
        with tempfile.TemporaryDirectory() as td:
            csv_dir = Path(td) / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            header = 'uuid,short_qid,question,choices,unsure,target,llm_response,predicted,grade,correct,sure\n'
            (csv_dir / 'a.csv').write_text(header + 'a,qid-1,Q,,,,,,1,True,True\nb,qid-2,Q,,,,,,1,True,True\n')
            (csv_dir / 'b.csv').write_text(header + 'c,qid-2,Q,,,,,,0,False,True\nd,qid-3,Q,,,,,,1,True,True\n')
            adapter = BixBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 3)
            self.assertEqual(tests[0]['test_id'], 'qid-1')
            self.assertEqual(tests[1]['test_id'], 'qid-2')
            self.assertEqual(tests[2]['test_id'], 'qid-3')

    def test_bixbench_load_results_from_csv(self):
        with tempfile.TemporaryDirectory() as td:
            csv_dir = Path(td) / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            csv_content = 'uuid,short_qid,question,choices,unsure,target,llm_response,predicted,grade,correct,sure\na,qid-1,Q1,,,,,R1,1,True,True\nb,qid-1,Q1,,,,,R2,0,False,True\nc,qid-2,Q2,,,,,R3,1,True,True\nd,qid-2,Q2,,,,,R4,1,True,True\n'
            (csv_dir / 'results.csv').write_text(csv_content)
            adapter = BixBenchAdapter(root=td, tests_catalog='missing.json')
            results = adapter.load_run_results()
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['test_id'], 'qid-1')
            self.assertAlmostEqual(results[0]['score'], 0.5)
            self.assertEqual(results[0]['suite'], 'bixbench')
            self.assertTrue(results[0]['attempted'])
            self.assertEqual(results[1]['test_id'], 'qid-2')
            self.assertAlmostEqual(results[1]['score'], 1.0)

    def test_bixbench_load_results_csv_scores_zero(self):
        with tempfile.TemporaryDirectory() as td:
            csv_dir = Path(td) / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            csv_content = 'uuid,short_qid,question,choices,unsure,target,llm_response,predicted,grade,correct,sure\na,qid-fail,Q,,,,,,0,False,True\nb,qid-fail,Q,,,,,,0,False,True\nc,qid-pass,Q,,,,,,1,True,True\nd,qid-pass,Q,,,,,,1,True,True\n'
            (csv_dir / 'eval.csv').write_text(csv_content)
            adapter = BixBenchAdapter(root=td, tests_catalog='missing.json')
            results = adapter.load_run_results()
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['test_id'], 'qid-fail')
            self.assertAlmostEqual(results[0]['score'], 0.0)
            self.assertTrue(results[0]['attempted'])
            self.assertEqual(results[1]['test_id'], 'qid-pass')
            self.assertAlmostEqual(results[1]['score'], 1.0)


    def test_bixbench_list_tests_prefers_tests_json(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = Path(td) / 'tests.json'
            catalog.write_text(json.dumps({'tests': [{'test_id': 'x1'}, {'test_id': 'x2'}]}))
            csv_dir = Path(td) / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            (csv_dir / 'test.csv').write_text('uuid,short_qid,question,choices,unsure,target,llm_response,predicted,grade,correct,sure\na,q1,Q,,,,,,1,True,True\n')
            adapter = BixBenchAdapter(root=td, tests_catalog=str(catalog))
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 2)
            self.assertEqual(tests[0]['test_id'], 'x1')

    def test_bixbench_load_results_standard_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'results.json'
            out.write_text(json.dumps({'results': [{'test_id': 'bx-1', 'questions_correct': 7, 'questions_total': 10}]}))
            old = os.environ.get('BIXBENCH_RESULTS_JSON')
            os.environ['BIXBENCH_RESULTS_JSON'] = str(out)
            try:
                adapter = BixBenchAdapter(root=td, tests_catalog='missing.json')
                results = adapter.load_run_results()
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]['test_id'], 'bx-1')
                self.assertAlmostEqual(results[0]['score'], 0.7)
                self.assertEqual(results[0]['suite'], 'bixbench')
            finally:
                if old is None:
                    del os.environ['BIXBENCH_RESULTS_JSON']
                else:
                    os.environ['BIXBENCH_RESULTS_JSON'] = old



REPO_ROOT = Path(__file__).resolve().parents[1]


class RealRepoAdapterTests(unittest.TestCase):
    @unittest.skipUnless((REPO_ROOT / 'external' / 'bioagent-bench' / 'src' / 'task_metadata.json').exists(), 'bioagent-bench not cloned')
    def test_bioagent_real_repo(self):
        adapter = BioAgentBenchAdapter(root=str(REPO_ROOT / 'external' / 'bioagent-bench'))
        tests = adapter.list_tests()
        self.assertEqual(len(tests), 10)
        ids = [t['task_id'] for t in tests]
        self.assertIn('alzheimer-mouse', ids)
        self.assertIn('deseq', ids)

    @unittest.skipUnless((REPO_ROOT / 'external' / 'BixBench' / 'bixbench_results' / 'baseline_eval_data').exists(), 'BixBench not cloned')
    def test_bixbench_real_repo_list(self):
        adapter = BixBenchAdapter(root=str(REPO_ROOT / 'external' / 'BixBench'))
        tests = adapter.list_tests()
        self.assertGreater(len(tests), 200)
        ids = [t['test_id'] for t in tests]
        self.assertIn('bix-1_q1', ids)

    @unittest.skipUnless((REPO_ROOT / 'external' / 'BixBench' / 'bixbench_results' / 'baseline_eval_data').exists(), 'BixBench not cloned')
    def test_bixbench_real_repo_load_results(self):
        adapter = BixBenchAdapter(root=str(REPO_ROOT / 'external' / 'BixBench'))
        results = adapter.load_run_results()
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertGreaterEqual(r['score'], 0.0)
            self.assertLessEqual(r['score'], 1.0)
            self.assertEqual(r['suite'], 'bixbench')


if __name__ == '__main__':
    unittest.main()
