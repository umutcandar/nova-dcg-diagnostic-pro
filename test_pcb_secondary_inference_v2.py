"""Offline three-way independent vision reviewer tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from pcb_secondary_inference_v2 import (
    SecondaryModelError,examine,verify_model
)
from pcb_secondary_external_compare import compare


class FakeSession:
    def __init__(self,logits):self.logits=logits
    def get_inputs(self):return [type("Input",(),{"name":"image"})()]
    def run(self,ignore,values):
        import numpy as np
        assert values["image"].shape==(1,3,160,160)
        return [np.asarray([self.logits],dtype="float32")]


class ThirdClassReviewTests(unittest.TestCase):
    def test_other_family_never_auto_deletes_component(self):
        board=Image.new("RGB",(700,500),"white")
        part={
            "label":"Diyot","bbox_xyxy_pixels":[100,100,250,300],
            "review_required":False,"review_note":"","confidence":.7,
            "verified":False,
        }
        count=examine(board,[part],FakeSession([0,1,4]))
        self.assertEqual(count,1)
        self.assertEqual(part["label"],"Diyot")
        self.assertTrue(part["review_required"])
        self.assertIn("başka bir komponent",part["review_note"])
        self.assertEqual(part["secondary_evidence"]["label_family"],"other")
        self.assertFalse(part["secondary_evidence"]["technician_verified"])

    def test_low_margin_other_prediction_is_not_a_hard_review_alarm(self):
        image=Image.new("RGB",(240,200),"white")
        row={"label":"Kondansatör","bbox_xyxy_pixels":[30,30,130,130],
             "review_required":False,"review_note":"","confidence":.7,"verified":False}
        result=examine(image,[row],FakeSession([.30,.20,.35]))
        self.assertEqual(result,1)
        self.assertFalse(row["review_required"])
        self.assertFalse(row["secondary_evidence"]["actionable_disagreement"])
        self.assertEqual(row["label"],"Kondansatör")

    def test_same_family_proposal_stays_unverified(self):
        board=Image.new("RGB",(700,500),"white")
        region={"label":"Kondansatör","bbox_xyxy_pixels":[70,50,250,250],
                "review_required":False,"review_note":"","confidence":.9,
                "verified":False}
        self.assertEqual(examine(board,[region],FakeSession([5,0,0])),1)
        self.assertFalse(region["review_required"])
        self.assertFalse(region["secondary_evidence"]["technician_verified"])
        self.assertEqual(region["label"],"Kondansatör")

    def test_unreleased_artifact_has_verifiable_sha_and_exact_source(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            weight=root/"reviewer_cap_diode_other.onnx"
            weight.write_bytes(b"fake-but-hash-checked")
            report=root/"training_report.json"
            content={
                "schema":"nova-independent-capacitor-diode-other-reviewer-v2",
                "labels":["capacitor","diode","other"],
                "source_audit":{"full_zip_md5_verified":True,
                    "board_identity_split_from_official_manifest":True},
                "approved_for_live_use":False,
                "model":{"file":weight.name,"bytes":weight.stat().st_size,
                         "sha256":hashlib.sha256(weight.read_bytes()).hexdigest()},
            }
            report.write_text(json.dumps(content))
            self.assertEqual(verify_model(report,weight)["labels"][-1],"other")
            weight.write_bytes(b"tampered")
            with self.assertRaisesRegex(SecondaryModelError,"size|SHA256"):
                verify_model(report,weight)

    def test_reviewer_on_real_yolo_geometry_can_report_other_without_mutating(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"dataset/images/val").mkdir(parents=True)
            (root/"dataset/labels/val").mkdir(parents=True)
            photo=root/"dataset/images/val/board.png"
            Image.new("RGB",(160,160),(65,85,115)).save(photo)
            (root/"dataset/labels/val/board.txt").write_text("1 .5 .5 .6 .6\n")
            def predict(_):
                return [{"label":"Diyot","source_label":"diode",
                         "bbox_xyxy_pixels":[32,32,128,128],"confidence":.5}]
            result=compare(root,None,None,predict=predict,
                           session=FakeSession([1,1,5]),reviewer=examine,model_version="v2")
        self.assertEqual(result["counts"]["second_model_other"],1)
        self.assertEqual(result["counts"]["other_on_matched_cap_or_diode"],1)
        self.assertEqual(result["auto_corrected_labels"],0)
        self.assertFalse(result["approved_for_live_use"])

if __name__=="__main__":
    unittest.main()
