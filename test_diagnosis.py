import unittest
from diagnosis import prioritize

class DiagnosisTests(unittest.TestCase):
    def test_low_resistance_is_not_definitive(self):
        findings=prioritize([{"point":"VIN-GND","mode":"Direnç (Ω)","value":0.8}])
        self.assertIn("paralel",findings[0].reason)
        self.assertEqual(findings[0].priority,"Kontrol gerekli")

    def test_normal_value_does_not_prove_health(self):
        findings=prioritize([{"point":"R1","mode":"Direnç (Ω)","value":1000}])
        self.assertEqual(findings[0].priority,"Yetersiz kanıt")

    def test_invalid_values_ignored(self):
        findings=prioritize([{"point":"R1","mode":"resistance","value":"bad"}])
        self.assertEqual(findings[0].priority,"Yetersiz kanıt")

if __name__=="__main__":
    unittest.main()
