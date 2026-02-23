import tempfile
import unittest
import json
import os
from pathlib import Path

from harness import cli


class RunnerCliSmokeTests(unittest.TestCase):
    def _write_minimal_suite(self, root):
        tests = Path(root) / 'tests' / 'd'
        case = tests / 't1'
        case.mkdir(parents=True)
        (tests / 'manifest.json').write_text('{"domain":"d","display_name":"D","description":"x","tests":[{"test_id":"t1"}]}')
        (case / 'task.json').write_text('{"test_id":"t1","version":"1.0","domain":"d","difficulty":"basic","prompt":"p","context":{},"evaluation":{"type":"multi_criteria","criteria":[{"name":"x","type":"file_check","description":"d","weight":1.0,"target_pattern":"*.txt"}]},"metadata":{}}')
        return Path(root) / 'tests'

    def test_validate_runs(self):
        with tempfile.TemporaryDirectory() as td:
            tests_root = self._write_minimal_suite(td)
            code = cli.main(['validate', '--tests-root', str(tests_root)])
            self.assertEqual(code, 0)

    def test_validate_allow_missing_expected(self):
        with tempfile.TemporaryDirectory() as td:
            tests = Path(td) / 'tests' / 'd'
            case = tests / 't1'
            case.mkdir(parents=True)
            (tests / 'manifest.json').write_text('{"domain":"d","display_name":"D","description":"x","tests":[{"test_id":"t1"}]}')
            (case / 'task.json').write_text('{"test_id":"t1","version":"1.0","domain":"d","difficulty":"basic","prompt":"p","context":{},"evaluation":{"type":"multi_criteria","criteria":[{"name":"x","type":"set_overlap","description":"d","weight":1.0,"expected_file":"expected/missing.tsv","target_file":"out.tsv","metric":"element_jaccard","field":"id"}]},"metadata":{}}')
            tests_root = Path(td) / 'tests'
            self.assertEqual(cli.main(['validate', '--tests-root', str(tests_root)]), 1)
            self.assertEqual(cli.main(['validate', '--tests-root', str(tests_root), '--allow-missing-expected']), 0)

    def test_run_compare_report(self):
        with tempfile.TemporaryDirectory() as td:
            tests_root = self._write_minimal_suite(td)
            out_a = Path(td) / 'results_a'
            out_b = Path(td) / 'results_b'

            self.assertEqual(
                cli.main(
                    [
                        'run',
                        '--suite',
                        'biotaskbench',
                        '--model',
                        'test-model',
                        '--skills-path',
                        '/tmp/skills',
                        '--tests-root',
                        str(tests_root),
                        '--output',
                        str(out_a),
                    ]
                ),
                0,
            )
            self.assertEqual(cli.main(['run', '--suite', 'biotaskbench', '--tests-root', str(tests_root), '--output', str(out_b)]), 0)

            run_a = next(out_a.glob('run-*/run.json'))
            run_b_dir = next(out_b.glob('run-*'))
            payload = json.loads(run_a.read_text())
            self.assertEqual(payload['model'], 'test-model')
            self.assertEqual(payload['skills_path'], '/tmp/skills')
            self.assertEqual(cli.main(['compare', str(run_a), str(run_b_dir)]), 0)

            report_path = Path(td) / 'report.md'
            self.assertEqual(cli.main(['report', str(run_a), str(run_b_dir), '--output', str(report_path)]), 0)
            self.assertTrue(report_path.exists())
            text = report_path.read_text()
            self.assertIn('## Delta (Run 2 - Run 1)', text)
            self.assertIn('- domains:', text)
            self.assertIn('completion_rate_delta', text)

    def test_run_with_agent_cmd(self):
        with tempfile.TemporaryDirectory() as td:
            tests_root = self._write_minimal_suite(td)
            out_dir = Path(td) / 'results_agent_cmd'
            cmd = "printf 'ok\\n' > out.txt"
            self.assertEqual(
                cli.main(['run', '--suite', 'biotaskbench', '--tests-root', str(tests_root), '--agent-cmd', cmd, '--output', str(out_dir)]),
                0,
            )
            run_json = next(out_dir.glob('run-*/run.json'))
            payload = json.loads(run_json.read_text())
            self.assertEqual(payload['aggregate']['tests_total'], 1)
            self.assertEqual(payload['aggregate']['tests_attempted'], 1)
            self.assertAlmostEqual(payload['aggregate']['score_overall'], 1.0)

    def test_run_all_and_audits(self):
        with tempfile.TemporaryDirectory() as td:
            tests_root = self._write_minimal_suite(td)
            out_dir = Path(td) / 'results_all'
            self.assertEqual(cli.main(['run', '--suite', 'all', '--tests-root', str(tests_root), '--output', str(out_dir)]), 0)

            run_all = next(out_dir.glob('run-all-*/run.json'))
            payload = json.loads(run_all.read_text())
            self.assertEqual(payload['suite'], 'all')
            self.assertIn('aggregate', payload)
            self.assertIn('suites', payload['aggregate'])

            self.assertEqual(cli.main(['audit-data', '--tests-root', str(tests_root)]), 0)
            self.assertEqual(cli.main(['audit-flaky', str(run_all), str(run_all), '--threshold', '0.3']), 0)
            self.assertEqual(cli.main(['adapter-status']), 0)

    def test_external_suite_loads_results_json(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / 'external_results'
            ext_results = Path(td) / 'bioagent_results.json'
            ext_results.write_text(
                json.dumps({'results': [{'test_id': 'ba-1', 'steps_completed': 3, 'steps_to_completion': 4, 'attempted': True}]})
            )

            old = os.environ.get('BIOAGENT_BENCH_RESULTS_JSON')
            os.environ['BIOAGENT_BENCH_RESULTS_JSON'] = str(ext_results)
            try:
                self.assertEqual(cli.main(['run', '--suite', 'bioagent-bench', '--output', str(out_dir)]), 0)
            finally:
                if old is None:
                    del os.environ['BIOAGENT_BENCH_RESULTS_JSON']
                else:
                    os.environ['BIOAGENT_BENCH_RESULTS_JSON'] = old

            run_json = next(out_dir.glob('bioagent-bench-run-*/run.json'))
            payload = json.loads(run_json.read_text())
            self.assertEqual(payload['status'], 'ok')
            self.assertEqual(payload['aggregate']['tests_total'], 1)
            self.assertAlmostEqual(payload['aggregate']['score_overall'], 0.75)

    def test_external_suite_run_command_generates_results(self):
        with tempfile.TemporaryDirectory() as td:
            ext_root = Path(td) / 'ext_bioagent'
            ext_root.mkdir(parents=True, exist_ok=True)
            out_dir = Path(td) / 'external_results_cmd'
            cmd = (
                "python -c \"import json; from pathlib import Path; "
                "Path('results.json').write_text(json.dumps({'results':[{'test_id':'ba-2','steps_completed':1,'steps_to_completion':2,'attempted':True}]}))\""
            )

            old_root = os.environ.get('BIOAGENT_BENCH_ROOT')
            old_cmd = os.environ.get('BIOAGENT_BENCH_RUN_CMD')
            old_res = os.environ.get('BIOAGENT_BENCH_RESULTS_JSON')
            os.environ['BIOAGENT_BENCH_ROOT'] = str(ext_root)
            os.environ['BIOAGENT_BENCH_RUN_CMD'] = cmd
            os.environ['BIOAGENT_BENCH_RESULTS_JSON'] = str(ext_root / 'results.json')
            try:
                self.assertEqual(cli.main(['run', '--suite', 'bioagent-bench', '--output', str(out_dir)]), 0)
            finally:
                if old_root is None:
                    del os.environ['BIOAGENT_BENCH_ROOT']
                else:
                    os.environ['BIOAGENT_BENCH_ROOT'] = old_root
                if old_cmd is None:
                    del os.environ['BIOAGENT_BENCH_RUN_CMD']
                else:
                    os.environ['BIOAGENT_BENCH_RUN_CMD'] = old_cmd
                if old_res is None:
                    del os.environ['BIOAGENT_BENCH_RESULTS_JSON']
                else:
                    os.environ['BIOAGENT_BENCH_RESULTS_JSON'] = old_res

            run_json = next(out_dir.glob('bioagent-bench-run-*/run.json'))
            payload = json.loads(run_json.read_text())
            self.assertEqual(payload['status'], 'ok')
            self.assertTrue(payload['adapter_execution']['executed'])
            self.assertEqual(payload['adapter_execution']['returncode'], 0)
            self.assertEqual(payload['aggregate']['tests_total'], 1)
            self.assertAlmostEqual(payload['aggregate']['score_overall'], 0.5)

    def test_external_suite_run_command_bad_root_reports_error(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / 'external_results_bad_cmd'
            old_root = os.environ.get('BIOAGENT_BENCH_ROOT')
            old_cmd = os.environ.get('BIOAGENT_BENCH_RUN_CMD')
            os.environ['BIOAGENT_BENCH_ROOT'] = str(Path(td) / 'does_not_exist')
            os.environ['BIOAGENT_BENCH_RUN_CMD'] = "echo should-not-run"
            try:
                self.assertEqual(cli.main(['run', '--suite', 'bioagent-bench', '--output', str(out_dir)]), 0)
            finally:
                if old_root is None:
                    del os.environ['BIOAGENT_BENCH_ROOT']
                else:
                    os.environ['BIOAGENT_BENCH_ROOT'] = old_root
                if old_cmd is None:
                    del os.environ['BIOAGENT_BENCH_RUN_CMD']
                else:
                    os.environ['BIOAGENT_BENCH_RUN_CMD'] = old_cmd

            run_json = next(out_dir.glob('bioagent-bench-run-*/run.json'))
            payload = json.loads(run_json.read_text())
            self.assertEqual(payload['status'], 'error')
            self.assertIn('adapter execution command failed', payload['message'])


if __name__ == '__main__':
    unittest.main()
