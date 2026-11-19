"""Test SHA256 release gating and honest second-visual-model disagreement."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from pcb_secondary_inference import (
    SecondaryModelError,verify_artifact,evaluate_detections,
    run_if_approved,score_image_region,preprocess_crop,
)


class DummyInput:
    name="image"


class FakeOnnxSession:
    def __init__(self,logits):
        self.logits=logits
        self.calls=0
    def get_inputs(self):
        return [DummyInput()]
    def run(self,unused,inputs):
        import numpy as np
        self.calls+=1
        tensor=inputs["image"]
        assert tensor.shape==(1,3,160,160),tensor.shape
        return [np.asarray([self.logits],dtype=np.float32)]


def labeled(box,label,score=.50):
    return {"label":label,"bbox_xyxy_pixels":list(box),"confidence":score,
            "review_required":False,"review_note":"","verified":False}


class IndependentReviewerInferenceTests(unittest.TestCase):
    def test_invalid_release_or_checksum_cannot_be_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            onnx=folder/"reviewer_capacitor_diode.onnx"
            onnx.write_bytes(b"this is a deliberately fake test model")
            report={
                "schema":"nova-independent-capacitor-diode-reviewer-v1",
                "labels":["capacitor","diode"],
                "source_audit":{"full_zip_md5_verified":True},
                "independent_board_disjoint":True,
                "approved_for_live_use":False,
                "model":{"file":onnx.name,"sha256":hashlib.sha256(onnx.read_bytes()).hexdigest(),
                         "bytes":onnx.stat().st_size},
            }
            manifest=folder/"report.json"
            manifest.write_text(json.dumps(report))
            self.assertFalse(verify_artifact(manifest,onnx)["approved_for_live_use"])
            with self.assertRaisesRegex(SecondaryModelError,"approval"):
                verify_artifact(manifest,onnx,require_release=True)
            report["approved_for_live_use"]=True
            manifest.write_text(json.dumps(report))
            self.assertTrue(verify_artifact(manifest,onnx,require_release=True)["approved_for_live_use"])
            onnx.write_bytes(b"tampered")
            with self.assertRaisesRegex(SecondaryModelError,"count|SHA256"):
                verify_artifact(manifest,onnx,require_release=True)

    def test_independent_visual_disagreement_requires_review_but_never_edits_class(self):
        image=Image.new("RGB",(800,600),(60,95,70))
        diode=labeled([110,60,180,170],"Diyot")
        cap=labeled([300,60,360,165],"Kondansatör")
        model=FakeOnnxSession([5.,1.])
        items=[diode,cap]
        reviewed=evaluate_detections(image,items,model)
        self.assertEqual(reviewed,2)
        self.assertEqual(model.calls,2)
        self.assertEqual(items[0]["label"],"Diyot")
        self.assertTrue(items[0]["review_required"])
        self.assertIn("farklı",items[0]["review_note"])
        self.assertFalse(items[0]["secondary_evidence"]["technician_verified"])
        self.assertEqual(items[0]["secondary_evidence"]["label_family"],"capacitor")
        self.assertEqual(items[1]["label"],"Kondansatör")
        self.assertTrue(items[1]["secondary_evidence"]["agrees_with_detector"])
        self.assertFalse(items[1]["review_required"])

    def test_close_second_model_scores_do_not_trigger_unnecessary_review(self):
        image=Image.new("RGB",(300,250),"white")
        row=labeled([40,50,140,160],"Diyot",.6)
        model=FakeOnnxSession([.20,.19])
        self.assertEqual(evaluate_detections(image,[row],model),1)
        self.assertFalse(row["review_required"])
        self.assertFalse(row["secondary_evidence"]["actionable_disagreement"])
        self.assertEqual(row["label"],"Diyot")

    def test_verified_labels_and_other_components_are_never_touched(self):
        image=Image.new("RGB",(800,600),"white")
        rows=[
            {**labeled([0,0,120,120],"Diyot"),"verified":True},
            labeled([150,100,300,160],"Direnç"),
        ]
        model=FakeOnnxSession([1.,4.])
        self.assertEqual(evaluate_detections(image,rows,model),0)
        self.assertEqual(model.calls,0)
        self.assertFalse(rows[0]["review_required"])

    def test_malformed_model_output_is_not_trusted(self):
        model=FakeOnnxSession([float("nan"),0])
        image=Image.new("RGB",(100,100),"black")
        with self.assertRaisesRegex(SecondaryModelError,"output"):
            score_image_region(model,image,(.5,.5,.4,.4))

    def test_disabled_by_default_has_no_external_api_or_image_read(self):
        with patch.dict("os.environ",{},clear=True):
            result=run_if_approved("/nonexistent.jpg",[])
        self.assertEqual(result["state"],"not_enabled")
        self.assertEqual(result["candidates_reviewed"],0)

    def test_preprocessing_is_consistent_with_training(self):
        image=Image.new("RGB",(400,300),(127,127,127))
        x=preprocess_crop(image,(.5,.5,.2,.2))
        self.assertEqual(x.shape,(1,3,160,160))
        self.assertTrue(x.min()>-5 and x.max()<5)

if __name__=="__main__":
    unittest.main()
