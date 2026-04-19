import json
import os
import subprocess
import sys
from pathlib import Path


SKILLS_REMINDER = '## Use Skills\n\nREMINDER: You have many bioinformatics skills installed to help with reviewing files and executing commands. For every task, first check if a relevant skill exists and load it as a tool before proceeding. Use skills as much as possible -- they contain curated code patterns and domain knowledge that produce better results than working from scratch.'

TOOLS_REMINDER = '## Tools\n\nRun all Python and R commands in the `bio_eval` conda environment. Maximize use of locally installed tools (CLI utilities in the conda env or system, e.g., samtools, bedtools, bcftools) before reimplementing functionality or installing new packages.'


def generate_claude_md(task, use_skills=False):
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
        sections.append(SKILLS_REMINDER)
    sections.append(TOOLS_REMINDER)
    return '\n\n'.join(sections) + '\n'


def build_claude_command(model=None, max_turns=200, json_output=False, use_skills=False, effort=None):
    if use_skills:
        prompt = 'Complete the bioinformatics analysis task. First check if any relevant skills exists and load them as a tool. Then complete the analysis task.'
    else:
        prompt = 'Complete the bioinformatics analysis task'
    parts = ['claude', '-p', f'"{prompt}"', '--dangerously-skip-permissions']
    if model:
        parts.extend(['--model', model])
    parts.extend(['--max-turns', str(max_turns)])
    if json_output:
        parts.extend(['--output-format', 'json'])
    if effort:
        parts.extend(['--effort', effort])
    return ' '.join(parts)


def build_preflight_command(model=None):
    parts = ['claude', '-p', '"Review the skills you have access to and update CLAUDE.md with the skills that are most relevant to this task if there are any."', '--dangerously-skip-permissions', '--max-turns', '3']
    if model:
        parts.extend(['--model', model])
    return ' '.join(parts)


def extract_skill_usage(json_output):
    '''Extract skill names from claude --output-format json stdout.'''
    if not json_output:
        return []
    for line in json_output.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            tools = data.get('tools', [])
            return [t for t in tools if t.startswith('bio-')]
        except (json.JSONDecodeError, AttributeError):
            continue
    return []


def main():
    task_path = os.environ['BIOTASKBENCH_TASK_JSON']
    with open(task_path) as f:
        task = json.load(f)
    use_skills = bool(os.environ.get('BENCHMARK_SKILLS_PATH'))
    model = os.environ.get('BENCHMARK_MODEL')
    effort = os.environ.get('BENCHMARK_EFFORT')
    Path('CLAUDE.md').write_text(generate_claude_md(task, use_skills=use_skills))
    if use_skills:
        subprocess.run(build_preflight_command(model), shell=True)
    cmd = build_claude_command(model, use_skills=use_skills, json_output=use_skills, effort=effort)
    result = subprocess.run(cmd, shell=True, capture_output=use_skills, text=use_skills)
    if use_skills and result.stdout:
        skills_used = extract_skill_usage(result.stdout)
        if skills_used:
            print(f'  skills_used: {skills_used}', flush=True)
        else:
            print('  skills_used: none detected', flush=True)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
