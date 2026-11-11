import unittest
from dataset import validate_annotation

class DatasetTests(unittest.TestCase):
    def test_conversion(self):
        data={"coordinate_system":"xyxy_normalized","regions":[
            {"label":"Direnç","bbox_xyxy_normalized":[0.1,0.2,0.5,0.6]}]}
        rows=validate_annotation(data)
        self.assertEqual(rows[0][0],0)
        for actual,expected in zip(rows[0][1:],(0.3,0.4,0.4,0.4)):
            self.assertAlmostEqual(actual,expected)
    def test_reject_outside(self):
        with self.assertRaises(ValueError):
            validate_annotation({"coordinate_system":"xyxy_normalized","regions":[
                {"label":"Diyot","bbox_xyxy_normalized":[0,0,1.1,1]}]})
    def test_reject_unknown(self):
        with self.assertRaises(ValueError):
            validate_annotation({"coordinate_system":"xyxy_normalized","regions":[
                {"label":"unknown","bbox_xyxy_normalized":[0,0,0.2,0.2]}]})

if __name__=="__main__":
    unittest.main()
