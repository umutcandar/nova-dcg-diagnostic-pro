import unittest
from detection_pipeline import filter_detections
class DetectionPipelineTests(unittest.TestCase):
    def test_filter(self):
        valid={"label":"Direnç","confidence":0.8,"bbox_xyxy_pixels":[10,10,30,30]}
        low={"label":"Diyot","confidence":0.2,"bbox_xyxy_pixels":[40,40,60,60]}
        accepted,rejected=filter_detections([valid,low],(100,100),0.5)
        self.assertEqual(len(accepted),1)
        self.assertEqual(len(rejected),1)
        self.assertFalse(accepted[0]["verified"])
    def test_bad_box(self):
        accepted,rejected=filter_detections([{"confidence":0.9,"bbox_xyxy_pixels":[-1,0,10,10]}],(100,100))
        self.assertEqual(len(accepted),0)
        self.assertEqual(len(rejected),1)
if __name__=="__main__":
    unittest.main()
