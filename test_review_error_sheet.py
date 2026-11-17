import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from review_error_sheet import create_review_sheet


class ReviewSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.photo = self.base / "board.png"
        Image.new("RGB", (300, 200), (50, 110, 80)).save(self.photo)
        self.report_path = self.base / "report.json"
        self.entry = {
            "board_id": "board-1", "image": str(self.photo), "kind": "false_candidate",
            "actual": None, "predicted": "Kondansatör",
            "bbox_xyxy_pixels": [20, 30, 60, 70], "confidence": .4,
        }
        self.report = {"ground_truth_available": True,
                       "results": [{"threshold": .45, "error_cases": [self.entry]}]}
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_review_sheet_without_network(self):
        out = self.base / "sheets" / "errors.png"
        result = create_review_sheet(self.report_path, out, .45, columns=2)
        self.assertTrue(out.is_file())
        with Image.open(out) as img:
            self.assertEqual(img.size, (520, 220))
        self.assertEqual(result["shown_errors"], 1)

    def test_rejects_unverified_report_or_wrong_threshold(self):
        with self.assertRaisesRegex(ValueError, "eşik"):
            create_review_sheet(self.report_path, self.base/"x.png", .6)
        self.report["ground_truth_available"] = False
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Gerçek etiketli"):
            create_review_sheet(self.report_path, self.base/"y.png", .45)

    def test_refuses_image_path_without_local_file(self):
        self.entry["image"] = str(self.base / "missing.png")
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            create_review_sheet(self.report_path, self.base/"x.png", .45)


if __name__ == "__main__":
    unittest.main()
