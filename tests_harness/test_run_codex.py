import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.run_codex import build_codex_command, build_preflight_command, check_codex_session_tokens, generate_agents_md, setup_codex_skills
from scripts.extract_skill_usage import extract_skills_from_codex_session


class GenerateAgentsMdTests(unittest.TestCase):
    def _make_task(self):
        return {
            'test_id': 'test-001',
            'prompt': 'Compute stats from input.tsv, write output.tsv',
            'context': {
                'data_files': ['input.tsv'],
                'data_description': 'Synthetic test data',
                'setup_notes': 'Python and R available',
            },
        }

    def test_generate_agents_md_basic(self):
        task = self._make_task()
        result = generate_agents_md(task)
        self.assertEqual(result.count('# Task: test-001'), 1)
        self.assertIn('Compute stats from input.tsv', result)
        self.assertIn('input.tsv', result)
        self.assertIn('Synthetic test data', result)
        self.assertIn('Python and R available', result)

    def test_generate_agents_md_multiple_data_files(self):
        task = self._make_task()
        task['context']['data_files'] = ['reads_1.fq.gz', 'reads_2.fq.gz', 'reference.fa']
        result = generate_agents_md(task)
        self.assertIn('reads_1.fq.gz', result)
        self.assertIn('reads_2.fq.gz', result)
        self.assertIn('reference.fa', result)

    def test_generate_agents_md_no_eval_leakage(self):
        task = self._make_task()
        task['evaluation'] = {'criteria': [{'weight': 0.7, 'range': [1, 10], 'type': 'range_check'}]}
        result = generate_agents_md(task)
        self.assertNotIn('0.7', result)
        self.assertNotIn('range_check', result)
        self.assertNotIn('[1, 10]', result)

    def test_generate_agents_md_with_skills_true(self):
        task = self._make_task()
        result = generate_agents_md(task, use_skills=True)
        self.assertIn('.agents/skills/', result)
        self.assertIn('locally installed tools', result)

    def test_generate_agents_md_with_skills_false(self):
        task = self._make_task()
        result = generate_agents_md(task, use_skills=False)
        self.assertNotIn('.agents/skills/', result)
        self.assertIn('locally installed tools', result)

    def test_generate_agents_md_default_no_skills(self):
        task = self._make_task()
        result = generate_agents_md(task)
        self.assertNotIn('.agents/skills/', result)
        self.assertIn('locally installed tools', result)

    def test_generate_agents_md_missing_optional_fields(self):
        task = {'test_id': 'x', 'prompt': 'Do something', 'context': {'data_files': []}}
        result = generate_agents_md(task)
        self.assertIn('Do something', result)
        self.assertIn('# Task: x', result)
        self.assertNotIn('Available Data', result)
        self.assertNotIn('Setup Notes', result)


class BuildCodexCommandTests(unittest.TestCase):
    def test_build_codex_command_with_model(self):
        cmd = build_codex_command(model='o3')
        self.assertIn('codex', cmd)
        self.assertIn('exec', cmd)
        self.assertIn('--dangerously-bypass-approvals-and-sandbox', cmd)
        self.assertIn('--model', cmd)
        self.assertIn('o3', cmd)
        self.assertIn('--skip-git-repo-check', cmd)

    def test_build_codex_command_no_model(self):
        cmd = build_codex_command(model=None)
        self.assertIn('codex', cmd)
        self.assertIn('exec', cmd)
        self.assertNotIn('--model', cmd)

    def test_build_codex_command_with_skills(self):
        cmd = build_codex_command(model='o3', use_skills=True)
        self.assertIn('.agents/skills/', cmd.lower())
        self.assertIn('Complete the bioinformatics analysis task', cmd)

    def test_build_codex_command_without_skills(self):
        cmd = build_codex_command(model=None, use_skills=False)
        self.assertNotIn('skills', cmd.lower())
        self.assertIn('Complete the bioinformatics analysis task', cmd)

    def test_build_codex_command_no_max_turns(self):
        cmd = build_codex_command(model='o3')
        self.assertNotIn('--max-turns', cmd)

    def test_build_codex_command_no_skip_permissions(self):
        cmd = build_codex_command(model='o3')
        self.assertNotIn('--dangerously-skip-permissions', cmd)
        self.assertIn('--dangerously-bypass-approvals-and-sandbox', cmd)

    def test_build_codex_command_with_effort(self):
        cmd = build_codex_command(model='o3', effort='high')
        self.assertIn('-c model_reasoning_effort=high', cmd)

    def test_build_codex_command_no_effort(self):
        cmd = build_codex_command(model='o3', effort=None)
        self.assertNotIn('model_reasoning_effort', cmd)


