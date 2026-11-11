import unittest
from component_labeler import normalized_box

class LabelTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalized_box(10,20,30,40,100,100),[0.1,0.2,0.3,0.4])
    def test_reverse_drag(self):
        self.assertEqual(normalized_box(30,40,10,20,100,100),[0.1,0.2,0.3,0.4])
    def test_small_box_rejected(self):
        with self.assertRaises(ValueError):
            normalized_box(10,10,10,10,100,100)

if __name__=="__main__":
    unittest.main()
