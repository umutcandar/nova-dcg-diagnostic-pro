import unittest
from probe_points import validate_probe_points
class ProbePointsTests(unittest.TestCase):
    def test_confirmed_points(self):
        r=validate_probe_points((100,100),(10,10,90,90),(20,20),(80,80),True)
        self.assertTrue(r["confirmed_by_technician"])
    def test_no_unconfirmed_points(self):
        with self.assertRaises(ValueError):
            validate_probe_points((100,100),(10,10,90,90),(20,20),(80,80))
    def test_reject_outside_box(self):
        with self.assertRaises(ValueError):
            validate_probe_points((100,100),(10,10,90,90),(1,1),(80,80),True)
if __name__=="__main__":
    unittest.main()
