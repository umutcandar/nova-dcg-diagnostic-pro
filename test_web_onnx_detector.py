"""Offline CPU ONNX PCB detector regression tests; no network or weights."""
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import numpy as np

import web_onnx_detector as model


class ONNXDetectorTests(unittest.TestCase):
    def test_model_is_pinned_and_potentiometer_label_is_known(self):
        self.assertEqual(len(model.CLASSES),21)
        self.assertEqual(model.CLASSES[15],"potentiometer")
        self.assertEqual(model.LABELS["potentiometer"],"Trimpot")
        self.assertEqual(len(model.EXPECTED_SHA256),64)
        self.assertEqual(model.EXPECTED_SIZE,44777137)

    def fake_prediction(self):
        return np.zeros((1,25,8400),dtype=np.float32)

    def test_trimpot_box_is_mapped_from_letterbox_to_photo(self):
        # Original photo is 1280x800, resized to 640x400 with 120px top padding.
        prediction=self.fake_prediction()
        prediction[0,0,500]=320
        prediction[0,1,500]=320
        prediction[0,2,500]=100
        prediction[0,3,500]=80
        prediction[0,4+15,500]=.90
        result=model.decode_predictions(prediction,1280,800,.5,0,120)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["label"],"Trimpot")
        self.assertEqual(result[0]["source_label"],"potentiometer")
        self.assertFalse(result[0]["verified"])
        self.assertAlmostEqual(result[0]["bbox_xyxy_pixels"][0],540.0)
        self.assertAlmostEqual(result[0]["bbox_xyxy_pixels"][1],320.0)
        self.assertAlmostEqual(result[0]["bbox_xyxy_pixels"][2],740.0)
        self.assertAlmostEqual(result[0]["bbox_xyxy_pixels"][3],480.0)

    def test_model_returns_second_chance_component_types(self):
        output=self.fake_prediction()
        output[0,0,20]=300
        output[0,1,20]=280
        output[0,2,20]=90
        output[0,3,20]=170
        output[0,4+6,20]=.47   # diode
        output[0,4+3,20]=.36   # capacitor
        output[0,4+20,20]=.13  # transistor
        actual=model.decode_predictions(output,640,640,1,0,0)
        self.assertEqual(actual[0]["label"],"Diyot")
        self.assertEqual(
            [x["label"] for x in actual[0]["alternatives"]],
            ["Diyot","Kondansatör","Transistör"]
        )
        self.assertEqual(actual[0]["alternatives"][1]["confidence"],.36)

    def test_tiled_inference_crops_stay_inside_large_photo(self):
        self.assertEqual(model.candidate_tiles(640,480),[])
        crop_regions=model.candidate_tiles(1600,1200)
        self.assertGreaterEqual(len(crop_regions),4)
        self.assertLessEqual(len(crop_regions),25)
        for x1,y1,x2,y2 in crop_regions:
            self.assertTrue(0<=x1<x2<=1600)
            self.assertTrue(0<=y1<y2<=1200)
            self.assertTrue(x2-x1>=640)

    def test_every_pixel_is_covered_even_on_4k_and_8k_photos(self):
        for width,height in ((4096,3072),(7680,4320),(2048,1536),(2800,900),(1200,2400)):
            tiles=model.candidate_tiles(width,height)
            self.assertGreaterEqual(len(tiles),1)
            self.assertLessEqual(len(tiles),25)
            # Sample every 1/24th grid cell across the entire photograph.
            for iy in range(25):
                y=(iy+.5)*height/25
                for ix in range(25):
                    x=(ix+.5)*width/25
                    self.assertTrue(any(x1<=x<x2 and y1<=y<y2
                        for x1,y1,x2,y2 in tiles),
                        msg=f"Uncovered pixel ({x:.0f},{y:.0f}) on {width}x{height}")

    def test_original_3_by_3_crops_are_preserved_on_medium_photos(self):
        width,height=1600,1200
        size=min(1024,max(640,round(max(width,height)*.58)))
        xs=sorted(set((0,(width-size)//2,width-size)))
        ys=sorted(set((0,(height-size)//2,height-size)))
        expected=[(x,y,x+size,y+size) for y in ys for x in xs]
        self.assertEqual(model.candidate_tiles(width,height),expected)

    def test_4k_expansion_preserves_old_anchor_boxes(self):
        width,height=4096,3072
        old_size=1024
        xs=(0,(width-old_size)//2,width-old_size)
        ys=(0,(height-old_size)//2,height-old_size)
        tiles=set(model.candidate_tiles(width,height))
        for y in ys:
            for x in xs:
                self.assertIn((x,y,x+old_size,y+old_size),tiles)
        self.assertGreater(len(tiles),9)
        self.assertLessEqual(len(tiles),25)

    def test_adjacent_tiles_overlap_instead_of_leaving_resized_gaps(self):
        tiles=model.candidate_tiles(4096,3072)
        xs=sorted(set((x1,x2) for x1,_,x2,_ in tiles))
        ys=sorted(set((y1,y2) for _,y1,_,y2 in tiles))
        for axis in (xs,ys):
            self.assertEqual(axis[0][0],0)
            for prior,following in zip(axis,axis[1:]):
                self.assertGreater(prior[1]-following[0],0)

    def test_tiled_inference_removes_same_class_duplicates_but_keeps_ambiguity(self):
        shared={"label":"Kondansatör","source_label":"capacitor"}
        first={**shared,"confidence":.8,"bbox_xyxy_pixels":[10,20,80,130]}
        duplicate={**shared,"confidence":.5,"bbox_xyxy_pixels":[11,21,81,131]}
        different={"label":"Diyot","source_label":"diode","confidence":.65,
                   "bbox_xyxy_pixels":[11,21,81,131]}
        result=model.merge_overlapping_detections([duplicate,different,first])
        self.assertEqual(len(result),2)
        self.assertEqual([x["source_label"] for x in result],["capacitor","diode"] if
                         result[0]["confidence"]>.7 else ["diode","capacitor"])
        self.assertEqual(next(x for x in result if x["source_label"]=="capacitor")["confidence"],.8)

    def test_low_confidence_predictions_are_not_reported(self):
        data=self.fake_prediction()
        data[0,0,100]=100
        data[0,1,100]=100
        data[0,2,100]=30
        data[0,3,100]=30
        data[0,4+17,100]=.11
        self.assertEqual(model.decode_predictions(data,640,640,1,0,0),[])

    def test_overlapping_same_class_is_deduplicated(self):
        data=self.fake_prediction()
        for index,score in ((30,.90),(40,.60)):
            data[0,0,index]=200
            data[0,1,index]=200
            data[0,2,index]=50
            data[0,3,index]=35
            data[0,4+17,index]=score
        actual=model.decode_predictions(data,640,640,1,0,0)
        self.assertEqual(len(actual),1)
        self.assertEqual(actual[0]["label"],"Direnç")

    def test_invalid_output_shape_is_rejected(self):
        with self.assertRaises(model.OnnxDetectorError):
            model.decode_predictions(np.zeros((1,24,8400)),640,640,1,0,0)
        data=self.fake_prediction()
        data[0,0,10]=np.nan
        with self.assertRaises(model.OnnxDetectorError):
            model.decode_predictions(data,640,640,1,0,0)

    def test_existing_tampered_weights_are_rejected_not_executed(self):
        with TemporaryDirectory() as temp:
            weights=Path(temp)/"pcb.onnx"
            weights.write_bytes(b"not a model")
            with self.assertRaises(model.OnnxDetectorError):
                model.ensure_weights(weights)

    def test_classes_have_explicit_no_unknown_to_resistor_mapping(self):
        self.assertEqual(model.LABELS["fuse"],"Sigorta")
        self.assertEqual(model.LABELS["ic"],"Entegre")
        self.assertEqual(model.LABELS["heatsink"],"Soğutucu")


if __name__=="__main__":
    unittest.main()
