import unittest
from multimeter_guides import guide_for

class GuideTests(unittest.TestCase):
    def test_no_invented_capacitance(self):
        self.assertIn("doğrulan",guide_for("capacitor")["expected"])
    def test_verified_example(self):
        self.assertIn("9–11 µF",guide_for("capacitor",10,10,"µF")["expected"])
    def test_diode_probe_polarity(self):
        self.assertIn("anot",guide_for("diode")["probes"])
    def test_ic_requires_pinout(self):
        self.assertIn("doğrulan",guide_for("ic")["probes"])
    def test_unknown_component(self):
        self.assertEqual(guide_for("unknown")["status"],"ek bilgi gerekli")
if __name__=="__main__":
    unittest.main()