class BuildPreflightCommandTests(unittest.TestCase):
    def test_preflight_basic(self):
        cmd = build_preflight_command()
        self.assertIn('codex', cmd)
        self.assertIn('exec', cmd)
        self.assertIn('.agents/skills/', cmd)
        self.assertIn('--dangerously-bypass-approvals-and-sandbox', cmd)
        self.assertNotIn('--model', cmd)

    def test_preflight_with_model(self):
        cmd = build_preflight_command(model='o3')
        self.assertIn('--model', cmd)
        self.assertIn('o3', cmd)


class SetupCodexSkillsTests(unittest.TestCase):
    def test_symlinks_skills_dir(self):
        with tempfile.TemporaryDirectory() as skills_src, tempfile.TemporaryDirectory() as workspace:
            skill_dir = Path(skills_src) / 'bio-chipseq'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text('# ChIP-seq skill')
            setup_codex_skills(skills_src, workspace)
            link = Path(workspace) / '.agents' / 'skills'
            self.assertTrue(link.is_symlink())
            self.assertEqual(str(link.resolve()), str(Path(skills_src).resolve()))
            self.assertTrue((link / 'bio-chipseq' / 'SKILL.md').exists())

    def test_creates_dot_agents_dir(self):
        with tempfile.TemporaryDirectory() as skills_src, tempfile.TemporaryDirectory() as workspace:
            setup_codex_skills(skills_src, workspace)
            self.assertTrue((Path(workspace) / '.agents').is_dir())

    def test_noop_when_no_path(self):
        with tempfile.TemporaryDirectory() as workspace:
            setup_codex_skills(None, workspace)
            self.assertFalse((Path(workspace) / '.agents').exists())

    def test_skills_readable_through_link(self):
        with tempfile.TemporaryDirectory() as skills_src, tempfile.TemporaryDirectory() as workspace:
            skill_dir = Path(skills_src) / 'bio-rnaseq'
            skill_dir.mkdir()
            content = '# RNA-seq normalization\n\nUse DESeq2 median-of-ratios.'
            (skill_dir / 'SKILL.md').write_text(content)
            setup_codex_skills(skills_src, workspace)
            read_content = (Path(workspace) / '.agents' / 'skills' / 'bio-rnaseq' / 'SKILL.md').read_text()
            self.assertEqual(read_content, content)


