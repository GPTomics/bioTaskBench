import ast
import csv
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from harness import runner
from harness.adapters.bixbench import BixBenchAdapter


# ---------------------------------------------------------------------------
# Phase 1: _make_result + _parse_test_id
# ---------------------------------------------------------------------------

class MakeResultTests(unittest.TestCase):
    def test_make_result_defaults(self):
        adapter = BixBenchAdapter(root='/tmp/fake')
        result = adapter._make_result('bix-1_q1', 1.0)
        self.assertEqual(result['test_id'], 'bix-1_q1')
        self.assertEqual(result['suite'], 'bixbench')
        self.assertEqual(result['domain'], 'bixbench')
        self.assertTrue(result['attempted'])
        self.assertAlmostEqual(result['score'], 1.0)
        self.assertEqual(result['criteria_scores'], {})
        self.assertEqual(result['criteria_results'], [])

    def test_make_result_not_attempted(self):
        adapter = BixBenchAdapter(root='/tmp/fake')
        result = adapter._make_result('bix-1_q1', 0.0, attempted=False)
        self.assertFalse(result['attempted'])
        self.assertAlmostEqual(result['score'], 0.0)

    def test_make_result_custom_domain(self):
        adapter = BixBenchAdapter(root='/tmp/fake')
        result = adapter._make_result('bix-1_q1', 1.0, domain='bix-1')
        self.assertEqual(result['domain'], 'bix-1')


class ParseTestIdTests(unittest.TestCase):
    def test_parse_bix1_q1(self):
        adapter = BixBenchAdapter(root='/tmp/fake')
        parsed = adapter._parse_test_id('bix-1_q1')
        self.assertEqual(parsed['capsule'], 'bix-1')
        self.assertEqual(parsed['question_num'], 1)

    def test_parse_bix42_q7(self):
        adapter = BixBenchAdapter(root='/tmp/fake')
        parsed = adapter._parse_test_id('bix-42_q7')
        self.assertEqual(parsed['capsule'], 'bix-42')
        self.assertEqual(parsed['question_num'], 7)

    def test_parse_no_underscore_q(self):
        adapter = BixBenchAdapter(root='/tmp/fake')
        parsed = adapter._parse_test_id('legacy-id')
        self.assertEqual(parsed['capsule'], 'legacy-id')
        self.assertIsNone(parsed['question_num'])


# ---------------------------------------------------------------------------
# Phase 2: Question index from CSV
# ---------------------------------------------------------------------------

def _write_mcq_csv(path, rows):
    fieldnames = ['uuid', 'short_qid', 'question', 'choices', 'unsure', 'target', 'llm_response', 'predicted', 'grade', 'correct', 'sure']
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _make_csv_row(short_qid, question='What is X?', choices=None, target='A', uuid='uuid-1'):
    if choices is None:
        choices = "['(A) answer A', '(B) answer B', '(C) answer C', '(D) answer D']"
    return {'uuid': uuid, 'short_qid': short_qid, 'question': question, 'choices': choices, 'unsure': 'empty', 'target': target, 'llm_response': '', 'predicted': '', 'grade': '1', 'correct': 'True', 'sure': 'False'}


