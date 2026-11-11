import unittest
from photo_coordinates import image_to_widget_point
class PhotoCoordinatesTests(unittest.TestCase):
    def test_scaled(self):
        self.assertEqual(image_to_widget_point(100,50,(2000,1000),(500,250)),(400,200))
    def test_offset(self):
        self.assertEqual(image_to_widget_point(110,60,(2000,1000),(500,250),(10,10)),(400,200))
    def test_outside(self):
        with self.assertRaises(ValueError):
            image_to_widget_point(999,50,(2000,1000),(500,250))
if __name__=="__main__":
    unittest.main()
