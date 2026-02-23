import tempfile
import unittest
from pathlib import Path

from harness import grader


class GraderCoreTests(unittest.TestCase):
    def test_exact_match_exclude_patterns(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'motifs.tsv'
            p.write_text('motif_name\tp\nCTCFL\t1e-6\nCTCF\t1e-9\n')
            criterion = {
                'type': 'exact_match',
                'target_file': 'motifs.tsv',
                'target': 'CTCF',
                'match_type': 'substring_case_insensitive',
                'exclude_patterns': ['CTCFL'],
            }
            res = grader._grade_exact_match(criterion, td)
            self.assertEqual(res['score'], 1.0)

    def test_range_check_partial(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'x.tsv'
            p.write_text('val\n45\n')
            criterion = {
                'type': 'range_check',
                'target_file': 'x.tsv',
                'field': 'top_val',
                'range': [60, 100],
                'partial_range': [30, 60],
                'partial_score': 0.5,
            }
            res = grader._grade_range_check(criterion, td)
            self.assertEqual(res['score'], 0.5)


if __name__ == '__main__':
    unittest.main()