class QuestionIndexTests(unittest.TestCase):
    def test_build_index_from_csv(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'bixbench_llm_baseline_refusal_False_mcq_gpt-4o_1.0.csv', [
                _make_csv_row('bix-1_q1', target='A'),
                _make_csv_row('bix-1_q2', target='B'),
                _make_csv_row('bix-2_q1', target='C'),
            ])
            adapter = BixBenchAdapter(root=str(root))
            adapter._build_question_index()
            self.assertEqual(len(adapter._question_index), 3)
            self.assertIn('bix-1_q1', adapter._question_index)
            self.assertIn('bix-2_q1', adapter._question_index)

    def test_index_deduplicates_first_file_wins(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'aaa_first.csv', [_make_csv_row('bix-1_q1', target='A')])
            _write_mcq_csv(csv_dir / 'zzz_second.csv', [_make_csv_row('bix-1_q1', target='D')])
            adapter = BixBenchAdapter(root=str(root))
            adapter._build_question_index()
            self.assertEqual(adapter._question_index['bix-1_q1']['target'], 'A')

    def test_index_skips_empty_choices(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [
                _make_csv_row('bix-1_q1', choices="['(A) a', '(B) b']"),
                _make_csv_row('bix-1_q2', choices=''),
            ])
            adapter = BixBenchAdapter(root=str(root))
            adapter._build_question_index()
            self.assertIn('bix-1_q1', adapter._question_index)
            self.assertNotIn('bix-1_q2', adapter._question_index)

    def test_index_missing_dir(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BixBenchAdapter(root=str(Path(td) / 'nonexistent'))
            adapter._build_question_index()
            self.assertEqual(len(adapter._question_index), 0)

    def test_setup_populates_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [_make_csv_row('bix-1_q1')])
            adapter = BixBenchAdapter(root=str(root))
            adapter.setup()
            self.assertIn('bix-1_q1', adapter._question_index)

    def test_index_entry_has_required_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [_make_csv_row('bix-1_q1', question='What is DNA?', target='B', uuid='abc-123')])
            adapter = BixBenchAdapter(root=str(root))
            adapter._build_question_index()
            entry = adapter._question_index['bix-1_q1']
            self.assertEqual(entry['question'], 'What is DNA?')
            self.assertEqual(entry['target'], 'B')
            self.assertEqual(entry['uuid'], 'abc-123')
            self.assertIsInstance(entry['choices'], list)
            self.assertEqual(len(entry['choices']), 4)


# ---------------------------------------------------------------------------
# Phase 3: prepare_task
# ---------------------------------------------------------------------------

