import unittest
from detection_review import review_detections
class DetectionReviewTests(unittest.TestCase):
    def test_low_confidence(self):
        data=review_detections([{"label":"Direnç","confidence":0.3}])
        self.assertIn("Düşük güven",data[0]["review_note"])
    def test_manual_correction(self):
        data=review_detections([{"label":"Direnç","confidence":0.9}],{0:"MOSFET"})
        self.assertEqual(data[0]["label"],"MOSFET")
        self.assertTrue(data[0]["verified"])
    def test_unknown_class(self):
        data=review_detections([{"label":"Diğer: LED","confidence":0.8}])
        self.assertEqual(data[0]["label"],"Bilinmiyor")
if __name__=="__main__":
    unittest.main()
