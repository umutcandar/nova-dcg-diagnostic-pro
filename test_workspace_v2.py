"""Real Tk tests of the V2 studio, executed under Xvfb on GitHub Actions."""
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pcb_workspace_v2 import Workspace


@unittest.skipUnless(bool(os.environ.get("DISPLAY")) or sys.platform in ("darwin","win32"),
                     "Requires a graphical display")
class V2WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.photo=Path(self.temp.name)/"pcb.png"
        Image.new("RGB",(900,600),"#184b3b").save(self.photo)
        self.root=tk.Tk()
        self.root.geometry("1300x800")
        self.app=Workspace(self.root)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def wait_for_detection(self,timeout=5):
        limit=time.monotonic()+timeout
        while time.monotonic()<limit:
            self.root.update()
            if not self.app._busy:
                return
            time.sleep(.035)
        self.fail("Detector did not return")

    def test_auto_scan_selection_zoom_pan_and_fluke(self):
        items=[
            {"label":"Direnç","source_label":"Resistor","confidence":.90,
             "bbox_xyxy_pixels":[30,40,95,80]},
            {"label":"Kondansatör","source_label":"Capacitor","confidence":.78,
             "bbox_xyxy_pixels":[200,220,260,275]},
        ]
        with patch("pcb_workspace_v2.automatic_detect",return_value=items):
            self.assertTrue(self.app.open_photo(self.photo))
            self.wait_for_detection()
        self.assertEqual(len(self.app.tasks),2)
        self.assertEqual(self.app.mode_text.get(),"Ω")
        self.app.select_index(1)
        self.assertIn("Kapasitans",self.app.mode_text.get())
        before=self.app.viewport.scale
        self.app.zoom_center(1.25)
        self.assertGreater(self.app.viewport.scale,before)
        self.app.viewport.pan(15,12)
        self.app.fit_image()
        self.app.select_index(0)
        self.app.reading.set("25,4")
        self.app.save_measurement()
        self.assertEqual(len(self.app.tasks[0]["measurement_history"]),1)
        self.assertIn("kaydedildi",self.app.measure_result.get())

    def test_photo_replace_and_visible_error(self):
        with patch("pcb_workspace_v2.automatic_detect",side_effect=RuntimeError("Model indirilemedi")):
            self.assertTrue(self.app.open_photo(self.photo))
            self.wait_for_detection()
        self.assertIn("Model indirilemedi",self.app.image_status.get())
        self.assertEqual(len(self.app.tasks),0)
        newer=Path(self.temp.name)/"new.png"
        Image.new("RGB",(420,420),"#785433").save(newer)
        with patch("pcb_workspace_v2.automatic_detect",return_value=[]):
            self.assertTrue(self.app.open_photo(newer))
            self.wait_for_detection()
        self.assertEqual(self.app.image.size,(420,420))
        self.assertEqual(len(self.app.tasks),0)

    def test_reference_requires_verified_values(self):
        items=[{"label":"Direnç","confidence":.9,"bbox_xyxy_pixels":[15,15,75,50]}]
        with patch("pcb_workspace_v2.automatic_detect",return_value=items):
            self.app.open_photo(self.photo)
            self.wait_for_detection()
        self.app.nominal.set("100")
        self.app.tolerance.set("5")
        self.app.unit.set("Ω")
        self.app.refresh_guide()
        self.assertNotIn("95",self.app.expected_text.get())
        self.app.verified_nominal.set(True)
        self.app.refresh_guide()
        self.assertIn("95",self.app.expected_text.get())
        self.assertIn("105",self.app.expected_text.get())
if __name__=="__main__":
    unittest.main()