class PrepareTaskTests(unittest.TestCase):
    def _setup_adapter(self, td):
        root = Path(td)
        csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
        csv_dir.mkdir(parents=True)
        _write_mcq_csv(csv_dir / 'test.csv', [
            _make_csv_row('bix-1_q1', question='What enzyme cuts DNA?', choices="['(A) Ligase', '(B) Restriction enzyme', '(C) Polymerase', '(D) Helicase']", target='B'),
            _make_csv_row('bix-1_q2', question='What is PCR?', target='A'),
        ])
        adapter = BixBenchAdapter(root=str(root))
        adapter.setup()
        return adapter

    def test_prepare_task_writes_task_json(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('bix-1_q1', workspace)
            self.assertTrue(Path(task_path).exists())
            task = json.loads(Path(task_path).read_text())
            self.assertIsInstance(task, dict)

    def test_prepare_task_fields(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('bix-1_q1', workspace)
            task = json.loads(Path(task_path).read_text())
            self.assertEqual(task['test_id'], 'bix-1_q1')
            self.assertIn('What enzyme cuts DNA?', task['prompt'])

    def test_prepare_task_choices_in_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('bix-1_q1', workspace)
            task = json.loads(Path(task_path).read_text())
            for choice in ['Ligase', 'Restriction enzyme', 'Polymerase', 'Helicase']:
                self.assertIn(choice, task['prompt'])

    def test_prepare_task_no_target_leak(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('bix-1_q1', workspace)
            task = json.loads(Path(task_path).read_text())
            setup_notes = task.get('context', {}).get('setup_notes', '')
            self.assertNotIn('target', setup_notes.lower())
            self.assertNotIn('correct answer is B', setup_notes)

    def test_prepare_task_setup_notes_mention_answer_txt(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            task_path = adapter.prepare_task('bix-1_q1', workspace)
            task = json.loads(Path(task_path).read_text())
            setup_notes = task.get('context', {}).get('setup_notes', '')
            self.assertIn('answer.txt', setup_notes)


# ---------------------------------------------------------------------------
# Phase 4: Answer extraction
# ---------------------------------------------------------------------------

class AnswerExtractionTests(unittest.TestCase):
    def test_extract_clean_letter(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'answer.txt').write_text('B')
            adapter = BixBenchAdapter(root='/tmp/fake')
            self.assertEqual(adapter._extract_answer(td), 'B')

    def test_extract_with_whitespace(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'answer.txt').write_text('  A \n')
            adapter = BixBenchAdapter(root='/tmp/fake')
            self.assertEqual(adapter._extract_answer(td), 'A')

    def test_extract_verbose_text(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'answer.txt').write_text('The answer is (C) because of reasons.')
            adapter = BixBenchAdapter(root='/tmp/fake')
            self.assertEqual(adapter._extract_answer(td), 'C')

    def test_extract_xml_format(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'answer.txt').write_text('<answer>D</answer>')
            adapter = BixBenchAdapter(root='/tmp/fake')
            self.assertEqual(adapter._extract_answer(td), 'D')

    def test_extract_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BixBenchAdapter(root='/tmp/fake')
            self.assertEqual(adapter._extract_answer(td), '')

    def test_extract_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'answer.txt').write_text('')
            adapter = BixBenchAdapter(root='/tmp/fake')
            self.assertEqual(adapter._extract_answer(td), '')

    def test_extract_lowercase(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'answer.txt').write_text('b')
            adapter = BixBenchAdapter(root='/tmp/fake')
            self.assertEqual(adapter._extract_answer(td), 'B')


# ---------------------------------------------------------------------------
# Phase 5: grade
# ---------------------------------------------------------------------------

class GradeTests(unittest.TestCase):
    def _setup_adapter(self, td):
        root = Path(td) / 'bixbench'
        root.mkdir()
        csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
        csv_dir.mkdir(parents=True)
        _write_mcq_csv(csv_dir / 'test.csv', [
            _make_csv_row('bix-1_q1', target='A'),
            _make_csv_row('bix-1_q2', target='C'),
        ])
        adapter = BixBenchAdapter(root=str(root))
        adapter.setup()
        return adapter

    def test_grade_correct_answer(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            (workspace / 'answer.txt').write_text('A')
            result = adapter.grade('bix-1_q1', str(workspace))
            self.assertTrue(result['attempted'])
            self.assertAlmostEqual(result['score'], 1.0)

    def test_grade_wrong_answer(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            (workspace / 'answer.txt').write_text('B')
            result = adapter.grade('bix-1_q1', str(workspace))
            self.assertTrue(result['attempted'])
            self.assertAlmostEqual(result['score'], 0.0)

    def test_grade_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            (workspace / 'answer.txt').write_text('a')
            result = adapter.grade('bix-1_q1', str(workspace))
            self.assertAlmostEqual(result['score'], 1.0)

    def test_grade_missing_answer_file(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            result = adapter.grade('bix-1_q1', str(workspace))
            self.assertFalse(result['attempted'])
            self.assertAlmostEqual(result['score'], 0.0)

    def test_grade_verbose_answer(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            (workspace / 'answer.txt').write_text('I think the answer is (C) based on the data.')
            result = adapter.grade('bix-1_q2', str(workspace))
            self.assertAlmostEqual(result['score'], 1.0)

    def test_grade_domain_from_capsule(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = self._setup_adapter(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            (workspace / 'answer.txt').write_text('A')
            result = adapter.grade('bix-1_q1', str(workspace))
            self.assertEqual(result['domain'], 'bix-1')


# ---------------------------------------------------------------------------
# Phase 6: can_grade
# ---------------------------------------------------------------------------

class CanGradeTests(unittest.TestCase):
    def test_can_grade_indexed_question(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [_make_csv_row('bix-1_q1')])
            adapter = BixBenchAdapter(root=str(root))
            adapter.setup()
            self.assertTrue(adapter.can_grade('bix-1_q1'))

    def test_cannot_grade_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [_make_csv_row('bix-1_q1')])
            adapter = BixBenchAdapter(root=str(root))
            adapter.setup()
            self.assertFalse(adapter.can_grade('bix-99_q99'))

    def test_cannot_grade_before_setup(self):
        adapter = BixBenchAdapter(root='/tmp/fake')
        self.assertFalse(adapter.can_grade('bix-1_q1'))


# ---------------------------------------------------------------------------
# Phase 7: Runner integration
# ---------------------------------------------------------------------------

class RunnerIntegrationTests(unittest.TestCase):
    def _make_bixbench_root(self, td):
        root = Path(td) / 'bixbench'
        root.mkdir()
        csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
        csv_dir.mkdir(parents=True)
        _write_mcq_csv(csv_dir / 'test.csv', [
            _make_csv_row('bix-1_q1', target='A'),
            _make_csv_row('bix-1_q2', target='B'),
        ])
        return root

    @patch('harness.runner._run_agent_command')
    def test_runner_uses_prepare_task_and_grade(self, mock_agent):
        mock_agent.return_value = {'agent_cmd': 'echo ok', 'returncode': 0, 'stdout': '', 'stderr': ''}
        with tempfile.TemporaryDirectory() as td:
            root = self._make_bixbench_root(td)
            old_root = os.environ.get('BIXBENCH_ROOT')
            os.environ['BIXBENCH_ROOT'] = str(root)
            try:
                result = runner.run_external_suite('bixbench', output_dir=Path(td) / 'out', agent_cmd='echo ok')
            finally:
                if old_root is None:
                    os.environ.pop('BIXBENCH_ROOT', None)
                else:
                    os.environ['BIXBENCH_ROOT'] = old_root
            self.assertTrue(mock_agent.called)
            payload = result['payload']
            self.assertEqual(payload['status'], 'ok')
            self.assertEqual(len(payload['results']), 2)

    @patch('harness.runner._run_agent_command')
    def test_runner_skips_non_gradable(self, mock_agent):
        mock_agent.return_value = {'agent_cmd': 'echo ok', 'returncode': 0, 'stdout': '', 'stderr': ''}
        with tempfile.TemporaryDirectory() as td:
            root = self._make_bixbench_root(td)
            # Add a tests.json that includes a question NOT in the CSV index
            tests_json = root / 'tests.json'
            tests_json.write_text(json.dumps([
                {'test_id': 'bix-1_q1'},
                {'test_id': 'bix-1_q2'},
                {'test_id': 'bix-99_q99'},
            ]))
            old_root = os.environ.get('BIXBENCH_ROOT')
            os.environ['BIXBENCH_ROOT'] = str(root)
            try:
                result = runner.run_external_suite('bixbench', output_dir=Path(td) / 'out', agent_cmd='echo ok')
            finally:
                if old_root is None:
                    os.environ.pop('BIXBENCH_ROOT', None)
                else:
                    os.environ['BIXBENCH_ROOT'] = old_root
            payload = result['payload']
            test_ids = [r['test_id'] for r in payload['results']]
            self.assertIn('bix-1_q1', test_ids)
            self.assertIn('bix-1_q2', test_ids)
            self.assertNotIn('bix-99_q99', test_ids)

    @patch('harness.runner._run_agent_command')
    def test_runner_test_id_filter(self, mock_agent):
        mock_agent.return_value = {'agent_cmd': 'echo ok', 'returncode': 0, 'stdout': '', 'stderr': ''}
        with tempfile.TemporaryDirectory() as td:
            root = self._make_bixbench_root(td)
            old_root = os.environ.get('BIXBENCH_ROOT')
            os.environ['BIXBENCH_ROOT'] = str(root)
            try:
                result = runner.run_external_suite('bixbench', output_dir=Path(td) / 'out', agent_cmd='echo ok', test_id='bix-1_q2')
            finally:
                if old_root is None:
                    os.environ.pop('BIXBENCH_ROOT', None)
                else:
                    os.environ['BIXBENCH_ROOT'] = old_root
            payload = result['payload']
            test_ids = [r['test_id'] for r in payload['results']]
            self.assertEqual(test_ids, ['bix-1_q2'])

    @patch('harness.runner._run_agent_command')
    def test_runner_domain_filter(self, mock_agent):
        mock_agent.return_value = {'agent_cmd': 'echo ok', 'returncode': 0, 'stdout': '', 'stderr': ''}
        with tempfile.TemporaryDirectory() as td:
            root = self._make_bixbench_root(td)
            # add a third question in a different capsule
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            _write_mcq_csv(csv_dir / 'extra.csv', [_make_csv_row('bix-2_q1', uuid='uuid-2', target='C')])
            old_root = os.environ.get('BIXBENCH_ROOT')
            os.environ['BIXBENCH_ROOT'] = str(root)
            try:
                result = runner.run_external_suite('bixbench', output_dir=Path(td) / 'out', agent_cmd='echo ok', domain='bix-1')
            finally:
                if old_root is None:
                    os.environ.pop('BIXBENCH_ROOT', None)
                else:
                    os.environ['BIXBENCH_ROOT'] = old_root
            payload = result['payload']
            test_ids = [r['test_id'] for r in payload['results']]
            self.assertIn('bix-1_q1', test_ids)
            self.assertIn('bix-1_q2', test_ids)
            self.assertNotIn('bix-2_q1', test_ids)

    @patch('harness.runner._run_agent_command')
    def test_runner_payload_structure(self, mock_agent):
        mock_agent.return_value = {'agent_cmd': 'echo ok', 'returncode': 0, 'stdout': '', 'stderr': ''}
        with tempfile.TemporaryDirectory() as td:
            root = self._make_bixbench_root(td)
            old_root = os.environ.get('BIXBENCH_ROOT')
            os.environ['BIXBENCH_ROOT'] = str(root)
            try:
                result = runner.run_external_suite('bixbench', output_dir=Path(td) / 'out', agent_cmd='echo ok')
            finally:
                if old_root is None:
                    os.environ.pop('BIXBENCH_ROOT', None)
                else:
                    os.environ['BIXBENCH_ROOT'] = old_root
            payload = result['payload']
            self.assertIn('aggregate', payload)
            agg = payload['aggregate']
            self.assertIn('tests_total', agg)
            self.assertIn('coverage', agg)
            self.assertIn('score', agg)


# ---------------------------------------------------------------------------
# Phase 8: Data readiness
# ---------------------------------------------------------------------------

class DataDirTests(unittest.TestCase):
    def test_data_dir_property(self):
        adapter = BixBenchAdapter(root='/tmp/fake_bixbench')
        self.assertEqual(adapter.data_dir, Path('/tmp/fake_bixbench/data/capsules'))

    def test_data_dir_relative_to_root(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BixBenchAdapter(root=td)
            self.assertEqual(adapter.data_dir, Path(td) / 'data' / 'capsules')


class CheckDataReadyTests(unittest.TestCase):
    def test_check_data_ready_no_data_dir(self):
        adapter = BixBenchAdapter(root='/tmp/nonexistent_bixbench_root')
        ready, info = adapter.check_data_ready()
        self.assertFalse(ready)
        self.assertIn('missing', info.lower())

    def test_check_data_ready_empty_data_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'data' / 'capsules').mkdir(parents=True)
            adapter = BixBenchAdapter(root=str(root))
            ready, info = adapter.check_data_ready()
            self.assertFalse(ready)

    def test_check_data_ready_with_capsule_folders(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            capsule_dir = root / 'data' / 'capsules' / 'CapsuleFolder-uuid-1'
            capsule_dir.mkdir(parents=True)
            (capsule_dir / 'data.csv').write_text('col1,col2\n1,2\n')
            adapter = BixBenchAdapter(root=str(root))
            ready, info = adapter.check_data_ready()
            self.assertTrue(ready)

    def test_check_data_ready_reports_capsule_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(3):
                d = root / 'data' / 'capsules' / f'CapsuleFolder-uuid-{i}'
                d.mkdir(parents=True)
                (d / 'data.csv').write_text('a,b\n1,2\n')
            adapter = BixBenchAdapter(root=str(root))
            ready, info = adapter.check_data_ready()
            self.assertTrue(ready)
            self.assertIn('3', info)

    def test_check_data_ready_matches_question_index(self):
        '''check_data_ready should report missing capsules when index has uuids not in data_dir'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [
                _make_csv_row('bix-1_q1', uuid='uuid-aaa'),
                _make_csv_row('bix-2_q1', uuid='uuid-bbb'),
            ])
            # only create one capsule folder
            capsule_dir = root / 'data' / 'capsules' / 'CapsuleFolder-uuid-aaa'
            capsule_dir.mkdir(parents=True)
            (capsule_dir / 'data.csv').write_text('a\n1\n')
            adapter = BixBenchAdapter(root=str(root))
            adapter.setup()
            ready, info = adapter.check_data_ready()
            self.assertFalse(ready)
            self.assertIn('uuid-bbb', info)


# ---------------------------------------------------------------------------
# Phase 9: prepare_task copies capsule data into workspace
# ---------------------------------------------------------------------------

def _setup_adapter_with_data(td, questions=None):
    '''Create adapter with CSV index AND capsule data on disk.'''
    root = Path(td) / 'bixbench'
    root.mkdir()
    csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
    csv_dir.mkdir(parents=True)
    if questions is None:
        questions = [
            _make_csv_row('bix-1_q1', question='What enzyme?', uuid='uuid-aaa', target='B'),
            _make_csv_row('bix-1_q2', question='What is PCR?', uuid='uuid-aaa', target='A'),
            _make_csv_row('bix-2_q1', question='How many sites?', uuid='uuid-bbb', target='C'),
        ]
    _write_mcq_csv(csv_dir / 'test.csv', questions)
    # create capsule data folders matching the uuids
    cap_a = root / 'data' / 'capsules' / 'CapsuleFolder-uuid-aaa'
    cap_a.mkdir(parents=True)
    (cap_a / 'expression_matrix.tsv').write_text('gene\tvalue\nTP53\t42\n')
    (cap_a / 'metadata.xlsx').write_bytes(b'fake-excel-bytes')
    cap_b = root / 'data' / 'capsules' / 'CapsuleFolder-uuid-bbb'
    cap_b.mkdir(parents=True)
    (cap_b / 'variants.vcf').write_text('##fileformat=VCFv4.1\n#CHROM\tPOS\n')
    adapter = BixBenchAdapter(root=str(root))
    adapter.setup()
    return adapter


class PrepareTaskCopiesDataTests(unittest.TestCase):
    def test_prepare_task_copies_capsule_files(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = _setup_adapter_with_data(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            adapter.prepare_task('bix-1_q1', workspace)
            self.assertTrue((workspace / 'expression_matrix.tsv').exists())
            self.assertTrue((workspace / 'metadata.xlsx').exists())

    def test_prepare_task_copies_correct_capsule(self):
        '''bix-2_q1 uses uuid-bbb which has variants.vcf, not expression_matrix.tsv'''
        with tempfile.TemporaryDirectory() as td:
            adapter = _setup_adapter_with_data(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            adapter.prepare_task('bix-2_q1', workspace)
            self.assertTrue((workspace / 'variants.vcf').exists())
            self.assertFalse((workspace / 'expression_matrix.tsv').exists())

    def test_prepare_task_same_capsule_different_questions(self):
        '''bix-1_q1 and bix-1_q2 share uuid-aaa, both should get same data files'''
        with tempfile.TemporaryDirectory() as td:
            adapter = _setup_adapter_with_data(td)
            ws1 = Path(td) / 'ws1'
            ws1.mkdir()
            ws2 = Path(td) / 'ws2'
            ws2.mkdir()
            adapter.prepare_task('bix-1_q1', ws1)
            adapter.prepare_task('bix-1_q2', ws2)
            self.assertTrue((ws1 / 'expression_matrix.tsv').exists())
            self.assertTrue((ws2 / 'expression_matrix.tsv').exists())

    def test_prepare_task_data_files_populated(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = _setup_adapter_with_data(td)
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            task_path = adapter.prepare_task('bix-1_q1', workspace)
            task = json.loads(Path(task_path).read_text())
            data_files = task['context']['data_files']
            self.assertIn('expression_matrix.tsv', data_files)
            self.assertIn('metadata.xlsx', data_files)

    def test_prepare_task_data_files_empty_when_no_capsule(self):
        '''If capsule data folder is missing, data_files should be empty (graceful degradation)'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bixbench'
            root.mkdir()
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [
                _make_csv_row('bix-99_q1', uuid='uuid-missing', target='A'),
            ])
            adapter = BixBenchAdapter(root=str(root))
            adapter.setup()
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            task_path = adapter.prepare_task('bix-99_q1', workspace)
            task = json.loads(Path(task_path).read_text())
            self.assertEqual(task['context']['data_files'], [])

    def test_prepare_task_copies_subdirectories(self):
        '''Capsules may contain subdirectories -- these should be copied too'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bixbench'
            root.mkdir()
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [_make_csv_row('bix-3_q1', uuid='uuid-ccc', target='A')])
            cap = root / 'data' / 'capsules' / 'CapsuleFolder-uuid-ccc'
            (cap / 'subdir').mkdir(parents=True)
            (cap / 'subdir' / 'nested.txt').write_text('nested content')
            (cap / 'top.csv').write_text('a\n1\n')
            adapter = BixBenchAdapter(root=str(root))
            adapter.setup()
            workspace = Path(td) / 'ws'
            workspace.mkdir()
            adapter.prepare_task('bix-3_q1', workspace)
            self.assertTrue((workspace / 'top.csv').exists())
            self.assertTrue((workspace / 'subdir' / 'nested.txt').exists())


# ---------------------------------------------------------------------------
# Phase 10: prep_data -- download and extract capsule data from HF
# ---------------------------------------------------------------------------

def _make_fake_capsule_zip(zip_path, uuid, files=None):
    '''Create a zip matching BixBench CapsuleFolder structure.'''
    if files is None:
        files = {'data.csv': 'a,b\n1,2\n'}
    with zipfile.ZipFile(zip_path, 'w') as zf:
        data_folder = f'CapsuleData-{uuid}'
        notebook_folder = f'CapsuleNotebook-{uuid}'
        for name, content in files.items():
            zf.writestr(f'{data_folder}/{name}', content)
        zf.writestr(f'{notebook_folder}/notebook.ipynb', '{}')


class PrepDataTests(unittest.TestCase):
    def _setup_adapter_with_csvs(self, td, rows=None):
        root = Path(td) / 'bixbench'
        root.mkdir()
        csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
        csv_dir.mkdir(parents=True)
        if rows is None:
            rows = [
                _make_csv_row('bix-1_q1', uuid='uuid-aaa'),
                _make_csv_row('bix-2_q1', uuid='uuid-bbb'),
            ]
        _write_mcq_csv(csv_dir / 'test.csv', rows)
        adapter = BixBenchAdapter(root=str(root))
        adapter.setup()
        return adapter, root

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_creates_data_dir(self, mock_hf):
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td)
            # mock hf_hub_download to create a zip in the expected location
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                uuid = filename.replace('CapsuleFolder-', '').replace('.zip', '')
                _make_fake_capsule_zip(zip_path, uuid)
                return str(zip_path)
            mock_hf.side_effect = fake_download
            adapter.prep_data()
            self.assertTrue(adapter.data_dir.exists())

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_downloads_all_capsules(self, mock_hf):
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td)
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                uuid = filename.replace('CapsuleFolder-', '').replace('.zip', '')
                _make_fake_capsule_zip(zip_path, uuid)
                return str(zip_path)
            mock_hf.side_effect = fake_download
            adapter.prep_data()
            self.assertEqual(mock_hf.call_count, 2)
            called_filenames = sorted(c.kwargs.get('filename', c.args[1] if len(c.args) > 1 else None) for c in mock_hf.call_args_list)
            self.assertIn('CapsuleFolder-uuid-aaa.zip', called_filenames)
            self.assertIn('CapsuleFolder-uuid-bbb.zip', called_filenames)

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_extracts_data_files(self, mock_hf):
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td, rows=[
                _make_csv_row('bix-1_q1', uuid='uuid-aaa'),
            ])
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                _make_fake_capsule_zip(zip_path, 'uuid-aaa', {'results.tsv': 'gene\tscore\nTP53\t0.9\n'})
                return str(zip_path)
            mock_hf.side_effect = fake_download
            adapter.prep_data()
            capsule_dir = adapter.data_dir / 'CapsuleFolder-uuid-aaa'
            self.assertTrue(capsule_dir.exists())
            self.assertTrue((capsule_dir / 'results.tsv').exists())
            self.assertEqual((capsule_dir / 'results.tsv').read_text(), 'gene\tscore\nTP53\t0.9\n')

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_removes_notebook_folder(self, mock_hf):
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td, rows=[
                _make_csv_row('bix-1_q1', uuid='uuid-aaa'),
            ])
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                _make_fake_capsule_zip(zip_path, 'uuid-aaa')
                return str(zip_path)
            mock_hf.side_effect = fake_download
            adapter.prep_data()
            capsule_dir = adapter.data_dir / 'CapsuleFolder-uuid-aaa'
            notebooks = list(capsule_dir.glob('*Notebook*'))
            self.assertEqual(notebooks, [])

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_removes_zip_after_extract(self, mock_hf):
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td, rows=[
                _make_csv_row('bix-1_q1', uuid='uuid-aaa'),
            ])
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                _make_fake_capsule_zip(zip_path, 'uuid-aaa')
                return str(zip_path)
            mock_hf.side_effect = fake_download
            adapter.prep_data()
            zips = list(adapter.data_dir.glob('*.zip'))
            self.assertEqual(zips, [])

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_skips_existing_capsules(self, mock_hf):
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td)
            # pre-create one capsule folder so it gets skipped
            existing = adapter.data_dir / 'CapsuleFolder-uuid-aaa'
            existing.mkdir(parents=True)
            (existing / 'data.csv').write_text('pre-existing')
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                uuid = filename.replace('CapsuleFolder-', '').replace('.zip', '')
                _make_fake_capsule_zip(zip_path, uuid)
                return str(zip_path)
            mock_hf.side_effect = fake_download
            adapter.prep_data()
            # only uuid-bbb should be downloaded
            self.assertEqual(mock_hf.call_count, 1)
            # pre-existing data should be untouched
            self.assertEqual((existing / 'data.csv').read_text(), 'pre-existing')

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_uses_correct_hf_repo(self, mock_hf):
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td, rows=[
                _make_csv_row('bix-1_q1', uuid='uuid-aaa'),
            ])
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                _make_fake_capsule_zip(zip_path, 'uuid-aaa')
                return str(zip_path)
            mock_hf.side_effect = fake_download
            adapter.prep_data()
            call_kwargs = mock_hf.call_args
            self.assertEqual(call_kwargs.kwargs.get('repo_id', call_kwargs.args[0] if call_kwargs.args else None), 'futurehouse/bixbench')
            self.assertEqual(call_kwargs.kwargs.get('repo_type', None), 'dataset')

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_prep_data_check_ready_after(self, mock_hf):
        '''After prep_data, check_data_ready should return True'''
        with tempfile.TemporaryDirectory() as td:
            adapter, root = self._setup_adapter_with_csvs(td)
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                uuid = filename.replace('CapsuleFolder-', '').replace('.zip', '')
                _make_fake_capsule_zip(zip_path, uuid)
                return str(zip_path)
            mock_hf.side_effect = fake_download
            ready_before, _ = adapter.check_data_ready()
            self.assertFalse(ready_before)
            adapter.prep_data()
            ready_after, _ = adapter.check_data_ready()
            self.assertTrue(ready_after)


# ---------------------------------------------------------------------------
# Phase 11: CLI prep-bixbench command
# ---------------------------------------------------------------------------

class CLIPrepBixbenchTests(unittest.TestCase):
    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_cli_prep_bixbench_calls_prep_data(self, mock_hf):
        from harness.cli import main
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bixbench'
            root.mkdir()
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [_make_csv_row('bix-1_q1', uuid='uuid-aaa')])
            def fake_download(repo_id, filename, local_dir, repo_type):
                zip_path = Path(local_dir) / filename
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                _make_fake_capsule_zip(zip_path, 'uuid-aaa')
                return str(zip_path)
            mock_hf.side_effect = fake_download
            old_root = os.environ.get('BIXBENCH_ROOT')
            os.environ['BIXBENCH_ROOT'] = str(root)
            try:
                main(['prep-bixbench'])
            finally:
                if old_root is None:
                    os.environ.pop('BIXBENCH_ROOT', None)
                else:
                    os.environ['BIXBENCH_ROOT'] = old_root
            self.assertTrue(mock_hf.called)

    @patch('harness.adapters.bixbench.hf_hub_download')
    def test_cli_prep_bixbench_check_only(self, mock_hf):
        from harness.cli import main
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bixbench'
            root.mkdir()
            csv_dir = root / 'bixbench_results' / 'baseline_eval_data'
            csv_dir.mkdir(parents=True)
            _write_mcq_csv(csv_dir / 'test.csv', [_make_csv_row('bix-1_q1', uuid='uuid-aaa')])
            old_root = os.environ.get('BIXBENCH_ROOT')
            os.environ['BIXBENCH_ROOT'] = str(root)
            try:
                result = main(['prep-bixbench', '--check'])
            finally:
                if old_root is None:
                    os.environ.pop('BIXBENCH_ROOT', None)
                else:
                    os.environ['BIXBENCH_ROOT'] = old_root
            # --check should NOT download anything
            self.assertFalse(mock_hf.called)
            # should return non-zero when data is missing
            self.assertNotEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
