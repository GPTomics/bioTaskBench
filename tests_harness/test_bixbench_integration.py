import ast
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == '__main__':
    unittest.main()
