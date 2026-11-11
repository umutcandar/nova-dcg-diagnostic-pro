"""Automated detector control tests (no network and no model needed)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import auto_detector


class AutoDetectorTests(unittest.TestCase):
    def test_missing_image_rejected(self):
        with self.assertRaises(auto_detector.DetectorSetupError):
            auto_detector.automatic_detect("/not/a/real/board_photo_91831.png")

    def test_missing_dependency_actionable(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "board.png"
            image.write_bytes(b"example")
            with patch("auto_detector.importlib.util.find_spec", return_value=None):
                with self.assertRaisesRegex(auto_detector.DetectorSetupError, "requirements.txt"):
                    auto_detector.automatic_detect(image)

    def test_previously_verified_model_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.pt"
            path.write_bytes(b"known checkpoint for test")
            with patch.object(auto_detector, "verify_weights", return_value=True):
                with patch.object(auto_detector, "download") as downloader:
                    self.assertEqual(auto_detector.ensure_weights(path), path)
                    downloader.assert_not_called()

    def test_invalid_existing_checkpoint_not_executed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.pt"
            path.write_bytes(b"not weights")
            with self.assertRaisesRegex(auto_detector.DetectorSetupError, "doğrulanamadı"):
                auto_detector.ensure_weights(path)

    def test_inference_only_after_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "board.png"
            image.write_bytes(b"example")
            with patch("auto_detector.importlib.util.find_spec", return_value=object()):
                with patch.object(auto_detector, "ensure_weights", return_value=Path("model.pt")):
                    import sys
                    import types
                    fake_module = types.ModuleType("model_inference")
                    fake_module.detect_components = lambda image_path, weights: [{"label": "Direnç", "bbox_xyxy_pixels": [1,2,10,20]}]
                    with patch.dict(sys.modules, {"model_inference": fake_module}):
                        result = auto_detector.automatic_detect(image)
            self.assertEqual(result[0]["label"], "Direnç")

if __name__ == "__main__":
    unittest.main()
