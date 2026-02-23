import json
import os
import subprocess
from pathlib import Path


class BioCoderAdapter:
    name = 'biocoder'

    def __init__(self, root=None, tests_catalog=None):
        self.root = Path(root or os.getenv('BIOCODER_ROOT', 'external/biocoder'))
        self.tests_catalog = Path(tests_catalog or os.getenv('BIOCODER_TESTS_JSON', self.root / 'tests.json'))
        self.results_json = Path(os.getenv('BIOCODER_RESULTS_JSON', self.root / 'results.json'))
        self.run_command = os.getenv('BIOCODER_RUN_CMD')

    def setup(self):
        return {'root': str(self.root), 'root_exists': self.root.exists(), 'tests_catalog': str(self.tests_catalog)}

    def list_tests(self):
        if self.tests_catalog.exists():
            with self.tests_catalog.open() as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('tests', [])
        return []

    def run_test(self, test_id, agent_config):
        raise NotImplementedError('BioCoder execution is not yet wired in this repository')

    def grade(self, test_id, outputs):
        raise NotImplementedError('BioCoder grading is not yet wired in this repository')

    def normalize_score(self, raw_result):
        if isinstance(raw_result, (int, float)):
            return 1.0 if float(raw_result) > 0 else 0.0
        passed = float(raw_result.get('tests_passed', raw_result.get('passed', 0)))
        total = float(raw_result.get('tests_total', raw_result.get('total', 0)))
        if total <= 0:
            return 0.0
        return max(0.0, min(1.0, passed / total))

    def load_run_results(self):
        if not self.results_json.exists():
            return []
        with self.results_json.open() as f:
            data = json.load(f)
        items = data.get('results', []) if isinstance(data, dict) else data
        results = []
        for item in items:
            score = self.normalize_score(item)
            results.append(
                {
                    'test_id': str(item.get('test_id', item.get('id', f'case-{len(results)+1}'))),
                    'suite': self.name,
                    'domain': self.name,
                    'attempted': bool(item.get('attempted', True)),
                    'score': score,
                    'criteria_scores': {},
                    'criteria_results': [],
                }
            )
        return results

    def run_all(self, model=None, skills_path=None):
        if not self.run_command:
            return {'executed': False, 'message': 'BIOCODER_RUN_CMD not configured'}
        try:
            env = os.environ.copy()
            if model:
                env['BENCHMARK_MODEL'] = str(model)
            if skills_path:
                env['BENCHMARK_SKILLS_PATH'] = str(skills_path)
            completed = subprocess.run(self.run_command, shell=True, cwd=self.root, env=env, capture_output=True, text=True)
            return {
                'executed': True,
                'returncode': completed.returncode,
                'stdout': completed.stdout[-8000:],
                'stderr': completed.stderr[-8000:],
            }
        except Exception as e:
            return {'executed': True, 'returncode': 1, 'stdout': '', 'stderr': str(e)}
