import unittest
from model_inference import validate_model_classes
from dataset import CLASSES

class ModelInferenceTests(unittest.TestCase):
    def test_matching_classes(self):
        self.assertTrue(validate_model_classes(CLASSES))
    def test_reject_wrong_classes(self):
        with self.assertRaises(ValueError):
            validate_model_classes(["resistor","capacitor"])

if __name__=="__main__":
    unittest.main()
