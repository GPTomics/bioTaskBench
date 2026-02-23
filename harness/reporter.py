import json
from pathlib import Path


def aggregate_results(test_results):
    total = len(test_results)
    attempted = sum(1 for r in test_results if r.get('attempted'))
    completed = sum(1 for r in test_results if float(r.get('score', 0.0)) > 0.0)

    if attempted:
        score_attempted = sum(r.get('score', 0.0) for r in test_results if r.get('attempted')) / attempted
    else:
        score_attempted = 0.0

    score_overall = sum(r.get('score', 0.0) for r in test_results) / total if total else 0.0

    by_domain = {}
    by_difficulty = {}
    for r in test_results:
        domain = r.get('domain', 'unknown')
        bucket = by_domain.setdefault(domain, {'total': 0, 'attempted': 0, 'scores_all': [], 'scores_attempted': []})
        bucket['total'] += 1
        score = r.get('score', 0.0)
        bucket['scores_all'].append(score)
        if r.get('attempted'):
            bucket['attempted'] += 1
            bucket['scores_attempted'].append(score)

        difficulty = r.get('difficulty', 'unknown')
        db = by_difficulty.setdefault(difficulty, {'total': 0, 'scores_all': []})
        db['total'] += 1
        db['scores_all'].append(score)

    domain_summary = {}
    for domain, bucket in by_domain.items():
        total_d = bucket['total']
        attempted_d = bucket['attempted']
        completed_d = sum(1 for s in bucket['scores_all'] if float(s) > 0.0)
        domain_summary[domain] = {
            'tests_total': total_d,
            'tests_attempted': attempted_d,
            'coverage': attempted_d / total_d if total_d else 0.0,
            'completion_rate': completed_d / total_d if total_d else 0.0,
            'score': (sum(bucket['scores_attempted']) / attempted_d) if attempted_d else 0.0,
            'score_overall': (sum(bucket['scores_all']) / total_d) if total_d else 0.0,
        }

    difficulty_summary = {}
    for difficulty, bucket in by_difficulty.items():
        total_x = bucket['total']
        difficulty_summary[difficulty] = {
            'tests_total': total_x,
            'score_overall': (sum(bucket['scores_all']) / total_x) if total_x else 0.0,
        }

    return {
        'tests_total': total,
        'tests_attempted': attempted,
        'coverage': attempted / total if total else 0.0,
        'completion_rate': completed / total if total else 0.0,
        'score': score_attempted,
        'score_overall': score_overall,
        'domains': domain_summary,
        'difficulty': difficulty_summary,
    }


def aggregate_suite_runs(run_payloads):
    by_suite = {}
    tests_total = 0
    tests_attempted = 0
    weighted_score_sum = 0.0
    weighted_score_overall_sum = 0.0
    counted_suites = 0
    mean_suite_scores = []

    for run in run_payloads:
        suite = run.get('suite', 'unknown')
        agg = run.get('aggregate', {})
        total = int(agg.get('tests_total', 0))
        attempted = int(agg.get('tests_attempted', 0))
        score = float(agg.get('score', 0.0))
        score_overall = float(agg.get('score_overall', 0.0))

        by_suite[suite] = {
            'tests_total': total,
            'tests_attempted': attempted,
            'coverage': float(agg.get('coverage', 0.0)),
            'score': score,
            'score_overall': score_overall,
            'status': run.get('status', 'ok'),
        }

        tests_total += total
        tests_attempted += attempted
        weighted_score_sum += score * total
        weighted_score_overall_sum += score_overall * total
        if total > 0:
            counted_suites += 1
            mean_suite_scores.append(score_overall)

    return {
        'suites_total': len(by_suite),
        'tests_total': tests_total,
        'tests_attempted': tests_attempted,
        'coverage': (tests_attempted / tests_total) if tests_total else 0.0,
        'score_weighted': (weighted_score_sum / tests_total) if tests_total else 0.0,
        'score_overall_weighted': (weighted_score_overall_sum / tests_total) if tests_total else 0.0,
        'score_overall_suite_mean': (sum(mean_suite_scores) / counted_suites) if counted_suites else 0.0,
        'suites': by_suite,
    }


def write_run_output(output_dir, run_payload):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_json = output_dir / 'run.json'
    with run_json.open('w') as f:
        json.dump(run_payload, f, indent=2)

    summary_txt = output_dir / 'summary.txt'
    summary_txt.write_text(format_summary(run_payload))

    return run_json


