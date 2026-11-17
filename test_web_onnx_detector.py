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
