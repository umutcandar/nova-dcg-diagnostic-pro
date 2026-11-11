"""Headless GUI smoke test for photo-triggered automatic model analysis."""
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from gui import App


@unittest.skipUnless(
    bool(os.environ.get("DISPLAY")) or sys.platform in ("darwin", "win32"),
    "Requires a graphical display (GitHub's GUI workflow uses xvfb-run)."
)
class AutomaticPhotoGUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.photo_path = Path(self.temp.name) / "sample_board.png"
        Image.new("RGB", (300, 200), "#b5deaa").save(self.photo_path)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)
        self.app.photo = str(self.photo_path)

    def tearDown(self):
        self.root.destroy()
        self.temp.cleanup()

    def pump(self):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            self.root.update()
            if not self.app._analysis_active:
                self.root.after(150, lambda: None)
                self.root.update()
                time.sleep(0.15)
                self.root.update()
                return
            time.sleep(0.02)
        self.fail("Automated image analysis did not finish in 5 seconds")

    def test_detection_marks_photo_and_opens_guide(self):
        suggestions = [
            {"label": "Direnç", "source_label": "Resistor", "confidence": 0.91,
             "bbox_xyxy_pixels": [40, 60, 90, 110]}
        ]
        with patch("gui.automatic_detect", return_value=suggestions), patch.object(self.app, "guided_photo") as guide:
            self.app.start_auto_analysis()
            self.pump()
            self.assertEqual(self.app.auto_detections, suggestions)
            self.assertIsNotNone(self.app.photo_preview_image)
            self.assertIn("1 komponent adayı", self.app.analysis_status.get())
            self.assertTrue(guide.called, "Measurement guide should open automatically")

    def test_errors_are_visible_and_do_not_claim_success(self):
        with patch("gui.automatic_detect", side_effect=RuntimeError("YOLO kurulumu eksik")):
            self.app.start_auto_analysis()
            self.pump()
            self.assertIn("YOLO kurulumu eksik", self.app.analysis_status.get())
            self.assertFalse(self.app.auto_detections)


if __name__ == "__main__":
    unittest.main()