def format_summary(run_payload):
    aggregate = run_payload.get('aggregate', {})
    lines = []
    if 'suites' in aggregate:
        lines.append('Benchmark Run Summary')
        lines.append(f"suites_total: {aggregate.get('suites_total', 0)}")
        lines.append(f"tests_total: {aggregate.get('tests_total', 0)}")
        lines.append(f"tests_attempted: {aggregate.get('tests_attempted', 0)}")
        lines.append(f"coverage: {aggregate.get('coverage', 0.0):.3f}")
        lines.append(f"score_weighted: {aggregate.get('score_weighted', 0.0):.3f}")
        lines.append(f"score_overall_weighted: {aggregate.get('score_overall_weighted', 0.0):.3f}")
        lines.append(f"score_overall_suite_mean: {aggregate.get('score_overall_suite_mean', 0.0):.3f}")
        suites = aggregate.get('suites', {})
        if suites:
            lines.append('suites:')
            for suite in sorted(suites):
                s = suites[suite]
                lines.append(
                    f"  - {suite}: status={s.get('status', 'ok')}, coverage={s.get('coverage', 0.0):.3f}, "
                    f"score={s.get('score', 0.0):.3f}, score_overall={s.get('score_overall', 0.0):.3f}, "
                    f"attempted={s.get('tests_attempted', 0)}/{s.get('tests_total', 0)}"
                )
        return '\n'.join(lines) + '\n'

    suite_name = run_payload.get('suite', 'biotaskbench')
    if suite_name == 'biotaskbench':
        lines.append('BioTaskBench Run Summary')
    else:
        lines.append(f'{suite_name} Run Summary')
    lines.append(f"tests_total: {aggregate.get('tests_total', 0)}")
    lines.append(f"tests_attempted: {aggregate.get('tests_attempted', 0)}")
    lines.append(f"coverage: {aggregate.get('coverage', 0.0):.3f}")
    lines.append(f"completion_rate: {aggregate.get('completion_rate', 0.0):.3f}")
    lines.append(f"score: {aggregate.get('score', 0.0):.3f}")
    lines.append(f"score_overall: {aggregate.get('score_overall', 0.0):.3f}")

    domains = aggregate.get('domains', {})
    if domains:
        lines.append('domains:')
        for domain in sorted(domains):
            d = domains[domain]
            lines.append(
                f"  - {domain}: coverage={d['coverage']:.3f}, score={d['score']:.3f}, "
                f"score_overall={d['score_overall']:.3f}, completion_rate={d.get('completion_rate', 0.0):.3f}, "
                f"attempted={d['tests_attempted']}/{d['tests_total']}"
            )

    difficulties = aggregate.get('difficulty', {})
    if difficulties:
        lines.append('difficulty:')
        for difficulty in sorted(difficulties):
            d = difficulties[difficulty]
            lines.append(f"  - {difficulty}: score_overall={d.get('score_overall', 0.0):.3f}, tests={d.get('tests_total', 0)}")

    return '\n'.join(lines) + '\n'


def load_run(path):
    path = Path(path)
    if path.is_dir():
        direct = path / 'run.json'
        if direct.exists():
            path = direct
        else:
            nested = sorted(path.glob('run-*/run.json'))
            if nested:
                path = nested[-1]
            else:
                raise FileNotFoundError(f'no run.json found under directory: {path}')
    with path.open() as f:
        return json.load(f)


def compare_runs(path_a, path_b):
    a = load_run(path_a)
    b = load_run(path_b)

    agg_a = a.get('aggregate', {})
    agg_b = b.get('aggregate', {})

    domain_deltas = {}
    domains = set(agg_a.get('domains', {})) | set(agg_b.get('domains', {}))
    for domain in sorted(domains):
        a_d = agg_a.get('domains', {}).get(domain, {})
        b_d = agg_b.get('domains', {}).get(domain, {})
        domain_deltas[domain] = {
            'coverage_delta': float(b_d.get('coverage', 0.0)) - float(a_d.get('coverage', 0.0)),
            'completion_rate_delta': float(b_d.get('completion_rate', 0.0)) - float(a_d.get('completion_rate', 0.0)),
            'score_delta': float(b_d.get('score', 0.0)) - float(a_d.get('score', 0.0)),
            'score_overall_delta': float(b_d.get('score_overall', 0.0)) - float(a_d.get('score_overall', 0.0)),
        }

    difficulty_deltas = {}
    levels = set(agg_a.get('difficulty', {})) | set(agg_b.get('difficulty', {}))
    for level in sorted(levels):
        a_x = agg_a.get('difficulty', {}).get(level, {})
        b_x = agg_b.get('difficulty', {}).get(level, {})
        difficulty_deltas[level] = {
            'score_overall_delta': float(b_x.get('score_overall', 0.0)) - float(a_x.get('score_overall', 0.0)),
            'tests_total_delta': int(b_x.get('tests_total', 0)) - int(a_x.get('tests_total', 0)),
        }

    return {
        'run_a': str(path_a),
        'run_b': str(path_b),
        'coverage_delta': float(agg_b.get('coverage', 0.0)) - float(agg_a.get('coverage', 0.0)),
        'completion_rate_delta': float(agg_b.get('completion_rate', 0.0)) - float(agg_a.get('completion_rate', 0.0)),
        'score_delta': float(agg_b.get('score', 0.0)) - float(agg_a.get('score', 0.0)),
        'score_overall_delta': float(agg_b.get('score_overall', 0.0)) - float(agg_a.get('score_overall', 0.0)),
        'domains': domain_deltas,
        'difficulty': difficulty_deltas,
    }