class CodexMainIntegrationTests(unittest.TestCase):
    def _make_task_file(self, td):
        task = {
            'test_id': 'test-001',
            'prompt': 'Analyze data',
            'context': {'data_files': [], 'data_description': 'Test data'},
        }
        task_path = Path(td) / 'task.json'
        task_path.write_text(json.dumps(task))
        return str(task_path)

    def test_main_writes_agents_md(self):
        with tempfile.TemporaryDirectory() as td:
            task_path = self._make_task_file(td)
            mock_result = MagicMock(returncode=0)
            with patch.dict(os.environ, {'BIOTASKBENCH_TASK_JSON': task_path}, clear=False), \
                 patch('subprocess.run', return_value=mock_result):
                from scripts.run_codex import main
                orig_cwd = os.getcwd()
                os.chdir(td)
                try:
                    with self.assertRaises(SystemExit):
                        main()
                    self.assertTrue((Path(td) / 'AGENTS.md').exists())
                    self.assertFalse((Path(td) / 'CLAUDE.md').exists())
                finally:
                    os.chdir(orig_cwd)

    def test_main_no_preflight_without_skills(self):
        with tempfile.TemporaryDirectory() as td:
            task_path = self._make_task_file(td)
            mock_result = MagicMock(returncode=0)
            with patch.dict(os.environ, {'BIOTASKBENCH_TASK_JSON': task_path}, clear=False), \
                 patch('subprocess.run', return_value=mock_result) as mock_run:
                from scripts.run_codex import main
                orig_cwd = os.getcwd()
                os.chdir(td)
                try:
                    with self.assertRaises(SystemExit):
                        main()
                    self.assertEqual(mock_run.call_count, 1)
                finally:
                    os.chdir(orig_cwd)

    def test_main_preflight_with_skills(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as skills_src:
            task_path = self._make_task_file(td)
            skill_dir = Path(skills_src) / 'bio-test'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text('# Test skill')
            mock_result = MagicMock(returncode=0)
            with patch.dict(os.environ, {'BIOTASKBENCH_TASK_JSON': task_path, 'BENCHMARK_SKILLS_PATH': skills_src}, clear=False), \
                 patch('subprocess.run', return_value=mock_result) as mock_run:
                from scripts.run_codex import main
                orig_cwd = os.getcwd()
                os.chdir(td)
                try:
                    with self.assertRaises(SystemExit):
                        main()
                    self.assertEqual(mock_run.call_count, 2)
                    preflight_cmd = mock_run.call_args_list[0][0][0]
                    self.assertIn('Review the skills', preflight_cmd)
                    self.assertIn('.agents/skills/', preflight_cmd)
                finally:
                    os.chdir(orig_cwd)

    def test_main_with_skills_sets_up_dirs(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as skills_src:
            task_path = self._make_task_file(td)
            skill_dir = Path(skills_src) / 'bio-test'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text('# Test skill')
            mock_result = MagicMock(returncode=0)
            with patch.dict(os.environ, {'BIOTASKBENCH_TASK_JSON': task_path, 'BENCHMARK_SKILLS_PATH': skills_src}, clear=False), \
                 patch('subprocess.run', return_value=mock_result):
                from scripts.run_codex import main
                orig_cwd = os.getcwd()
                os.chdir(td)
                try:
                    with self.assertRaises(SystemExit):
                        main()
                    self.assertTrue((Path(td) / '.agents' / 'skills').is_symlink())
                finally:
                    os.chdir(orig_cwd)

    def test_main_passes_model_from_env(self):
        with tempfile.TemporaryDirectory() as td:
            task_path = self._make_task_file(td)
            mock_result = MagicMock(returncode=0)
            with patch.dict(os.environ, {'BIOTASKBENCH_TASK_JSON': task_path, 'BENCHMARK_MODEL': 'o3'}, clear=False), \
                 patch('subprocess.run', return_value=mock_result) as mock_run:
                from scripts.run_codex import main
                orig_cwd = os.getcwd()
                os.chdir(td)
                try:
                    with self.assertRaises(SystemExit):
                        main()
                    cmd_str = mock_run.call_args[0][0]
                    self.assertIn('--model', cmd_str)
                    self.assertIn('o3', cmd_str)
                finally:
                    os.chdir(orig_cwd)

    def test_main_exits_with_returncode(self):
        with tempfile.TemporaryDirectory() as td:
            task_path = self._make_task_file(td)
            mock_result = MagicMock(returncode=42)
            with patch.dict(os.environ, {'BIOTASKBENCH_TASK_JSON': task_path}, clear=False), \
                 patch('subprocess.run', return_value=mock_result):
                from scripts.run_codex import main
                orig_cwd = os.getcwd()
                os.chdir(td)
                try:
                    with self.assertRaises(SystemExit) as ctx:
                        main()
                    self.assertEqual(ctx.exception.code, 42)
                finally:
                    os.chdir(orig_cwd)


class CheckCodexSessionTokensTests(unittest.TestCase):
    def _write_session(self, session_dir, cwd, output_tokens):
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / 'rollout-2026-01-01T00-00-00-test.jsonl'
        lines = [
            json.dumps({'type': 'turn_context', 'payload': {'cwd': cwd}}),
            json.dumps({'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 100, 'output_tokens': output_tokens, 'total_tokens': 100 + output_tokens}}}}),
        ]
        session_file.write_text('\n'.join(lines) + '\n')

    def test_returns_true_when_tokens_present(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            sessions = Path(td) / 'sessions'
            self._write_session(sessions, str(workspace), output_tokens=500)
            with patch('scripts.run_codex.Path.home', return_value=Path(td)):
                # Need to create .codex/sessions structure
                codex_sessions = Path(td) / '.codex' / 'sessions'
                codex_sessions.mkdir(parents=True, exist_ok=True)
                self._write_session(codex_sessions, str(workspace), output_tokens=500)
                result = check_codex_session_tokens(str(workspace))
            self.assertTrue(result)

    def test_returns_false_when_zero_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            codex_sessions = Path(td) / '.codex' / 'sessions'
            self._write_session(codex_sessions, str(workspace), output_tokens=0)
            with patch('scripts.run_codex.Path.home', return_value=Path(td)):
                result = check_codex_session_tokens(str(workspace))
            self.assertFalse(result)

    def test_returns_true_when_no_session_found(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / 'workspace'
            workspace.mkdir()
            codex_sessions = Path(td) / '.codex' / 'sessions'
            codex_sessions.mkdir(parents=True, exist_ok=True)
            with patch('scripts.run_codex.Path.home', return_value=Path(td)):
                result = check_codex_session_tokens(str(workspace))
            self.assertTrue(result)


class ExtractCodexSkillUsageTests(unittest.TestCase):
    def _write_session(self, lines):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        for line in lines:
            f.write(json.dumps(line) + '\n')
        f.close()
        return Path(f.name)

    def test_extracts_skill_reads(self):
        p = self._write_session([
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': "sed -n '1,220p' .agents/skills/bio-chip-seq-peak-calling/SKILL.md"})}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': 'ls -l'})}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': "cat .agents/skills/bio-chipseq-qc/SKILL.md"})}},
        ])
        skills = extract_skills_from_codex_session(p)
        p.unlink()
        self.assertEqual(skills, ['bio-chip-seq-peak-calling', 'bio-chipseq-qc'])

    def test_no_skills(self):
        p = self._write_session([
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': 'macs3 callpeak -t treatment.tagAlign.gz'})}},
            {'type': 'event_msg', 'payload': {'type': 'task_complete'}},
        ])
        skills = extract_skills_from_codex_session(p)
        p.unlink()
        self.assertEqual(skills, [])

    def test_deduplicates(self):
        p = self._write_session([
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': "sed -n '1,220p' .agents/skills/bio-peak-calling/SKILL.md"})}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': "sed -n '1,60p' .agents/skills/bio-peak-calling/SKILL.md"})}},
        ])
        skills = extract_skills_from_codex_session(p)
        p.unlink()
        self.assertEqual(skills, ['bio-peak-calling'])

    def test_handles_absolute_paths(self):
        p = self._write_session([
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': "sed -n '1,220p' /Users/me/workspace/.agents/skills/bio-rnaseq/SKILL.md"})}},
        ])
        skills = extract_skills_from_codex_session(p)
        p.unlink()
        self.assertEqual(skills, ['bio-rnaseq'])


if __name__ == '__main__':
    unittest.main()
