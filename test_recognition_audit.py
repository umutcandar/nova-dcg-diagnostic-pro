"""Headless evidence-based recognition report tests."""
import json
import tempfile
import unittest
from pathlib import Path

from recognition_audit import summarize_detections, save_local_audit


class RecognitionAuditTests(unittest.TestCase):
    @staticmethod
    def det(label, confidence, box):
        return {
            "label": label,
            "confidence": confidence,
            "bbox_xyxy_pixels": box,
        }

    def test_four_low_confidence_detections_not_accuracy(self):
        # Four low-confidence suggestions reflect a real UI pattern,
        # not a hand-annotated ground-truth dataset.
        rows = [
            self.det("Entegre", .44, [20,20,80,60]),
            self.det("Entegre", .22, [130,40,180,100]),
            self.det("Kondansatör", .24, [50,150,75,190]),
            self.det("LED", .42, [200,175,230,195]),
        ]
        report = summarize_detections(rows, (320,240))
        self.assertEqual(report["detected_candidates"], 4)
        self.assertEqual(report["requires_review"], 4)
        self.assertEqual(report["class_counts"]["Entegre"], 2)
        self.assertFalse(report["ground_truth_available"])
        self.assertFalse(report["accuracy_evaluated"])
        self.assertNotIn("accuracy", report)

    def test_empty_predictions_do_not_imply_empty_board(self):
        report = summarize_detections([], (640,480))
        self.assertEqual(report["detected_candidates"], 0)
        self.assertIn("parça olmadığı anlamına gelmez", report["warnings"][0])

    def test_invalid_boxes_and_nonfinite_confidence_ignored(self):
        rows = [
            self.det("Diyot", float("nan"), [1,1,15,15]),
            self.det("Direnç", .97, [10,10,3,19]),
            self.det("LED", .9, [2,2,14,18]),
        ]
        report = summarize_detections(rows, (100,100))
        self.assertEqual(report["detected_candidates"], 1)
        self.assertEqual(len(report["invalid_indices"]), 2)

    def test_audit_saved_locally_without_copying_picture(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pcb.png"
            path.write_bytes(b"imagebytes")
            report = summarize_detections([], (300,200))
            result = save_local_audit(path,report,folder=Path(d)/"private")
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["report"]["detected_candidates"], 0)
            self.assertEqual(payload["photo_filename"], "pcb.png")
            self.assertEqual(len(list((Path(d)/"private").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
