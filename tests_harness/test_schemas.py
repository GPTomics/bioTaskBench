import unittest

from harness import schemas


class SchemasTests(unittest.TestCase):
    def test_task_weights_must_sum_to_one(self):
        task = {
            'test_id': 'x',
            'version': '1.0',
            'domain': 'chip-seq',
            'difficulty': 'basic',
            'prompt': 'p',
            'context': {},
            'evaluation': {
                'type': 'multi_criteria',
                'criteria': [
                    {'name': 'a', 'type': 'file_check', 'description': 'd', 'weight': 0.9, 'target_pattern': '*.tsv'},
                ],
            },
            'metadata': {},
        }
        errors = schemas.validate_task(task)
        self.assertTrue(any('weights must sum to 1.0' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
