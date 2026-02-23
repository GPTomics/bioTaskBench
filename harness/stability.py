import statistics
from pathlib import Path

from harness import reporter


def analyze_flakiness(run_paths, threshold=0.3):
    runs = [reporter.load_run(Path(p)) for p in run_paths]
    per_test = {}

    expanded_runs = []
    for run in runs:
        if run.get('suite') == 'all' and isinstance(run.get('runs'), list):
            expanded_runs.extend(r for r in run['runs'] if isinstance(r, dict))
        else:
            expanded_runs.append(run)

    for run in expanded_runs:
        for result in run.get('results', []):
            key = result.get('test_id')
            if not key:
                continue
            rec = per_test.setdefault(key, {'scores': [], 'attempted': [], 'domain': result.get('domain')})
            rec['scores'].append(float(result.get('score', 0.0)))
            rec['attempted'].append(bool(result.get('attempted')))

    analyses = []
    for test_id, rec in sorted(per_test.items()):
        scores = rec['scores']
        if not scores:
            continue
        spread = max(scores) - min(scores)
        analyses.append(
            {
                'test_id': test_id,
                'domain': rec.get('domain'),
                'runs_seen': len(scores),
                'score_mean': statistics.fmean(scores),
                'score_stdev': statistics.pstdev(scores) if len(scores) > 1 else 0.0,
                'score_min': min(scores),
                'score_max': max(scores),
                'score_spread': spread,
                'attempt_rate': sum(1 for a in rec['attempted'] if a) / len(rec['attempted']),
                'is_flaky': spread > float(threshold),
            }
        )

    flaky = [a for a in analyses if a['is_flaky']]
    return {
        'runs_compared': len(runs),
        'suite_runs_analyzed': len(expanded_runs),
        'threshold': float(threshold),
        'tests_analyzed': len(analyses),
        'flaky_tests': flaky,
        'flaky_count': len(flaky),
        'per_test': analyses,
    }
