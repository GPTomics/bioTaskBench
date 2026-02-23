import argparse
import json
from pathlib import Path

from harness import data_manager, reporter, runner, stability


def cmd_validate(args):
    errors = runner.validate_tests(args.tests_root, args.domain, args.test_id, args.allow_missing_expected)
    if not errors:
        print('Validation passed: no errors found')
        return 0

    print(f'Validation failed: {len(errors)} issue(s)')
    for item in errors:
        print(f"- {item['path']}: {item['error']}")
    return 1


def cmd_run(args):
    out = runner.run_suite(
        suite=args.suite,
        tests_root=args.tests_root,
        domain=args.domain,
        test_id=args.test_id,
        workspace_root=args.workspace_root,
        output_dir=args.output,
        model=args.model,
        skills_path=args.skills_path,
        agent_cmd=args.agent_cmd,
        timeout_seconds=args.timeout_seconds,
    )

    print(reporter.format_summary(out['payload']))
    print(f"run_json: {out['run_json']}")
    return 0


def cmd_compare(args):
    try:
        delta = reporter.compare_runs(args.run_a, args.run_b)
        print(json.dumps(delta, indent=2))
        return 0
    except Exception as e:
        print(f'compare_failed: {e}')
        return 2


def cmd_report(args):
    run_paths = [Path(p) for p in args.runs]
    try:
        runs = [reporter.load_run(p) for p in run_paths]
    except Exception as e:
        print(f'report_failed: {e}')
        return 2

    payload = {'runs': runs}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.suffix.lower() in {'.json', ''}:
        if output.suffix == '':
            output = output.with_suffix('.json')
        output.write_text(json.dumps(payload, indent=2))
    else:
        lines = ['# BioTaskBench Report', '']
        for i, run in enumerate(runs, 1):
            agg = run.get('aggregate', {})
            lines.append(f'## Run {i}')
            lines.append(f"- coverage: {agg.get('coverage', 0.0):.3f}")
            lines.append(f"- completion_rate: {agg.get('completion_rate', 0.0):.3f}")
            lines.append(f"- score: {agg.get('score', 0.0):.3f}")
            lines.append(f"- score_overall: {agg.get('score_overall', 0.0):.3f}")
            domains = agg.get('domains', {})
            if domains:
                lines.append('- domains:')
                for domain in sorted(domains):
                    d = domains[domain]
                    lines.append(
                        f"  - {domain}: coverage={d.get('coverage', 0.0):.3f}, "
                        f"score={d.get('score', 0.0):.3f}, score_overall={d.get('score_overall', 0.0):.3f}"
                    )
            lines.append('')

        if len(run_paths) >= 2:
            delta = reporter.compare_runs(run_paths[0], run_paths[1])
            lines.append('## Delta (Run 2 - Run 1)')
            lines.append(f"- coverage_delta: {delta.get('coverage_delta', 0.0):.3f}")
            lines.append(f"- completion_rate_delta: {delta.get('completion_rate_delta', 0.0):.3f}")
            lines.append(f"- score_delta: {delta.get('score_delta', 0.0):.3f}")
            lines.append(f"- score_overall_delta: {delta.get('score_overall_delta', 0.0):.3f}")
            domain_deltas = delta.get('domains', {})
            if domain_deltas:
                lines.append('- domains:')
                for domain in sorted(domain_deltas):
                    d = domain_deltas[domain]
                    lines.append(
                        f"  - {domain}: coverage_delta={d.get('coverage_delta', 0.0):.3f}, "
                        f"completion_rate_delta={d.get('completion_rate_delta', 0.0):.3f}, "
                        f"score_delta={d.get('score_delta', 0.0):.3f}, "
                        f"score_overall_delta={d.get('score_overall_delta', 0.0):.3f}"
                    )
            diff_deltas = delta.get('difficulty', {})
            if diff_deltas:
                lines.append('- difficulty:')
                for level in sorted(diff_deltas):
                    d = diff_deltas[level]
                    lines.append(
                        f"  - {level}: score_overall_delta={d.get('score_overall_delta', 0.0):.3f}, "
                        f"tests_total_delta={d.get('tests_total_delta', 0)}"
                    )
            lines.append('')
        output.write_text('\n'.join(lines) + '\n')

    print(f'report_written: {output}')
    return 0


def cmd_audit_data(args):
    report = data_manager.audit_data_sizes(args.tests_root, args.max_test_mb, args.max_total_mb)
    print(json.dumps(report, indent=2))
    has_issues = bool(report.get('total_size_violation') or report.get('per_test_size_violations') or report.get('tests_with_missing_data_files'))
    return 1 if has_issues else 0


def cmd_audit_flaky(args):
    report = stability.analyze_flakiness(args.runs, args.threshold)
    print(json.dumps(report, indent=2))
    return 0


def cmd_adapter_status(_args):
    print(json.dumps(runner.external_adapter_statuses(), indent=2))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog='benchmarkAgentBfx')
    sub = parser.add_subparsers(dest='command', required=True)

    run_p = sub.add_parser('run')
    run_p.add_argument('--suite', default='biotaskbench', choices=['biotaskbench', 'bioagent-bench', 'biocoder', 'bixbench', 'all'])
    run_p.add_argument('--model')
    run_p.add_argument('--skills-path')
    run_p.add_argument('--tests-root', default='tests')
    run_p.add_argument('--domain')
    run_p.add_argument('--test-id')
    run_p.add_argument('--workspace-root')
    run_p.add_argument('--agent-cmd')
    run_p.add_argument('--timeout-seconds', type=int, default=600)
    run_p.add_argument('--output', default='results')
    run_p.set_defaults(func=cmd_run)

    val_p = sub.add_parser('validate')
    val_p.add_argument('--tests-root', default='tests')
    val_p.add_argument('--domain')
    val_p.add_argument('--test-id')
    val_p.add_argument('--allow-missing-expected', action='store_true')
    val_p.set_defaults(func=cmd_validate)

    cmp_p = sub.add_parser('compare')
    cmp_p.add_argument('run_a')
    cmp_p.add_argument('run_b')
    cmp_p.set_defaults(func=cmd_compare)

    rep_p = sub.add_parser('report')
    rep_p.add_argument('runs', nargs='+')
    rep_p.add_argument('--output', required=True)
    rep_p.set_defaults(func=cmd_report)

    data_p = sub.add_parser('audit-data')
    data_p.add_argument('--tests-root', default='tests')
    data_p.add_argument('--max-test-mb', type=float, default=10.0)
    data_p.add_argument('--max-total-mb', type=float, default=500.0)
    data_p.set_defaults(func=cmd_audit_data)

    flaky_p = sub.add_parser('audit-flaky')
    flaky_p.add_argument('runs', nargs='+')
    flaky_p.add_argument('--threshold', type=float, default=0.3)
    flaky_p.set_defaults(func=cmd_audit_flaky)

    status_p = sub.add_parser('adapter-status')
    status_p.set_defaults(func=cmd_adapter_status)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
