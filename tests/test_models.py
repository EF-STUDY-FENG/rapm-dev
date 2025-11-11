import unittest, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from models import SectionTiming

class TestModels(unittest.TestCase):
    def test_remaining_seconds(self):
        st = SectionTiming()
        st.initialize(start_time=100.0, duration_seconds=60.0)
        self.assertTrue(st.is_initialized())
        self.assertAlmostEqual(st.remaining_seconds(now=100.0), 60.0, places=3)
        self.assertAlmostEqual(st.remaining_seconds(now=160.0), 0.0, places=3)
        # Not initialized path
        st2 = SectionTiming()
        self.assertEqual(st2.remaining_seconds(now=50.0), 0.0)

if __name__ == '__main__':
    unittest.main()
