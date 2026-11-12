import unittest
from pcb_viewport import Viewport


class ViewportTests(unittest.TestCase):
    def test_fit_places_image_inside_canvas(self):
        v=Viewport(image_width=1400,image_height=900,canvas_width=800,canvas_height=600)
        v.fit()
        x,y=v.to_canvas(0,0)
        far_x,far_y=v.to_canvas(1400,900)
        self.assertGreaterEqual(x,0)
        self.assertGreaterEqual(y,0)
        self.assertLessEqual(far_x,800)
        self.assertLessEqual(far_y,600)

    def test_cursor_locked_zoom_and_inverse(self):
        v=Viewport(image_width=1200,image_height=800,canvas_width=700,canvas_height=500)
        v.fit()
        before=v.to_image(215,143)
        v.zoom(1.5,215,143)
        after=v.to_image(215,143)
        self.assertAlmostEqual(before[0],after[0])
        self.assertAlmostEqual(before[1],after[1])
        v.pan(35,-20)
        px,py=v.to_canvas(700,400)
        ix,iy=v.to_image(px,py)
        self.assertAlmostEqual(ix,700)
        self.assertAlmostEqual(iy,400)

    def test_visible_crop_stays_in_original_photo(self):
        v=Viewport(image_width=4000,image_height=2500,canvas_width=900,canvas_height=650)
        v.fit()
        self.assertEqual(v.visible_crop(),(0,0,4000,2500))
        v.zoom(5,450,325)
        crop=v.visible_crop()
        self.assertTrue(crop)
        self.assertGreaterEqual(crop[0],0)
        self.assertLessEqual(crop[2],4000)
        self.assertLess(crop[2]-crop[0],4000)

    def test_click_finds_smallest_box(self):
        v=Viewport(image_width=1000,image_height=600,canvas_width=1000,canvas_height=600)
        boxes=[[20,20,300,300],[70,70,95,95]]
        self.assertEqual(v.find_box(boxes,80,80),1)
        self.assertIsNone(v.find_box(boxes,999,590))

    def test_reject_invalid_zoom(self):
        v=Viewport()
        for factor in (0,-1,float("nan"),float("inf")):
            with self.subTest(factor=factor):
                with self.assertRaises(ValueError):
                    v.zoom(factor,0,0)
if __name__=="__main__":
    unittest.main()
