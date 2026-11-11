import unittest
from circuit_analysis import analyze_circuit,example_circuit
class CircuitAnalysisTests(unittest.TestCase):
    def test_linked_components(self):
        data=example_circuit()
        result=analyze_circuit(**data)
        self.assertEqual(result[0]["refs"],["C1","F1","L1"])
        self.assertEqual(result[0]["priority"],2)
    def test_unknown_net_rejected(self):
        data=example_circuit()
        data["measurements"][0]["net"]="UNKNOWN"
        with self.assertRaises(ValueError):
            analyze_circuit(**data)
    def test_no_unsupported_verdict(self):
        data=example_circuit()
        self.assertIn("kanıtı değildir",analyze_circuit(**data)[0]["reason"])
if __name__=="__main__":
    unittest.main()
