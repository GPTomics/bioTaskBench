import tempfile
import unittest
from pathlib import Path

from harness import grader


class SetOverlapTests(unittest.TestCase):
    def test_peak_count_jaccard(self):
        with tempfile.TemporaryDirectory() as td:
            truth = Path(td) / 'truth.bed'
            pred = Path(td) / 'pred.bed'
            truth.write_text('chr1\t100\t200\nchr1\t500\t600\n')
            pred.write_text('chr1\t120\t180\nchr1\t700\t800\n')
            score = grader._peak_count_jaccard(grader._read_intervals(truth), grader._read_intervals(pred), 0)
            self.assertAlmostEqual(score, 1 / 3)


if __name__ == '__main__':
    unittest.main()
