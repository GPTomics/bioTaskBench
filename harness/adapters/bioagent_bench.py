import json
import math
import os
import subprocess
from pathlib import Path

from harness.grader import _detect_delimiter, _jaccard, _paired_numeric_vectors, _pearson, _read_elements, _read_header, _read_rows


class BioAgentBenchAdapter:
    name = 'bioagent-bench'

    def __init__(self, root=None, tests_catalog=None):
        self.root = Path(root or os.getenv('BIOAGENT_BENCH_ROOT', 'external/bioagent-bench'))
        self.tests_catalog = Path(tests_catalog or os.getenv('BIOAGENT_BENCH_TESTS_JSON', self.root / 'tests.json'))
        self.results_json = Path(os.getenv('BIOAGENT_BENCH_RESULTS_JSON', self.root / 'results.json'))
        self.run_command = os.getenv('BIOAGENT_BENCH_RUN_CMD')
        self._task_index = {}

    def setup(self):
        self._build_task_index()
        return {'root': str(self.root), 'root_exists': self.root.exists(), 'tests_catalog': str(self.tests_catalog), 'tasks_indexed': len(self._task_index)}

    def _build_task_index(self):
        self._task_index = {}
        metadata = self.root / 'src' / 'task_metadata.json'
        if not metadata.exists():
            return
        with metadata.open() as f:
            data = json.load(f)
        if isinstance(data, list):
            self._task_index = {entry['task_id']: entry for entry in data if 'task_id' in entry}

    def _normalize_test_ids(self, tests):
        for entry in tests:
            if 'test_id' not in entry and 'task_id' in entry:
                entry['test_id'] = entry['task_id']
        return tests

    def list_tests(self):
        if self.tests_catalog.exists():
            with self.tests_catalog.open() as f:
                data = json.load(f)
            if isinstance(data, list):
                return self._normalize_test_ids(data)
            if isinstance(data, dict):
                return self._normalize_test_ids(data.get('tests', []))
        metadata = self.root / 'src' / 'task_metadata.json'
        if metadata.exists():
            with metadata.open() as f:
                data = json.load(f)
            if isinstance(data, list):
                return self._normalize_test_ids(data)
        return []

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

    def can_grade(self, test_id):
        if not self._task_index:
            return False
        if test_id not in self._task_index:
            return False
        results_dir = self.root / 'tasks' / test_id / 'results'
        return results_dir.exists() and any(results_dir.iterdir())

    def prepare_task(self, test_id, workspace_dir):
        workspace_dir = Path(workspace_dir)
        entry = self._task_index[test_id]
        data_files = []
        data_dir = self.root / 'tasks' / test_id / 'data'
        if data_dir.exists() and any(data_dir.iterdir()):
            link = workspace_dir / 'data'
            if not link.exists():
                os.symlink(str(data_dir.resolve()), str(link))
            data_files = [f'data/{f.name}' for f in data_dir.iterdir() if f.is_file()]

        description = entry.get('description', f'BioAgent Bench task: {entry.get("name", test_id)}')
        if not data_files:
            urls = entry.get('download_urls', {}).get('data', [])
            if urls:
                url_lines = '\n'.join(f'- {u["filename"]}: {u["url"]}' for u in urls)
                description += f'\n\nDownload the input data from:\n{url_lines}'
            ref_urls = entry.get('download_urls', {}).get('reference_data', [])
            if ref_urls:
                ref_lines = '\n'.join(f'- {u["filename"]}: {u["url"]}' for u in ref_urls)
                description += f'\n\nReference data:\n{ref_lines}'

        setup_notes = ('Available tools in bio_eval conda env: samtools, bedtools, bcftools, STAR, salmon, '
                       'R with DESeq2/edgeR/limma, Python with scipy/pandas/numpy/statsmodels/scanpy. '
                       'Produce output files in the current working directory following the format specified in the prompt.')

        task = {
            'test_id': test_id,
            'prompt': entry['task_prompt'],
            'context': {
                'data_files': data_files,
                'data_description': description,
                'setup_notes': setup_notes,
            },
        }
        task_path = workspace_dir / 'task.json'
        task_path.write_text(json.dumps(task, indent=2))
        return str(task_path)

    def _find_output(self, directory, task_id):
        directory = Path(directory)
        results_named = []
        other_tabular = []
        vcf_files = []
        for p in directory.rglob('*'):
            if not p.is_file():
                continue
            name_lower = p.name.lower()
            if name_lower == 'task.json':
                continue
            if p.suffix in ('.csv', '.tsv'):
                if 'result' in name_lower or 'output' in name_lower:
                    results_named.append(p)
                else:
                    other_tabular.append(p)
            elif p.suffix in ('.vcf',) or name_lower.endswith('.vcf.gz'):
                vcf_files.append(p)
        if results_named:
            return results_named[0]
        if other_tabular:
            return other_tabular[0]
        if vcf_files:
            return vcf_files[0]
        return None

    def _compare_outputs(self, output_path, reference_path):
        output_path, reference_path = Path(output_path), Path(reference_path)
        scores = {}

        is_vcf = output_path.suffix == '.vcf' or output_path.name.endswith('.vcf.gz')
        if is_vcf:
            return self._compare_vcf(output_path, reference_path)

        try:
            out_header = set(_read_header(output_path))
            ref_header = set(_read_header(reference_path))
        except Exception:
            return {'score': 0.0}

        union = out_header | ref_header
        scores['column_overlap'] = len(out_header & ref_header) / len(union) if union else 0.0

        shared = out_header & ref_header
        if not shared:
            scores['score'] = 0.0
            return scores

        id_col = self._find_id_column(shared, reference_path)
        if id_col:
            ref_ids = _read_elements(reference_path, id_col)
            out_ids = _read_elements(output_path, id_col)
            scores['id_overlap'] = _jaccard(ref_ids, out_ids)

        numeric_cols = self._find_numeric_columns(shared, reference_path)
        if numeric_cols and id_col:
            correlations = []
            for col in numeric_cols:
                x, y = _paired_numeric_vectors(reference_path, output_path, col, join_field=id_col)
                if len(x) >= 2:
                    r = _pearson(x, y)
                    if not math.isnan(r):
                        correlations.append(max(0.0, r))
            if correlations:
                scores['numeric_correlation'] = sum(correlations) / len(correlations)

        weights = {'column_overlap': 0.2, 'id_overlap': 0.4, 'numeric_correlation': 0.4}
        total_w, weighted_sum = 0.0, 0.0
        for k, w in weights.items():
            if k in scores:
                total_w += w
                weighted_sum += w * scores[k]
        scores['score'] = weighted_sum / total_w if total_w > 0 else 0.0
        return scores

    def _compare_vcf(self, output_path, reference_path):
        try:
            text = output_path.read_text(errors='replace') if output_path.suffix == '.vcf' else ''
            has_header = '#CHROM' in text
            data_lines = [l for l in text.strip().split('\n') if l and not l.startswith('#')]
            has_data = len(data_lines) > 0
            score = 0.0
            if has_header:
                score += 0.5
            if has_data:
                score += 0.5
            return {'score': score, 'has_header': has_header, 'data_lines': len(data_lines)}
        except Exception:
            return {'score': 0.0}

    def _find_id_column(self, shared_columns, reference_path):
        rows = _read_rows(reference_path)
        if not rows:
            return None
        id_candidates = [c for c in shared_columns if any(k in c.lower() for k in ('id', 'name', 'gene', 'transcript', 'pathway', 'cluster', 'species', 'chrom', 'otu'))]
        if id_candidates:
            return id_candidates[0]
        for col in sorted(shared_columns):
            vals = [str(row.get(col, '')) for row in rows[:10]]
            if all(v and not self._is_numeric(v) for v in vals):
                return col
        return None

    def _find_numeric_columns(self, shared_columns, reference_path):
        rows = _read_rows(reference_path)
        if not rows:
            return []
        numeric = []
        for col in shared_columns:
            vals = [str(row.get(col, '')) for row in rows[:10] if row.get(col)]
            if vals and all(self._is_numeric(v) for v in vals):
                numeric.append(col)
        return numeric

    @staticmethod
    def _is_numeric(value):
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def grade(self, test_id, workspace_dir):
        workspace_dir = Path(workspace_dir)
        domain = test_id

        output_path = self._find_output(workspace_dir, test_id)
        if not output_path:
            return self._make_result(test_id, 0.0, attempted=False, domain=domain)

        ref_dir = self.root / 'tasks' / test_id / 'results'
        ref_path = self._find_output(ref_dir, test_id) if ref_dir.exists() else None
        if not ref_path:
            return self._make_result(test_id, 0.1, domain=domain)

        comparison = self._compare_outputs(output_path, ref_path)
        return self._make_result(test_id, comparison['score'], domain=domain)

    def normalize_score(self, raw_result):
        if isinstance(raw_result, (int, float)):
            return max(0.0, min(1.0, float(raw_result)))
        steps_completed = float(raw_result.get('steps_completed', 0))
        steps_to_completion = float(raw_result.get('steps_to_completion', 0))
        if steps_to_completion <= 0:
            return 0.0
        return max(0.0, min(1.0, steps_completed / steps_to_completion))

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

    def run_all(self, model=None, skills_path=None, effort=None):
        if not self.run_command:
            return {'executed': False, 'message': 'BIOAGENT_BENCH_RUN_CMD not configured'}
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
