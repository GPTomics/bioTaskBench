import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


SKILL_PATH_RE = re.compile(r'\.agents/skills/(bio-[a-zA-Z0-9_-]+)/SKILL\.md')


def extract_skills_from_claude_session(jsonl_path):
    '''Extract skill names from a Claude Code session (Skill tool calls).'''
    skills = []
    for line in jsonl_path.open():
        try:
            entry = json.loads(line)
            content = entry.get('message', {}).get('content', [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get('name') == 'Skill':
                    skills.append(block['input']['skill'])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return skills


def extract_skills_from_codex_session(jsonl_path):
    '''Extract skill names from a Codex session (reads of .agents/skills/*/SKILL.md).'''
    skills = set()
    for line in jsonl_path.open():
        try:
            obj = json.loads(line)
            p = obj.get('payload', {})
            if obj.get('type') != 'response_item' or p.get('type') != 'function_call' or p.get('name') != 'exec_command':
                continue
            args = json.loads(p.get('arguments', '{}'))
            cmd = args.get('cmd', '')
            for m in SKILL_PATH_RE.finditer(cmd):
                skills.add(m.group(1))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return sorted(skills)


def get_codex_session_cwd(jsonl_path):
    '''Extract the cwd from a Codex session's turn_context event.'''
    for line in jsonl_path.open():
        try:
            obj = json.loads(line)
            if obj.get('type') == 'turn_context':
                return obj['payload'].get('cwd', '')
        except (json.JSONDecodeError, KeyError):
            continue
    return ''


def is_codex_preflight(jsonl_path):
    '''Check if a Codex session is a preflight (skill review) session.'''
    for line in jsonl_path.open():
        try:
            obj = json.loads(line)
            p = obj.get('payload', {})
            if obj.get('type') == 'response_item' and p.get('type') == 'message' and p.get('role') == 'user':
                for c in (p.get('content') or []):
                    if isinstance(c, dict) and 'Review the skills' in c.get('text', ''):
                        return True
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return False


def discover_test_ids(tests_root='tests'):
    ids = set()
    for task_json in Path(tests_root).glob('*/*/task.json'):
        ids.add(task_json.parent.name)
    return ids


def match_test_id(raw_suffix, known_ids):
    for tid in sorted(known_ids, key=len, reverse=True):
        if raw_suffix.startswith(tid + '-') or raw_suffix == tid:
            return tid
    return raw_suffix


def extract_skill_usage_claude(projects_dir, run_label, tests_root='tests'):
    '''Extract skill usage from Claude Code sessions (original approach).'''
    projects_dir = Path(projects_dir)
    known_ids = discover_test_ids(tests_root)
    results = defaultdict(lambda: {'skills': [], 'session_count': 0})
    for pdir in sorted(projects_dir.glob(f'*{run_label}*')):
        if 'workspaces-' not in pdir.name:
            continue
        raw_suffix = pdir.name.split('workspaces-')[1]
        test_id = match_test_id(raw_suffix, known_ids)
        for jsonl in pdir.glob('*.jsonl'):
            skills = extract_skills_from_claude_session(jsonl)
            results[test_id]['session_count'] += 1
            results[test_id]['skills'].extend(skills)
    return dict(results)


def extract_skill_usage_codex(results_dir, sessions_dir=None, tests_root='tests'):
    '''Extract skill usage from Codex sessions by matching workspace cwds.'''
    results_dir = Path(results_dir)
    if sessions_dir is None:
        sessions_dir = Path.home() / '.codex' / 'sessions'
    else:
        sessions_dir = Path(sessions_dir)
    known_ids = discover_test_ids(tests_root)

    workspaces = {}
    ws_dir = results_dir / '.workspaces'
    if not ws_dir.exists():
        return {}
    for ws in sorted(ws_dir.iterdir()):
        if ws.is_dir():
            raw = ws.name
            test_id = match_test_id(raw, known_ids)
            workspaces[str(ws.resolve())] = test_id

    session_index = defaultdict(list)
    for jsonl in sessions_dir.rglob('rollout-*.jsonl'):
        cwd = get_codex_session_cwd(jsonl)
        if cwd:
            resolved = str(Path(cwd).resolve())
            if resolved in workspaces:
                session_index[workspaces[resolved]].append(jsonl)

    results = {}
    for test_id in sorted(session_index):
        all_skills = set()
        main_sessions = 0
        for jsonl in session_index[test_id]:
            if is_codex_preflight(jsonl):
                continue
            all_skills.update(extract_skills_from_codex_session(jsonl))
            main_sessions += 1
        results[test_id] = {
            'skills': sorted(all_skills),
            'session_count': main_sessions,
        }
    return results


def print_results(usage):
    rows = []
    for test_id in sorted(usage):
        unique_skills = sorted(set(usage[test_id]['skills']))
        rows.append({
            'test_id': test_id,
            'skills_used': ', '.join(unique_skills) if unique_skills else 'none',
            'skill_count': len(unique_skills),
            'sessions': usage[test_id]['session_count'],
        })
    return rows


def main():
    if len(sys.argv) < 3:
        print('Usage: python extract_skill_usage.py <agent> <path> [--csv output.csv]')
        print('  agent: "claude" or "codex"')
        print('  path:  for claude: run_label substring to match project dirs')
        print('         for codex: results directory (e.g., ~/code/biotesting/codex_w_skills/results)')
        sys.exit(1)

    agent = sys.argv[1]
    path_arg = sys.argv[2]
    csv_path = None
    if '--csv' in sys.argv:
        csv_path = sys.argv[sys.argv.index('--csv') + 1]

    if agent == 'claude':
        projects_dir = Path.home() / '.claude' / 'projects'
        usage = extract_skill_usage_claude(projects_dir, path_arg)
    elif agent == 'codex':
        usage = extract_skill_usage_codex(path_arg)
    else:
        print(f'Unknown agent: {agent}. Use "claude" or "codex".')
        sys.exit(1)

    if not usage:
        print(f'No sessions found for {agent} at "{path_arg}"')
        sys.exit(1)

    rows = print_results(usage)

    if csv_path:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['test_id', 'skills_used', 'skill_count', 'sessions'])
            writer.writeheader()
            writer.writerows(rows)
        print(f'Wrote {len(rows)} rows to {csv_path}')
    else:
        total_with_skills = sum(1 for r in rows if r['skills_used'] != 'none')
        print(f'{"test_id":<30} {"sessions":>8}  {"skills_used"}')
        print('-' * 90)
        for r in rows:
            print(f'{r["test_id"]:<30} {r["sessions"]:>8}  {r["skills_used"]}')
        print(f'\n{total_with_skills}/{len(rows)} tests used skills')


if __name__ == '__main__':
    main()
