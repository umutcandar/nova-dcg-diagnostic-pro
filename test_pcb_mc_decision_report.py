"""Offline tests for non-production 23-class audit, no model load/download."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from pcb_mc_decision_report import CandidateEvidenceError, review, PRESENT_NAMES


def fixture():
    return {
        "trained": True, "approved_for_live_use": False,
        "source_fold": {
            "full_zip_md5_verified": True,
            "class_order": list(PRESENT_NAMES),
            "board_identity_split_from_official_manifest": True,
            "official_fold": 0,
            "source_train_images": 492, "source_val_images": 123,
            "labels_per_split": {
                "train": {x: 1000 for x in PRESENT_NAMES},
                "val": {x: 100 for x in PRESENT_NAMES},
            }
        },
        "validation": {
            "split": "publisher_official_board_aware_validation",
            "metrics": {
                "metrics/precision(B)": .68,
                "metrics/recall(B)": .03,
                "metrics/mAP50(B)": .025,
                "metrics/mAP50-95(B)": .013,
            },
            "by_class": [{"class": x, "mAP50_95": .01} for x in PRESENT_NAMES],
        },
        "best_checkpoint": {"sha256": "0" * 64},
        "parameters": {"epochs":3,"imgsz":640},
    }


class PCBMCReleaseReviewTests(unittest.TestCase):
    def test_unreleased_candidate_has_no_auto_promotion(self):
        data=fixture()
        data["source_fold"]["labels_per_split"]["train"]["Zener Diode"]=9
        data["source_fold"]["labels_per_split"]["val"]["Zener Diode"]=4
        result=review(data)
        self.assertFalse(result["can_replace_live_21class_detector"])
        self.assertFalse(result["checkpoint_sha256_verified"])
        self.assertEqual(result["trained_classes"],23)
        z=next(x for x in result["priority_capacitor_diode_evidence"] if x["name"]=="Zener Diode")
        self.assertEqual(z["train_objects"],9)
        self.assertEqual(z["validation_objects"],4)
        self.assertEqual(z["research_collection_priority"],"new_verified_board_photos_needed")

    def test_reject_changed_class_names_and_unverified_source(self):
        data=fixture()
        data["source_fold"]["class_order"][5]="Fictional component"
        with self.assertRaisesRegex(CandidateEvidenceError,"class ordering"):
            review(data)
        data=fixture()
        data["source_fold"]["full_zip_md5_verified"]=False
        with self.assertRaisesRegex(CandidateEvidenceError,"checksum"):
            review(data)

    def test_refuse_unverified_or_invalid_metrics(self):
        data=fixture()
        data["validation"]["metrics"]["metrics/recall(B)"]=float("nan")
        with self.assertRaisesRegex(CandidateEvidenceError,"metric"):
            review(data)
        data=fixture()
        del data["validation"]["by_class"][-1]
        with self.assertRaisesRegex(CandidateEvidenceError,"class names"):
            review(data)

    def test_tampered_checkpoint_is_rejected_without_unpickling(self):
        data=fixture()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"dummy.pt"
            p.write_bytes(b"not-a-pickle-load")
            data["best_checkpoint"]["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
            result=review(data,model_file=p)
            self.assertTrue(result["checkpoint_sha256_verified"])
            p.write_bytes(b"changed")
            with self.assertRaisesRegex(CandidateEvidenceError,"SHA256"):
                review(data,model_file=p)


if __name__=="__main__":
    unittest.main()
