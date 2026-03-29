import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_claude import build_claude_command, build_preflight_command, generate_claude_md
from scripts.extract_skill_usage import extract_skills_from_claude_session, match_test_id


class GenerateClaudeMdTests(unittest.TestCase):
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

    def test_generate_claude_md_basic(self):
        task = self._make_task()
        result = generate_claude_md(task)
        self.assertEqual(result.count('# Task: test-001'), 1)
        self.assertIn('Compute stats from input.tsv', result)
        self.assertIn('input.tsv', result)
        self.assertIn('Synthetic test data', result)
        self.assertIn('Python and R available', result)

    def test_generate_claude_md_multiple_data_files(self):
        task = self._make_task()
        task['context']['data_files'] = ['reads_1.fq.gz', 'reads_2.fq.gz', 'reference.fa']
        result = generate_claude_md(task)
        self.assertIn('reads_1.fq.gz', result)
        self.assertIn('reads_2.fq.gz', result)
        self.assertIn('reference.fa', result)

    def test_generate_claude_md_no_eval_leakage(self):
        task = self._make_task()
        task['evaluation'] = {'criteria': [{'weight': 0.7, 'range': [1, 10], 'type': 'range_check'}]}
        result = generate_claude_md(task)
        self.assertNotIn('0.7', result)
        self.assertNotIn('range_check', result)
        self.assertNotIn('[1, 10]', result)

    def test_generate_claude_md_with_skills_true(self):
        task = self._make_task()
        result = generate_claude_md(task, use_skills=True)
        self.assertIn('Use Skills', result)
        self.assertIn('bioinformatics skills installed', result)
        self.assertIn('locally installed tools', result)

    def test_generate_claude_md_with_skills_false(self):
        task = self._make_task()
        result = generate_claude_md(task, use_skills=False)
        self.assertNotIn('Use Skills', result)
        self.assertIn('locally installed tools', result)

    def test_generate_claude_md_default_no_skills(self):
        task = self._make_task()
        result = generate_claude_md(task)
        self.assertNotIn('Use Skills', result)
        self.assertIn('locally installed tools', result)

    def test_generate_claude_md_missing_optional_fields(self):
        task = {'test_id': 'x', 'prompt': 'Do something', 'context': {'data_files': []}}
        result = generate_claude_md(task)
        self.assertIn('Do something', result)
        self.assertIn('# Task: x', result)
        self.assertNotIn('Available Data', result)
        self.assertNotIn('Setup Notes', result)


class BuildClaudeCommandTests(unittest.TestCase):
    def test_build_claude_command_with_model(self):
        cmd = build_claude_command(model='claude-opus-4-6')
        self.assertIn('claude', cmd)
        self.assertIn('-p', cmd)
        self.assertIn('--dangerously-skip-permissions', cmd)
        self.assertIn('--model', cmd)
        self.assertIn('claude-opus-4-6', cmd)
        self.assertIn('--max-turns', cmd)

    def test_build_claude_command_no_model(self):
        cmd = build_claude_command(model=None)
        self.assertIn('claude', cmd)
        self.assertIn('-p', cmd)
        self.assertNotIn('--model', cmd)

    def test_build_claude_command_with_skills(self):
        cmd = build_claude_command(model='claude-opus-4-6', use_skills=True)
        self.assertIn('skills', cmd.lower())
        self.assertIn('Complete the bioinformatics analysis task', cmd)
        self.assertIn('load them as a tool', cmd)

    def test_build_claude_command_without_skills(self):
        cmd = build_claude_command(model=None, use_skills=False)
        self.assertNotIn('skills', cmd.lower())
        self.assertIn('Complete the bioinformatics analysis task', cmd)

    def test_build_preflight_command(self):
        cmd = build_preflight_command(model='claude-opus-4-6')
        self.assertIn('claude', cmd)
        self.assertIn('-p', cmd)
        self.assertIn('--dangerously-skip-permissions', cmd)
        self.assertIn('CLAUDE.md', cmd)
        self.assertIn('skills', cmd.lower())
        self.assertIn('--max-turns', cmd)
        self.assertIn('3', cmd)
        self.assertIn('--model', cmd)
        self.assertIn('claude-opus-4-6', cmd)

    def test_build_preflight_command_no_model(self):
        cmd = build_preflight_command(model=None)
        self.assertIn('claude', cmd)
        self.assertNotIn('--model', cmd)

    def test_build_claude_command_with_effort(self):
        cmd = build_claude_command(effort='high')
        self.assertIn('--effort', cmd)
        self.assertIn('high', cmd)

    def test_build_claude_command_no_effort(self):
        cmd = build_claude_command()
        self.assertNotIn('--effort', cmd)


class ExtractSkillUsageTests(unittest.TestCase):
    def test_extract_skills_from_claude_session(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps({'message': {'content': [{'name': 'Skill', 'input': {'skill': 'bio-chip-seq-peak-calling'}}]}}) + '\n')
            f.write(json.dumps({'message': {'content': [{'name': 'Bash', 'input': {'command': 'ls'}}]}}) + '\n')
            f.write(json.dumps({'message': {'content': [{'name': 'Skill', 'input': {'skill': 'bio-chip-seq-motif-analysis'}}]}}) + '\n')
            f.write(json.dumps({'type': 'queue-operation'}) + '\n')
            tmp_path = f.name
        skills = extract_skills_from_claude_session(Path(tmp_path))
        Path(tmp_path).unlink()
        self.assertEqual(skills, ['bio-chip-seq-peak-calling', 'bio-chip-seq-motif-analysis'])

    def test_extract_skills_from_claude_session_no_skills(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps({'message': {'content': [{'name': 'Bash', 'input': {'command': 'macs3 callpeak'}}]}}) + '\n')
            tmp_path = f.name
        skills = extract_skills_from_claude_session(Path(tmp_path))
        Path(tmp_path).unlink()
        self.assertEqual(skills, [])

    def test_match_test_id(self):
        known = {'chipseq-001', 'chipseq-002', 'crispr-003', 'metab-001'}
        self.assertEqual(match_test_id('chipseq-001-967hidth', known), 'chipseq-001')
        self.assertEqual(match_test_id('chipseq-001-law3-l9n', known), 'chipseq-001')
        self.assertEqual(match_test_id('crispr-003--kgkz3oh', known), 'crispr-003')
        self.assertEqual(match_test_id('metab-001', known), 'metab-001')


if __name__ == '__main__':
    unittest.main()
