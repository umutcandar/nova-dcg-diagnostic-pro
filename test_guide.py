import unittest
from guide import GUIDES, steps_for

class GuideTests(unittest.TestCase):
    def test_all_guides_have_steps(self):
        for name in GUIDES:
            self.assertGreaterEqual(len(steps_for(name)), 3)
    def test_unknown(self):
        self.assertEqual(steps_for("unknown"), [])

if __name__ == "__main__":
    unittest.main()
