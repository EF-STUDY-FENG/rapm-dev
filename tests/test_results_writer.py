import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from models import SectionTiming  # noqa: E402
from results_writer import ResultsWriter  # noqa: E402


class TestResultsWriter(unittest.TestCase):
    def test_save_creates_files_and_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResultsWriter(output_dir=tmpdir)
            participant = {"participant_id": "T001"}
            practice_conf = {
                'set': 'A',
                'time_limit_minutes': 1,
                'items': [
                    {'id': 'P01', 'question_image': '', 'options': ['']*8, 'correct': 2}
                ],
            }
            formal_conf = {
                'set': 'B',
                'time_limit_minutes': 1,
                'items': [
                    {'id': 'F01', 'question_image': '', 'options': ['']*8, 'correct': 3}
                ],
            }
            practice_ans = {'P01': 2}
            formal_ans = {'F01': 1}
            p_timing = SectionTiming()
            p_timing.initialize(0.0, 60.0)
            f_timing = SectionTiming()
            f_timing.initialize(0.0, 60.0)
            csv_path, json_path = writer.save(
                participant, practice_conf, formal_conf,
                practice_ans, formal_ans, p_timing, f_timing
            )
            self.assertTrue(os.path.exists(csv_path))
            self.assertTrue(os.path.exists(json_path))
            with open(json_path, encoding='utf-8') as f:
                meta = json.load(f)
            self.assertEqual(meta['participant']['participant_id'], 'T001')
            self.assertEqual(meta['practice']['correct_count'], 1)
            self.assertEqual(meta['formal']['correct_count'], 0)
            self.assertIn('remaining_seconds_at_save', meta['practice'])

if __name__ == '__main__':
    unittest.main()
