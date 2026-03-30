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


class BioAgentBenchIntegrationTests(unittest.TestCase):
    """Tests for BioAgent Bench prepare_task / can_grade / grade integration."""

    def _make_metadata(self, tasks):
        return json.dumps(tasks)

    def _make_adapter_with_metadata(self, td, tasks):
        src_dir = Path(td) / 'src'
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / 'task_metadata.json').write_text(self._make_metadata(tasks))
        adapter = BioAgentBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
        return adapter

    SAMPLE_TASKS = [
        {
            'task_id': 'deseq',
            'name': 'RNA-Seq Differential Expression',
            'description': 'RNA-Seq samples from Candida parapsilosis.',
            'task_prompt': 'Identify differentially expressed genes between planktonic and biofilm conditions.',
            'download_urls': {
                'data': [{'filename': 'data.tar.gz', 'url': 'https://example.com/data.tar.gz'}],
                'reference_data': [],
                'results': [{'filename': 'results.tar.gz', 'url': 'https://example.com/results.tar.gz'}],
            },
        },
        {
            'task_id': 'giab',
            'name': 'GIAB Variant Calling',
            'description': 'Germline variant calling on NA12878.',
            'task_prompt': 'Perform germline variant calling. Output a .vcf.gz file.',
            'download_urls': {
                'data': [{'filename': 'data.tar.gz', 'url': 'https://example.com/data.tar.gz'}],
                'reference_data': [],
                'results': [{'filename': 'results.tar.gz', 'url': 'https://example.com/results.tar.gz'}],
            },
        },
    ]

    # -- Phase 1: Foundation --

    def test_bioagent_list_tests_normalizes_test_id(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            tests = adapter.list_tests()
            self.assertEqual(len(tests), 2)
            for t in tests:
                self.assertIn('test_id', t)
                self.assertIn('task_id', t)
                self.assertEqual(t['test_id'], t['task_id'])

    def test_bioagent_make_result_defaults(self):
        adapter = BioAgentBenchAdapter(root='/tmp/fake')
        result = adapter._make_result('deseq', 0.75)
        self.assertEqual(result['test_id'], 'deseq')
        self.assertEqual(result['suite'], 'bioagent-bench')
        self.assertEqual(result['domain'], 'bioagent-bench')
        self.assertTrue(result['attempted'])
        self.assertAlmostEqual(result['score'], 0.75)
        self.assertEqual(result['criteria_scores'], {})
        self.assertEqual(result['criteria_results'], [])

    def test_bioagent_make_result_not_attempted(self):
        adapter = BioAgentBenchAdapter(root='/tmp/fake')
        result = adapter._make_result('deseq', 0.0, attempted=False)
        self.assertFalse(result['attempted'])
        self.assertAlmostEqual(result['score'], 0.0)

    def test_bioagent_make_result_custom_domain(self):
        adapter = BioAgentBenchAdapter(root='/tmp/fake')
        result = adapter._make_result('deseq', 0.5, domain='transcriptomics')
        self.assertEqual(result['domain'], 'transcriptomics')

    def test_bioagent_build_task_index(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter._build_task_index()
            self.assertEqual(len(adapter._task_index), 2)
            self.assertIn('deseq', adapter._task_index)
            self.assertIn('giab', adapter._task_index)
            self.assertEqual(adapter._task_index['deseq']['task_prompt'], self.SAMPLE_TASKS[0]['task_prompt'])
            self.assertEqual(adapter._task_index['deseq']['name'], 'RNA-Seq Differential Expression')
            self.assertIn('download_urls', adapter._task_index['deseq'])

    def test_bioagent_build_task_index_missing_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
            adapter._build_task_index()
            self.assertEqual(adapter._task_index, {})

    def test_bioagent_setup_includes_tasks_indexed(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            info = adapter.setup()
            self.assertEqual(info['tasks_indexed'], 2)
            self.assertEqual(len(adapter._task_index), 2)

    # -- Phase 2: Preparation --

    def test_bioagent_can_grade_with_results(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            results_dir = Path(td) / 'tasks' / 'deseq' / 'results'
            results_dir.mkdir(parents=True)
            (results_dir / 'up_regulated_genes.csv').write_text('gene_id,log2FoldChange,pvalue,padj\nGENE1,2.5,0.001,0.01\n')
            self.assertTrue(adapter.can_grade('deseq'))

    def test_bioagent_can_grade_no_results(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            self.assertFalse(adapter.can_grade('deseq'))

    def test_bioagent_can_grade_unknown_task(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            self.assertFalse(adapter.can_grade('nonexistent'))

    def test_bioagent_can_grade_before_setup(self):
        adapter = BioAgentBenchAdapter(root='/tmp/fake')
        self.assertFalse(adapter.can_grade('deseq'))

    def test_bioagent_prepare_task_creates_json(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('deseq', str(workspace))
            self.assertTrue(Path(task_path).exists())
            task = json.loads(Path(task_path).read_text())
            self.assertEqual(task['test_id'], 'deseq')
            self.assertIn('prompt', task)
            self.assertIn('context', task)
            self.assertIn('data_files', task['context'])
            self.assertIn('data_description', task['context'])
            self.assertIn('setup_notes', task['context'])

    def test_bioagent_prepare_task_prompt_from_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('deseq', str(workspace))
            task = json.loads(Path(task_path).read_text())
            self.assertIn('differentially expressed genes', task['prompt'])

    def test_bioagent_prepare_task_setup_notes_mentions_tools(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('deseq', str(workspace))
            task = json.loads(Path(task_path).read_text())
            self.assertIn('bio_eval', task['context']['setup_notes'])

    def test_bioagent_prepare_task_data_description(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('deseq', str(workspace))
            task = json.loads(Path(task_path).read_text())
            self.assertIn('Candida parapsilosis', task['context']['data_description'])

    def test_bioagent_prepare_task_symlinks_predownloaded_data(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            data_dir = Path(td) / 'tasks' / 'deseq' / 'data'
            data_dir.mkdir(parents=True)
            (data_dir / 'counts.csv').write_text('gene_id,count\nA,10\n')
            (data_dir / 'metadata.csv').write_text('sample,condition\nS1,treated\n')
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('deseq', str(workspace))
            task = json.loads(Path(task_path).read_text())
            self.assertTrue(len(task['context']['data_files']) > 0)
            for f in task['context']['data_files']:
                self.assertTrue((workspace / f).exists())

    def test_bioagent_prepare_task_includes_download_urls_when_no_local_data(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('deseq', str(workspace))
            task = json.loads(Path(task_path).read_text())
            self.assertIn('https://example.com/data.tar.gz', task['context']['data_description'])

    # -- Phase 2B: BixBench audit --

    def test_bixbench_prepare_task_has_data_description(self):
        with tempfile.TemporaryDirectory() as td:
            csv_dir = Path(td) / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            (csv_dir / 'test.csv').write_text(
                "uuid,short_qid,question,choices,unsure,target,llm_response,predicted,grade,correct,sure\n"
                "a,cap1_q1,What is X?,\"['A) foo', 'B) bar', 'C) baz', 'D) qux']\",False,A,resp,A,1,True,True\n"
            )
            adapter = BixBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('cap1_q1', str(workspace))
            task = json.loads(Path(task_path).read_text())
            self.assertIn('data_description', task['context'])
            self.assertTrue(len(task['context']['data_description']) > 0)

    def test_bixbench_prepare_task_setup_notes_complete(self):
        with tempfile.TemporaryDirectory() as td:
            csv_dir = Path(td) / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            (csv_dir / 'test.csv').write_text(
                "uuid,short_qid,question,choices,unsure,target,llm_response,predicted,grade,correct,sure\n"
                "a,cap1_q1,What is X?,\"['A) foo', 'B) bar', 'C) baz', 'D) qux']\",False,A,resp,A,1,True,True\n"
            )
            adapter = BixBenchAdapter(root=td, tests_catalog=str(Path(td) / 'tests.json'))
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('cap1_q1', str(workspace))
            task = json.loads(Path(task_path).read_text())
            self.assertIn('answer.txt', task['context']['setup_notes'])

    # -- Phase 3: Output Discovery + Comparison --

    def test_bioagent_find_output_csv(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            (Path(td) / 'output.csv').write_text('gene_id,pvalue\nA,0.01\n')
            found = adapter._find_output(Path(td), 'deseq')
            self.assertIsNotNone(found)
            self.assertEqual(found.suffix, '.csv')

    def test_bioagent_find_output_tsv(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            (Path(td) / 'quant.tsv').write_text('transcript_id\tcount\nENST1\t100\n')
            found = adapter._find_output(Path(td), 'transcript-quant')
            self.assertIsNotNone(found)

    def test_bioagent_find_output_vcf(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            (Path(td) / 'variants.vcf').write_text('##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\n')
            found = adapter._find_output(Path(td), 'giab')
            self.assertIsNotNone(found)

    def test_bioagent_find_output_prefers_results(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            (Path(td) / 'results.csv').write_text('gene_id,pvalue\nA,0.01\n')
            (Path(td) / 'other.csv').write_text('x,y\n1,2\n')
            found = adapter._find_output(Path(td), 'deseq')
            self.assertIsNotNone(found)
            self.assertIn('results', found.name)

    def test_bioagent_find_output_empty_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            found = adapter._find_output(Path(td), 'deseq')
            self.assertIsNone(found)

    def test_bioagent_compare_identical_csv(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            content = 'gene_id,log2FoldChange,pvalue\nGENE1,2.5,0.001\nGENE2,-1.3,0.05\nGENE3,3.1,0.0001\n'
            out = Path(td) / 'output.csv'
            ref = Path(td) / 'reference.csv'
            out.write_text(content)
            ref.write_text(content)
            result = adapter._compare_outputs(out, ref)
            self.assertGreater(result['score'], 0.9)

    def test_bioagent_compare_partial_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            ref = Path(td) / 'reference.csv'
            out = Path(td) / 'output.csv'
            ref.write_text('gene_id,log2FoldChange,pvalue\nGENE1,2.5,0.001\nGENE2,-1.3,0.05\nGENE3,3.1,0.0001\n')
            out.write_text('gene_id,log2FoldChange,pvalue\nGENE1,2.4,0.002\nGENE4,0.5,0.8\n')
            result = adapter._compare_outputs(out, ref)
            self.assertGreater(result['score'], 0.0)
            self.assertLess(result['score'], 1.0)

    def test_bioagent_compare_no_column_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            ref = Path(td) / 'reference.csv'
            out = Path(td) / 'output.csv'
            ref.write_text('gene_id,log2FoldChange\nGENE1,2.5\n')
            out.write_text('x,y\n1,2\n')
            result = adapter._compare_outputs(out, ref)
            self.assertAlmostEqual(result['score'], 0.0)

    def test_bioagent_compare_tsv(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            content = 'transcript_id\tcount\nENST1\t100\nENST2\t200\n'
            out = Path(td) / 'output.tsv'
            ref = Path(td) / 'reference.tsv'
            out.write_text(content)
            ref.write_text(content)
            result = adapter._compare_outputs(out, ref)
            self.assertGreater(result['score'], 0.9)

    def test_bioagent_compare_vcf_basic(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BioAgentBenchAdapter(root='/tmp/fake')
            vcf_content = '##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\nchr1\t100\t.\tA\tG\t30\tPASS\t.\n'
            out = Path(td) / 'output.vcf'
            ref = Path(td) / 'reference.vcf'
            out.write_text(vcf_content)
            ref.write_text(vcf_content)
            result = adapter._compare_outputs(out, ref)
            self.assertGreater(result['score'], 0.0)

    # -- Phase 4: Grade --

    def test_bioagent_grade_correct_output(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            results_dir = Path(td) / 'tasks' / 'deseq' / 'results'
            results_dir.mkdir(parents=True)
            content = 'gene_id,log2FoldChange,pvalue,padj\nGENE1,2.5,0.001,0.01\nGENE2,-1.3,0.05,0.1\n'
            (results_dir / 'up_regulated_genes.csv').write_text(content)
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            (workspace / 'results.csv').write_text(content)
            result = adapter.grade('deseq', str(workspace))
            self.assertTrue(result['attempted'])
            self.assertGreater(result['score'], 0.5)
            self.assertEqual(result['suite'], 'bioagent-bench')

    def test_bioagent_grade_no_output(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            result = adapter.grade('deseq', str(workspace))
            self.assertFalse(result['attempted'])
            self.assertAlmostEqual(result['score'], 0.0)

    def test_bioagent_grade_no_reference(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            (workspace / 'results.csv').write_text('gene_id,pvalue\nGENE1,0.01\n')
            result = adapter.grade('deseq', str(workspace))
            self.assertTrue(result['attempted'])
            self.assertAlmostEqual(result['score'], 0.1)

    def test_bioagent_grade_result_structure(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            result = adapter.grade('deseq', str(workspace))
            for key in ('test_id', 'suite', 'domain', 'attempted', 'score', 'criteria_scores', 'criteria_results'):
                self.assertIn(key, result)

    def test_bioagent_grade_domain_is_task_id(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._make_adapter_with_metadata(td, self.SAMPLE_TASKS)
            adapter.setup()
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            result = adapter.grade('deseq', str(workspace))
            self.assertEqual(result['domain'], 'deseq')


if __name__ == '__main__':
    unittest.main()
