import unittest
from measurement_reference import compare,validate_spec
S={"part_number":"IRF540N","source_url":"https://example.com/reference","mode":"Diyot (V)","unit":"Diyot (V)","minimum":0.3,"maximum":0.8,"conditions":"example test fixture","circuit_state":"out_of_circuit","limit_type":"measurement_reference","technician_verified":True}
class ReferenceTests(unittest.TestCase):
    def test_reference_range_not_health_verdict(self):
        self.assertEqual(compare(S,{"part_number":"IRF540N","mode":"Diyot (V)"},0.5,"out_of_circuit")["status"],"Referans aralığında")
    def test_circuit_state_mismatch(self):
        self.assertEqual(compare(S,{"part_number":"IRF540N","mode":"Diyot (V)"},0.5,"in_circuit")["status"],"Ek ölçüm gerekli")
    def test_reject_maximum_ratings(self):
        with self.assertRaises(ValueError):
            validate_spec({**S,"limit_type":"absolute_maximum"})
if __name__=="__main__":
    unittest.main()
