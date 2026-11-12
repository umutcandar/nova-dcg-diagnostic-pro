import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from train_v2_pipeline import audit_annotations, train_verified


class TrainingAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make_board(self, num, verified=True, label="Direnç", board_id=None):
        folder = self.base / f"board{num}"
        folder.mkdir(parents=True, exist_ok=True)
        image = folder / "board.png"
        Image.new("RGB", (64, 64), (30,100,90)).save(image)
        annotation = {
            "image": "board.png",
            "board_id": board_id or f"device-{num}",
            "technician_verified": verified,
            "coordinate_system": "xyxy_normalized",
            "regions": [{"label":label, "bbox_xyxy_normalized":[.1,.1,.6,.7]}],
        }
        (folder / "annotation.json").write_text(json.dumps(annotation), encoding="utf-8")

    def test_audit_verified_board_groups(self):
        for i in range(3):
            self.make_board(i, label="LED" if i==2 else "Direnç")
        report = audit_annotations(self.base)
        self.assertEqual(report["image_count"], 3)
        self.assertEqual(report["board_count"], 3)
        self.assertEqual(report["labels"]["LED"], 1)
        self.assertTrue(report["warnings"])

    def test_unverified_labels_must_not_train(self):
        for i in range(3):
            self.make_board(i, verified=(i!=2))
        with self.assertRaisesRegex(ValueError, "Teknisyen onayı"):
            audit_annotations(self.base)

    def test_reject_missing_board_diversity(self):
        for i in range(3):
            self.make_board(i, board_id="same-physical-board")
        with self.assertRaisesRegex(ValueError, "3 farklı"):
            audit_annotations(self.base)

    def test_training_refuses_missing_weights(self):
        for i in range(3):
            self.make_board(i)
        with self.assertRaises(FileNotFoundError):
            train_verified(self.base, self.base/"output", self.base/"missing.pt")

    def test_train_options_validate_before_gpu_use(self):
        with self.assertRaises(ValueError):
            train_verified(self.base, self.base/"output", "no.pt", imgsz=123)


if __name__ == "__main__":
    unittest.main()
