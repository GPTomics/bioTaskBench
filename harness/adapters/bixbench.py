import ast
import csv
import json
import os
import re
import subprocess
from pathlib import Path


class BixBenchAdapter:
    name = 'bixbench'

    def __init__(self, root=None, tests_catalog=None):
        self.root = Path(root or os.getenv('BIXBENCH_ROOT', 'external/bixbench'))
        self.tests_catalog = Path(tests_catalog or os.getenv('BIXBENCH_TESTS_JSON', self.root / 'tests.json'))
        self.baseline_csv_dir = self.root / 'bixbench_results' / 'baseline_eval_data'
        self.results_json = Path(os.getenv('BIXBENCH_RESULTS_JSON', self.root / 'results.json'))
        self.run_command = os.getenv('BIXBENCH_RUN_CMD')

    def setup(self):
        self._build_question_index()
        return {'root': str(self.root), 'root_exists': self.root.exists(), 'tests_catalog': str(self.tests_catalog), 'questions_indexed': len(self._question_index)}

    def _build_question_index(self):
        self._question_index = {}
        if not self.baseline_csv_dir.exists():
            return
        for csv_path in sorted(self.baseline_csv_dir.glob('*.csv')):
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                for row in reader:
                    qid = row.get('short_qid', '')
                    choices_str = row.get('choices', '')
                    if not qid or not choices_str:
                        continue
                    if qid in self._question_index:
                        continue
                    try:
                        choices = ast.literal_eval(choices_str)
                    except (ValueError, SyntaxError):
                        continue
                    self._question_index[qid] = {
                        'uuid': row.get('uuid', ''),
                        'question': row.get('question', ''),
                        'choices': choices,
                        'target': row.get('target', ''),
                    }

    def list_tests(self):
        if self.tests_catalog.exists():
            with self.tests_catalog.open() as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('tests', [])
        if self.baseline_csv_dir.exists():
            return self._list_tests_from_csvs()
        return []

    def _list_tests_from_csvs(self):
        qids = set()
        for csv_path in sorted(self.baseline_csv_dir.glob('*.csv')):
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                for row in reader:
                    qid = row.get('short_qid')
                    if qid:
                        qids.add(qid)
        return [{'test_id': qid} for qid in sorted(qids)]

    def _parse_test_id(self, test_id):
        parts = test_id.split('_q', 1)
        if len(parts) == 2 and parts[1].isdigit():
            return {'test_id': test_id, 'capsule': parts[0], 'question_num': int(parts[1])}
        return {'test_id': test_id, 'capsule': test_id, 'question_num': None}

    def _make_result(self, test_id, score, attempted=True, domain=None):
        return {
            'test_id': test_id,
            'suite': self.name,
            'domain': domain or self.name,
            'attempted': attempted,
            'score': score,
            'criteria_scores': {},
            'criteria_results': [],
        }

    def _extract_answer(self, workspace_dir):
        answer_path = Path(workspace_dir) / 'answer.txt'
        if not answer_path.exists():
            return ''
        text = answer_path.read_text().strip()
        if not text:
            return ''
        if len(text) == 1 and text.upper() in 'ABCD':
            return text.upper()
        xml_match = re.search(r'<answer>\s*([A-Da-d])\s*</answer>', text)
        if xml_match:
            return xml_match.group(1).upper()
        paren_match = re.search(r'\(([A-Da-d])\)', text)
        if paren_match:
            return paren_match.group(1).upper()
        bare_match = re.search(r'\b([A-Da-d])\b', text)
        if bare_match:
            return bare_match.group(1).upper()
        for ch in text:
            if ch.isalpha():
                return ch.upper()
        return ''

    def prepare_task(self, test_id, workspace_dir):
        workspace_dir = Path(workspace_dir)
        entry = self._question_index[test_id]
        choices_text = '\n'.join(entry['choices'])
        prompt = f'{entry["question"]}\n\n{choices_text}'
        task = {
            'test_id': test_id,
            'prompt': prompt,
            'context': {
                'data_files': [],
                'data_description': f'BixBench MCQ question from capsule {self._parse_test_id(test_id)["capsule"]}',
                'setup_notes': 'Write your answer to answer.txt. Include ONLY the single letter (A, B, C, or D) corresponding to the best answer.',
            },
        }
        task_path = workspace_dir / 'task.json'
        task_path.write_text(json.dumps(task, indent=2))
        return str(task_path)

    def can_grade(self, test_id):
        return test_id in getattr(self, '_question_index', {})

    def grade(self, test_id, workspace_dir):
        parsed = self._parse_test_id(test_id)
        domain = parsed['capsule']
        entry = self._question_index.get(test_id)
        if not entry:
            return self._make_result(test_id, 0.0, attempted=False, domain=domain)
        predicted = self._extract_answer(workspace_dir)
        if not predicted:
            return self._make_result(test_id, 0.0, attempted=False, domain=domain)
        target_norm = re.sub(r'[^a-zA-Z0-9]', '', entry['target']).lower()
        predicted_norm = re.sub(r'[^a-zA-Z0-9]', '', predicted).lower()
        score = 1.0 if predicted_norm == target_norm else 0.0
        return self._make_result(test_id, score, domain=domain)

    def normalize_score(self, raw_result):
        if isinstance(raw_result, (int, float)):
            return max(0.0, min(1.0, float(raw_result)))
        correct = float(raw_result.get('questions_correct', raw_result.get('correct', 0)))
        total = float(raw_result.get('questions_total', raw_result.get('total', 0)))
        if total <= 0:
            return 0.0
        return max(0.0, min(1.0, correct / total))

    def load_run_results(self):
        if self.results_json.exists():
            with self.results_json.open() as f:
                data = json.load(f)
            items = data.get('results', []) if isinstance(data, dict) else data
            results = []
            for item in items:
                score = self.normalize_score(item)
                results.append({
                    'test_id': str(item.get('test_id', item.get('id', f'case-{len(results)+1}'))),
                    'suite': self.name, 'domain': self.name,
                    'attempted': bool(item.get('attempted', True)), 'score': score,
                    'criteria_scores': {}, 'criteria_results': [],
                })
            return results
        if self.baseline_csv_dir.exists():
            return self._load_results_from_csv()
        return []

    def _load_results_from_csv(self):
        csv_files = sorted(self.baseline_csv_dir.glob('*.csv'))
        if not csv_files:
            return []
        by_qid = {}
        with csv_files[0].open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = row.get('short_qid')
                if not qid:
                    continue
                if qid not in by_qid:
                    by_qid[qid] = []
                by_qid[qid].append(int(row.get('grade', 0)))
        results = []
        for qid in sorted(by_qid):
            grades = by_qid[qid]
            score = sum(grades) / len(grades) if grades else 0.0
            results.append({
                'test_id': qid, 'suite': self.name, 'domain': self.name,
                'attempted': True, 'score': score,
                'criteria_scores': {}, 'criteria_results': [],
            })
        return results

    def run_all(self, model=None, skills_path=None, effort=None):
        if not self.run_command:
            return {'executed': False, 'message': 'BIXBENCH_RUN_CMD not configured'}
        try:
            env = os.environ.copy()
            if model:
                env['BENCHMARK_MODEL'] = str(model)
            if skills_path:
                env['BENCHMARK_SKILLS_PATH'] = str(skills_path)
            if effort:
                env['BENCHMARK_EFFORT'] = str(effort)
            completed = subprocess.run(self.run_command, shell=True, cwd=self.root, env=env, capture_output=True, text=True)
            return {
                'executed': True,
                'returncode': completed.returncode,
                'stdout': completed.stdout[-8000:],
                'stderr': completed.stderr[-8000:],
            }
        except Exception as e:
            return {'executed': True, 'returncode': 1, 'stdout': '', 'stderr': str(e)}
