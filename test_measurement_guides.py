import unittest
from measurement_guides import instruction_for
class MeasurementGuidesTests(unittest.TestCase):
    def test_mosfet_requires_datasheet(self):
        self.assertIn("datasheet",instruction_for("MOSFET")[1])
    def test_inductor_not_short(self):
        self.assertIn("tek başına",instruction_for("Bobin")[1])
if __name__=="__main__":
    unittest.main()
