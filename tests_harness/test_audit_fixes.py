import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

from harness import grader


REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / 'tests'


class ChipSeq002FabricationTest(unittest.TestCase):
    '''A fabricated motifs.tsv with fake consensus sequences must score < 1.0.'''

    def test_fabricated_motifs_score_below_one(self):
        task_path = TESTS_ROOT / 'chip-seq' / 'chipseq-002' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        test_dir = task_path.parent

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            motifs = workspace / 'motifs.tsv'
            motifs.write_text(
                'motif_id\tconsensus\tp_value\tpct_target\n'
                'CTCF\tAAAAAAAAAAAA\t1e-20\t85\n'
                'FakeTF1\tCCCCCCCCCC\t1e-8\t41\n'
                'FakeTF2\tGGGGGGGGGG\t2e-7\t35\n'
                'FakeTF3\tTTTTTTTTTT\t8e-6\t29\n'
                'FakeTF4\tACACACACACG\t1e-4\t21\n'
            )
            result = grader.grade_task(task, workspace, test_dir)
            self.assertLess(result['score'], 1.0,
                            'Fabricated motifs should not score full marks')


class ChipSeq003ShuffledAnnotationsTest(unittest.TestCase):
    '''Shuffling gene assignments across rows must score < 1.0.'''

    def test_shuffled_gene_assignments_score_below_one(self):
        task_path = TESTS_ROOT / 'chip-seq' / 'chipseq-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        test_dir = task_path.parent
        expected_path = test_dir / 'expected' / 'annotations.tsv'

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            annotations = workspace / 'annotations.tsv'

            with expected_path.open() as f:
                reader = csv.DictReader(f, delimiter='\t')
                rows = list(reader)

            genes = [r['nearest_gene'] for r in rows]
            distances = [r['distance_to_tss'] for r in rows]
            shifted_genes = genes[1:] + genes[:1]
            shifted_distances = distances[1:] + distances[:1]
            for i, row in enumerate(rows):
                row['nearest_gene'] = shifted_genes[i]
                row['distance_to_tss'] = shifted_distances[i]

            fieldnames = list(rows[0].keys())
            with annotations.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
                writer.writeheader()
                writer.writerows(rows)

            result = grader.grade_task(task, workspace, test_dir)
            self.assertLess(result['score'], 1.0,
                            'Shuffled gene assignments should not score full marks')


class Stx003MissingCentroidsTest(unittest.TestCase):
    '''Output without mean_x/mean_y columns must score < 1.0 after fix.'''

    def test_missing_centroids_score_below_one(self):
        task_path = TESTS_ROOT / 'spatial-transcriptomics' / 'stx-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        test_dir = task_path.parent

        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            output = workspace / 'cluster_summary.tsv'
            output.write_text(
                'cluster\tmean_marker_expression\tenriched\n'
                'C1\t2.1\tFALSE\n'
                'C2\t6.8\tTRUE\n'
                'C3\t2.3\tFALSE\n'
                'C4\t2.0\tFALSE\n'
                'C5\t6.7\tTRUE\n'
                'C6\t2.4\tFALSE\n'
                'C7\t2.2\tFALSE\n'
            )
            result = grader.grade_task(task, workspace, test_dir)
            self.assertLess(result['score'], 1.0,
                            'Missing centroid columns should not score full marks')


class Crispr003SetupNotesTest(unittest.TestCase):
    '''setup_notes must not contain false n>=20 claim.'''

    def test_no_false_sample_size_claim(self):
        task_path = TESTS_ROOT / 'crispr-screens' / 'crispr-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        notes = task['context']['setup_notes']
        self.assertNotIn('n >= 20', notes, 'setup_notes should not claim n >= 20 guides per gene')
        self.assertIn('12', notes, 'setup_notes should mention 12 values per group (4 guides x 3 reps)')

    def test_simplified_caveat_present(self):
        task_path = TESTS_ROOT / 'crispr-screens' / 'crispr-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        notes = task['context']['setup_notes'].lower()
        self.assertTrue('simplified' in notes or 'simplif' in notes,
                        'setup_notes should acknowledge this is a simplified approach')


class Lrs003CigarOpsTest(unittest.TestCase):
    '''Generated CIGAR strings must use =/X ops, not M.'''

    def test_no_m_op_in_generated_data(self):
        input_path = TESTS_ROOT / 'long-read-sequencing' / 'lrs-003' / 'data' / 'read_alignments.tsv'
        with input_path.open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                cigar = row['cigar']
                ops = re.findall(r'[A-Z=]', cigar)
                self.assertNotIn('M', ops, f'CIGAR should not contain M op: {cigar[:60]}...')
                self.assertTrue(any(op in ('=', 'X') for op in ops),
                                f'CIGAR should contain = or X ops: {cigar[:60]}...')

    def test_error_rate_excludes_softclips(self):
        task_path = TESTS_ROOT / 'long-read-sequencing' / 'lrs-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        prompt = task['prompt']
        self.assertIn('mismatch_bp', prompt, 'Prompt should reference mismatch_bp column')
        self.assertNotIn('softclip_bp) / (seq_match_bp + mismatch_bp + insertion_bp + deletion_bp + softclip_bp)',
                         prompt, 'error_rate formula should NOT include softclip_bp in denominator')


class Meth003FramingTest(unittest.TestCase):
    '''meth-003 should not reference bsseq and should use dmc.tsv.'''

    def test_no_bsseq_in_expected_tools(self):
        task_path = TESTS_ROOT / 'methylation-analysis' / 'meth-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        self.assertNotIn('bsseq', task['context']['expected_tools'],
                         'expected_tools should not include bsseq')

    def test_output_file_is_dmc_not_dmr(self):
        task_path = TESTS_ROOT / 'methylation-analysis' / 'meth-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        for criterion in task['evaluation']['criteria']:
            target = criterion.get('target_file', '')
            if target:
                self.assertNotEqual(target, 'dmr.tsv',
                                    f'criterion {criterion["name"]} should target dmc.tsv not dmr.tsv')

    def test_setup_notes_frames_as_simplified(self):
        task_path = TESTS_ROOT / 'methylation-analysis' / 'meth-003' / 'task.json'
        with task_path.open() as f:
            task = json.load(f)
        notes = task['context']['setup_notes'].lower()
        self.assertTrue('simplified' in notes or 'simplif' in notes,
                        'setup_notes should frame t-test as simplified benchmark approach')
        self.assertNotIn('bsseq', notes.lower(), 'setup_notes should not reference bsseq')


if __name__ == '__main__':
    unittest.main()
