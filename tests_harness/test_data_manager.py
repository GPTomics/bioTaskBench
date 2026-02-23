import tempfile
import unittest
from pathlib import Path

from harness import data_manager


class DataManagerTests(unittest.TestCase):
    def test_audit_data_sizes_reports_limits_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            tests = Path(td) / 'tests' / 'd'
            case = tests / 't1'
            data = case / 'data'
            data.mkdir(parents=True, exist_ok=True)
            (tests / 'manifest.json').write_text('{"domain":"d","display_name":"D","description":"x","tests":[{"test_id":"t1"}]}')
            (case / 'task.json').write_text(
                '{"test_id":"t1","version":"1.0","domain":"d","difficulty":"basic","prompt":"p","context":{"data_files":["a.tsv","missing.tsv"]},"evaluation":{"type":"multi_criteria","criteria":[{"name":"x","type":"file_check","description":"d","weight":1.0,"target_pattern":"*.txt"}]},"metadata":{}}'
            )
            (data / 'a.tsv').write_text('x\n')

            report = data_manager.audit_data_sizes(Path(td) / 'tests', max_test_mb=0.000001, max_total_mb=1)
            self.assertEqual(report['tests_total'], 1)
            self.assertEqual(len(report['per_test_size_violations']), 1)
            self.assertEqual(len(report['tests_with_missing_data_files']), 1)


if __name__ == '__main__':
    unittest.main()
