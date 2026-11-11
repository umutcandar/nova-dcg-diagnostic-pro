import unittest
from component_ocr import candidate_markings
class ComponentOcrTests(unittest.TestCase):
    def test_markings(self):
        self.assertEqual(candidate_markings("IRF540N\nIRF540N\nR1"),["IRF540N"])
    def test_no_numeric_code(self):
        self.assertEqual(candidate_markings("MOSFET"),[])
if __name__=="__main__":
    unittest.main()
