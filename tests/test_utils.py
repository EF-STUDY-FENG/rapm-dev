import os, sys
import unittest

# Ensure src/ is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from utils import build_items_from_pattern

class TestUtils(unittest.TestCase):
    def test_build_items_from_pattern_basic(self):
        pattern = 'stimuli/images/RAPM_t{XX}-{Y}.jpg'
        answers = [3, 5, 2]
        items = build_items_from_pattern(pattern, count=3, answers=answers, start_index=0, section_prefix='P')
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]['id'], 'P01')
        self.assertIn('RAPM_t01-0.jpg', items[0]['question_image'])
        self.assertEqual(len(items[0]['options']), 8)
        self.assertEqual(items[1]['correct'], 5)
        # Start index offset
        items2 = build_items_from_pattern(pattern, count=2, answers=answers, start_index=1, section_prefix='F')
        self.assertEqual(items2[0]['correct'], 5)
        self.assertEqual(items2[1]['correct'], 2)

if __name__ == '__main__':
    unittest.main()
