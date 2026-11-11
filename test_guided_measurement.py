import unittest
from guided_measurement import measurement_plan,evaluate
class GuidedMeasurementTests(unittest.TestCase):
    def test_detected_component_generates_task(self):
        tasks=measurement_plan([{"label":"Direnç","bbox_xyxy_pixels":[1,2,30,40],"confidence":0.8}])
        self.assertEqual(tasks[0]["mode"],"Direnç (Ω)")
    def test_no_false_good_verdict(self):
        task=measurement_plan([{"label":"Bobin","bbox_xyxy_pixels":[1,2,30,40]}])[0]
        self.assertEqual(evaluate(task,0.3)["status"],"Ek ölçüm gerekli")
    def test_zero_diode_requires_confirmation(self):
        task=measurement_plan([{"label":"Diyot","bbox_xyxy_pixels":[1,2,30,40]}])[0]
        self.assertEqual(evaluate(task,0)["status"],"Arıza şüphesi var")
    def test_invalid_box(self):
        with self.assertRaises(ValueError):
            measurement_plan([{"label":"Direnç","bbox_xyxy_pixels":[5,5,1,1]}])
if __name__=="__main__":
    unittest.main()
