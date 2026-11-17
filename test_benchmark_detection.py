"""Offline benchmark contracts; artificial fixtures test math, not real accuracy."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from benchmark_detection import run_benchmark, load_verified_records, score_predictions


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.annotations = self.base / "annotations"
        self.predictions = self.base / "predictions"
        self.holdout = self.base / "heldout.txt"
        self.holdout.write_text("physical-a\nphysical-b\n", encoding="utf-8")
        self._board("a", "physical-a",
                    [("Kondansatör", [0.1, 0.1, 0.3, 0.3]),
                     ("Diyot", [0.5, 0.5, 0.7, 0.7])],
                    [("Kondansatör", .9, [10, 10, 30, 30]),
                     ("Kondansatör", .6, [50, 50, 70, 70]),
                     ("Diyot", .25, [80, 5, 95, 18])])
        self._board("b", "physical-b",
                    [("Diyot", [0.1, 0.1, 0.4, 0.4])],
                    [("Diyot", .8, [10, 10, 40, 40])])

    def tearDown(self):
        self.tmp.cleanup()

    def _board(self, name, board_id, truths, guesses, *, complete=True, verified=True):
        af = self.annotations / name
        pf = self.predictions / name
        af.mkdir(parents=True, exist_ok=True)
        pf.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100,100), "#187a5e").save(af / "pcb.png")
        annotation = {
            "image": "pcb.png", "image_width": 100, "image_height": 100,
            "board_id": board_id, "coordinate_system": "xyxy_normalized",
            "technician_verified": verified, "annotation_complete": complete,
            "regions": [{"label": label, "bbox_xyxy_normalized": box}
                        for label, box in truths],
        }
        (af / "board.json").write_text(json.dumps(annotation, ensure_ascii=False), encoding="utf-8")
        preds = [{"label": label, "confidence": score, "bbox_xyxy_pixels": box}
                 for label, score, box in guesses]
        (pf / "board.predictions.json").write_text(json.dumps(preds, ensure_ascii=False), encoding="utf-8")

    def run_report(self):
        return run_benchmark(self.annotations, self.holdout, predictions_dir=self.predictions,
                             thresholds=(.22,.7))

    def test_counts_false_positive_and_diodes_mislabeled_as_capacitors(self):
        report = self.run_report()
        low, high = report["results"]
        self.assertEqual(low["gt_components"], 3)
        self.assertEqual(low["predicted_candidates"], 4)
        self.assertEqual(low["matched_locations"], 3)
        self.assertEqual(low["correct_classes"], 2)
        self.assertEqual(low["false_positive_candidates"], 1)
        self.assertEqual(low["diode_as_capacitor"], 1)
        self.assertEqual(low["capacitor_as_diode"], 0)
        self.assertEqual(low["classification_errors"], 1)
        self.assertEqual(low["candidate_precision"], .75)
        self.assertEqual(low["class_recall"], .6667)
        self.assertEqual(high["false_positive_candidates"], 0)
        self.assertEqual(high["missed_components"], 1)
        self.assertEqual(low["board_count"], 2)
        self.assertTrue(report["ground_truth_available"])

    def test_rejects_incomplete_annotations_before_reporting_precision(self):
        self._board("b", "physical-b", [("Diyot", [.1,.1,.4,.4])],
                    [("Diyot", .8, [10,10,40,40])], complete=False)
        with self.assertRaisesRegex(ValueError, "Tüm parçalar"):
            self.run_report()

    def test_rejects_unverified_annotations(self):
        self._board("a", "physical-a", [("Diyot", [.1,.1,.4,.4])],
                    [("Diyot", .8, [10,10,40,40])], verified=False)
        with self.assertRaisesRegex(ValueError, "Teknisyen onayı"):
            self.run_report()

    def test_rejects_missing_holdout_board(self):
        self.holdout.write_text("never-seen-board\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bulunamadı"):
            self.run_report()

    def test_rejects_wrong_photo_dimensions_and_unknown_ground_truth(self):
        p = self.annotations / "a" / "board.json"
        obj = json.loads(p.read_text(encoding="utf-8"))
        obj["image_width"] = 101
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "boyutu"):
            self.run_report()
        obj["image_width"] = 100
        obj["regions"][0]["label"] = "Bilinmiyor"
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Bilinmiyor"):
            self.run_report()

    def test_predictions_validation(self):
        p = self.predictions / "a" / "board.predictions.json"
        rows = json.loads(p.read_text(encoding="utf-8"))
        rows[0]["confidence"] = float("nan")
        p.write_text(json.dumps(rows), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "güveni"):
            self.run_report()

    def test_empty_predictions_distinguishes_absent_measurements(self):
        records = [{"board_id": "a", "gt": [], "predictions": []}]
        result = score_predictions(records)
        self.assertIsNone(result["candidate_precision"])
        self.assertIsNone(result["candidate_recall"])


if __name__ == "__main__":
    unittest.main()
