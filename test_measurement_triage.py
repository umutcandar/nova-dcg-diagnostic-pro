import unittest
from measurement_triage import Measurement,triage
class MeasurementTriageTests(unittest.TestCase):
    def test_in_circuit_never_definitive(self):
        m=Measurement("resistor","resistance",99,"ohm","in_circuit",True,90,110)
        self.assertEqual(triage(m)["status"],"ek ölçüm gerekli")
    def test_outside_reference(self):
        m=Measurement("resistor","resistance",120,"ohm","out_of_circuit",True,90,110)
        self.assertEqual(triage(m)["status"],"referans dışında")
    def test_missing_reference(self):
        m=Measurement("diode","diode",0.6,"V","out_of_circuit")
        self.assertEqual(triage(m)["status"],"ek ölçüm gerekli")
if __name__=="__main__":
    unittest.main()
