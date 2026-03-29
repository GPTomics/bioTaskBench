import glob
import json
import os
import subprocess
import sys
from pathlib import Path


CODEX_SKILLS_REMINDER = '## Use Skills\n\nREMINDER: You have bioinformatics skills available in .agents/skills/. For every task, first check if a relevant skill exists by reading its SKILL.md and following its instructions before proceeding. Use skills as much as possible -- they contain curated code patterns and domain knowledge that produce better results than working from scratch.'

TOOLS_REMINDER = '## Tools\n\nRun all Python and R commands in the `bio_eval` conda environment. Maximize use of locally installed tools (CLI utilities in the conda env or system, e.g., samtools, bedtools, bcftools) before reimplementing functionality or installing new packages.'


def generate_agents_md(task, use_skills=False):
    sections = [f"# Task: {task['test_id']}\n\n{task['prompt']}"]
    ctx = task.get('context', {})
    if ctx.get('data_description'):
        sections.append(f"## Available Data\n\n{ctx['data_description']}")
    data_files = ctx.get('data_files', [])
    if data_files:
        file_list = '\n'.join(f'- `{f}`' for f in data_files)
        sections.append(f"The following files are in your working directory:\n{file_list}")
    if ctx.get('setup_notes'):
        sections.append(f"## Setup Notes\n\n{ctx['setup_notes']}")
    if use_skills:
        sections.append(CODEX_SKILLS_REMINDER)
    sections.append(TOOLS_REMINDER)
    return '\n\n'.join(sections) + '\n'


def build_preflight_command(model=None):
    parts = ['codex', 'exec', '"Review the skills in .agents/skills/ and update AGENTS.md with the skills that are most relevant to this task if there are any."', '--dangerously-bypass-approvals-and-sandbox', '--skip-git-repo-check']
    if model:
        parts.extend(['--model', model])
    return ' '.join(parts)


def build_codex_command(model=None, use_skills=False, effort=None):
    if use_skills:
        prompt = 'Complete the bioinformatics analysis task. First check .agents/skills/ for relevant skill instructions and follow them. Then complete the analysis task.'
    else:
        prompt = 'Complete the bioinformatics analysis task'
    parts = ['codex', 'exec', f'"{prompt}"', '--dangerously-bypass-approvals-and-sandbox', '--skip-git-repo-check']
    if model:
        parts.extend(['--model', model])
    if effort:
        parts.extend(['-c', f'model_reasoning_effort={effort}'])
    return ' '.join(parts)


def check_codex_session_tokens(workspace_dir):
    '''Find the most recent Codex session for this workspace and check for zero-token output.
    Returns True if the session produced output, False if rate-limited/empty.'''
    sessions_dir = Path.home() / '.codex' / 'sessions'
    cwd_resolved = str(Path(workspace_dir).resolve())
    candidates = sorted(sessions_dir.rglob('rollout-*.jsonl'), key=lambda p: p.name, reverse=True)
    for session_path in candidates[:50]:
        for line in session_path.open():
            try:
                obj = json.loads(line)
                if obj.get('type') == 'turn_context':
                    if str(Path(obj['payload'].get('cwd', '')).resolve()) == cwd_resolved:
                        for sline in session_path.open():
                            sobj = json.loads(sline)
                            sp = sobj.get('payload', {})
                            if sp.get('type') == 'token_count':
                                total = ((sp.get('info') or {}).get('total_token_usage') or {})
                                if total.get('output_tokens', 0) > 0:
                                    return True
                                print('WARNING: Codex session produced zero output tokens (likely rate-limited)', flush=True)
                                return False
                    break
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return True


def setup_codex_skills(skills_path, workspace_dir):
    if not skills_path:
        return
    agents_dir = Path(workspace_dir) / '.agents'
    agents_dir.mkdir(parents=True, exist_ok=True)
    link = agents_dir / 'skills'
    os.symlink(os.path.abspath(skills_path), str(link))


def main():
    task_path = os.environ['BIOTASKBENCH_TASK_JSON']
    with open(task_path) as f:
        task = json.load(f)
    skills_path = os.environ.get('BENCHMARK_SKILLS_PATH')
    use_skills = bool(skills_path)
    model = os.environ.get('BENCHMARK_MODEL')
    effort = os.environ.get('BENCHMARK_EFFORT')
    Path('AGENTS.md').write_text(generate_agents_md(task, use_skills=use_skills))
    if use_skills:
        setup_codex_skills(skills_path, '.')
        subprocess.run(build_preflight_command(model), shell=True)
    cmd = build_codex_command(model, use_skills=use_skills, effort=effort)
    result = subprocess.run(cmd, shell=True)
    if result.returncode == 0 and not check_codex_session_tokens('.'):
        sys.exit(1)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
