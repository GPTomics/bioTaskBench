import datetime
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from harness import grader, reporter, schemas
from harness.adapters.bioagent_bench import BioAgentBenchAdapter
from harness.adapters.biocoder import BioCoderAdapter
from harness.adapters.bixbench import BixBenchAdapter


def _copy_task_inputs(task, test_dir, workspace_dir):
    data_dir = Path(test_dir) / 'data'
    for rel in task.get('context', {}).get('data_files', []):
        src = data_dir / rel
        dst = Path(workspace_dir) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)


def _run_agent_command(agent_cmd, task_path, test_dir, workspace_dir, model=None, skills_path=None, timeout_seconds=600):
    env = os.environ.copy()
    env['BIOTASKBENCH_TASK_JSON'] = str(task_path)
    env['BIOTASKBENCH_TEST_DIR'] = str(test_dir)
    env['BIOTASKBENCH_WORKSPACE'] = str(workspace_dir)
    if model:
        env['BENCHMARK_MODEL'] = str(model)
    if skills_path:
        env['BENCHMARK_SKILLS_PATH'] = str(skills_path)
    completed = subprocess.run(
        agent_cmd,
        shell=True,
        cwd=workspace_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        'agent_cmd': agent_cmd,
        'returncode': completed.returncode,
        'stdout': completed.stdout[-8000:],
        'stderr': completed.stderr[-8000:],
    }


def discover_tests(tests_root='tests', domain=None, test_id=None):
    tests_root = Path(tests_root)
    found = []

    if domain:
        domain_dirs = [tests_root / domain]
    else:
        domain_dirs = [d for d in tests_root.iterdir() if d.is_dir()]

    for domain_dir in sorted(domain_dirs):
        if not domain_dir.exists():
            continue

        manifest_path = domain_dir / 'manifest.json'
        if manifest_path.exists():
            manifest = schemas.load_json(manifest_path)
            tests = [t['test_id'] for t in manifest.get('tests', []) if 'test_id' in t]
            for tid in tests:
                if test_id and tid != test_id:
                    continue
                task_path = domain_dir / tid / 'task.json'
                if task_path.exists():
                    found.append({'domain': domain_dir.name, 'test_id': tid, 'task_path': task_path})
        else:
            for task_path in sorted(domain_dir.glob('*/task.json')):
                tid = task_path.parent.name
                if test_id and tid != test_id:
                    continue
                found.append({'domain': domain_dir.name, 'test_id': tid, 'task_path': task_path})

    return found


def validate_tests(tests_root='tests', domain=None, test_id=None, allow_missing_expected=False):
    tests_root = Path(tests_root)
    errors = []

    if domain:
        domain_dirs = [tests_root / domain]
    else:
        domain_dirs = [d for d in tests_root.iterdir() if d.is_dir()]

    for domain_dir in sorted(domain_dirs):
        manifest_path = domain_dir / 'manifest.json'
        if manifest_path.exists():
            manifest = schemas.load_json(manifest_path)
            for error in schemas.validate_manifest(manifest, manifest_path):
                errors.append({'path': str(manifest_path), 'error': error})

    for item in discover_tests(tests_root, domain, test_id):
        task = schemas.load_json(item['task_path'])
        task_errors = schemas.validate_task(task, item['task_path'])
        for error in task_errors:
            if allow_missing_expected and 'expected_file missing:' in error:
                continue
            errors.append({'path': str(item['task_path']), 'error': error})

    return errors


def run_biotaskbench(
    tests_root='tests',
    domain=None,
    test_id=None,
    workspace_root=None,
    output_dir='results',
    model=None,
    skills_path=None,
    agent_cmd=None,
    timeout_seconds=600,
):
    tests = discover_tests(tests_root, domain, test_id)
    results = []

    for item in tests:
        task_path = item['task_path']
        task = schemas.load_json(task_path)

        execution = None
        if workspace_root:
            ws1 = Path(workspace_root) / item['test_id']
            ws2 = Path(workspace_root) / item['domain'] / item['test_id']
            if ws1.exists():
                workspace_dir = ws1
            elif ws2.exists():
                workspace_dir = ws2
            else:
                workspace_dir = task_path.parent
        elif agent_cmd:
            temp_root = Path(output_dir) / '.workspaces'
            temp_root.mkdir(parents=True, exist_ok=True)
            workspace_dir = Path(tempfile.mkdtemp(prefix=f"{item['test_id']}-", dir=temp_root))
            _copy_task_inputs(task, task_path.parent, workspace_dir)
            execution = _run_agent_command(
                agent_cmd=agent_cmd,
                task_path=task_path,
                test_dir=task_path.parent,
                workspace_dir=workspace_dir,
                model=model,
                skills_path=skills_path,
                timeout_seconds=timeout_seconds,
            )
        else:
            workspace_dir = task_path.parent

        test_result = grader.grade_task(task, workspace_dir, task_path.parent)
        test_result['domain'] = item['domain']
        test_result['difficulty'] = task.get('difficulty', 'unknown')
        test_result['task_path'] = str(task_path)
        test_result['workspace_dir'] = str(workspace_dir)
        if execution is not None:
            test_result['agent_execution'] = execution
        results.append(test_result)

    aggregate = reporter.aggregate_results(results)
    timestamp = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M%S')
    run_dir = Path(output_dir) / f'run-{timestamp}'

    payload = {
        'suite': 'biotaskbench',
        'created_at_utc': timestamp,
        'model': model,
        'skills_path': skills_path,
        'tests_root': str(tests_root),
        'domain': domain,
        'test_id': test_id,
        'agent_cmd': agent_cmd,
        'timeout_seconds': timeout_seconds,
        'results': results,
        'aggregate': aggregate,
    }

    run_json = reporter.write_run_output(run_dir, payload)
    return {'run_dir': str(run_dir), 'run_json': str(run_json), 'payload': payload}


