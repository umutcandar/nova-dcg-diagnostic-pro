import unittest
from pin_mapping import suggest_probe_pair
class PinMappingTests(unittest.TestCase):
    def test_verified_mapping(self):
        p={"technician_verified":True,"pins":{"1":"G","2":"D","3":"S"}}
        r=suggest_probe_pair(p,{"1":[10,20],"2":[30,20],"3":[50,20]},"D","S")
        self.assertEqual(r["red"]["pin"],"2")
    def test_requires_verified_source(self):
        with self.assertRaises(ValueError):
            suggest_probe_pair({"pins":{"1":"D","2":"S"}},{"1":[1,1],"2":[2,2]},"D","S")
if __name__=="__main__":
    unittest.main()