def run_external_suite(suite, output_dir='results', model=None, skills_path=None):
    adapters = {
        'bioagent-bench': BioAgentBenchAdapter,
        'biocoder': BioCoderAdapter,
        'bixbench': BixBenchAdapter,
    }
    adapter_cls = adapters[suite]
    adapter = adapter_cls()
    timestamp = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M%S')
    run_dir = Path(output_dir) / f'{suite}-run-{timestamp}'

    try:
        setup_info = adapter.setup()
        tests = adapter.list_tests()
        execution = adapter.run_all(model=model, skills_path=skills_path) if hasattr(adapter, 'run_all') else {'executed': False}
        execution_failed = bool(execution.get('executed') and execution.get('returncode', 0) != 0)
        results = adapter.load_run_results() if hasattr(adapter, 'load_run_results') else []
        if execution_failed:
            aggregate = {
                'tests_total': len(tests),
                'tests_attempted': 0,
                'coverage': 0.0,
                'score': 0.0,
                'score_overall': 0.0,
                'domains': {},
            }
            status = 'error'
            message = 'adapter execution command failed'
        elif results:
            aggregate = reporter.aggregate_results(results)
            status = 'ok'
            message = 'loaded external results via adapter results JSON'
        else:
            aggregate = {
                'tests_total': len(tests),
                'tests_attempted': 0,
                'coverage': 0.0,
                'score': 0.0,
                'score_overall': 0.0,
                'domains': {},
            }
            status = 'scaffold_ready'
            message = 'adapter setup/listing works; execution/grading still pending'
        payload = {
            'suite': suite,
            'created_at_utc': timestamp,
            'model': model,
            'skills_path': skills_path,
            'status': status,
            'message': message,
            'adapter_setup': setup_info,
            'adapter_execution': execution,
            'results': results,
            'aggregate': aggregate,
        }
    except Exception as e:
        payload = {
            'suite': suite,
            'created_at_utc': timestamp,
            'model': model,
            'skills_path': skills_path,
            'status': 'error',
            'message': str(e),
            'results': [],
            'aggregate': {
                'tests_total': 0,
                'tests_attempted': 0,
                'coverage': 0.0,
                'score': 0.0,
                'score_overall': 0.0,
                'domains': {},
            },
        }

    run_json = reporter.write_run_output(run_dir, payload)
    return {'run_dir': str(run_dir), 'run_json': str(run_json), 'payload': payload}


def external_adapter_statuses():
    adapters = {
        'bioagent-bench': BioAgentBenchAdapter(),
        'biocoder': BioCoderAdapter(),
        'bixbench': BixBenchAdapter(),
    }
    statuses = {}
    for name, adapter in adapters.items():
        setup = adapter.setup()
        tests = adapter.list_tests()
        results = adapter.load_run_results() if hasattr(adapter, 'load_run_results') else []
        statuses[name] = {
            'setup': setup,
            'tests_listed': len(tests),
            'results_loaded': len(results),
            'has_run_command': bool(getattr(adapter, 'run_command', None)),
        }
    return statuses


def run_suite(
    suite='biotaskbench',
    tests_root='tests',
    domain=None,
    test_id=None,
    workspace_root=None,
    output_dir='results',
    model=None,
    skills_path=None,
    agent_cmd=None,
    timeout_seconds=600,
):
    if suite == 'biotaskbench':
        return run_biotaskbench(
            tests_root=tests_root,
            domain=domain,
            test_id=test_id,
            workspace_root=workspace_root,
            output_dir=output_dir,
            model=model,
            skills_path=skills_path,
            agent_cmd=agent_cmd,
            timeout_seconds=timeout_seconds,
        )

    if suite in {'bioagent-bench', 'biocoder', 'bixbench'}:
        return run_external_suite(suite=suite, output_dir=output_dir, model=model, skills_path=skills_path)

    if suite == 'all':
        suite_outputs = []
        suite_outputs.append(
            run_biotaskbench(
                tests_root=tests_root,
                domain=domain,
                test_id=test_id,
                workspace_root=workspace_root,
                output_dir=Path(output_dir) / 'biotaskbench',
                model=model,
                skills_path=skills_path,
                agent_cmd=agent_cmd,
                timeout_seconds=timeout_seconds,
            )['payload']
        )
        for s in ['bioagent-bench', 'biocoder', 'bixbench']:
            suite_outputs.append(run_external_suite(s, Path(output_dir) / s, model=model, skills_path=skills_path)['payload'])

        timestamp = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M%S')
        run_dir = Path(output_dir) / f'run-all-{timestamp}'
        payload = {
            'suite': 'all',
            'created_at_utc': timestamp,
            'model': model,
            'skills_path': skills_path,
            'runs': suite_outputs,
            'aggregate': reporter.aggregate_suite_runs(suite_outputs),
        }
        run_json = reporter.write_run_output(run_dir, payload)
        return {'run_dir': str(run_dir), 'run_json': str(run_json), 'payload': payload}

    raise ValueError(f'unknown suite: {suite}')
