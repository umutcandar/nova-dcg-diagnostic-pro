"""Real Tk tests of the V2 studio, executed under Xvfb on GitHub Actions."""
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image
from pcb_workspace_v2 import Workspace


@unittest.skipUnless(bool(os.environ.get("DISPLAY")) or sys.platform in ("darwin","win32"),
                     "Requires a graphical display")
class V2WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.photo=Path(self.temp.name)/"pcb.png"
        Image.new("RGB",(900,600),"#184b3b").save(self.photo)
        # The real application's root must provide native drop handlers.
        from tkinterdnd2 import TkinterDnD
        self.root=TkinterDnD.Tk()
        self.root.geometry("1300x800")
        self.app=Workspace(self.root)
        self.root.update()
        # In GUI tests dispatch the mocked inference worker immediately;
        # production keeps the real asynchronous worker thread.
        self.thread_patch = patch("pcb_workspace_v2.threading.Thread",
            side_effect=lambda target, daemon: SimpleNamespace(start=target))
        self.thread_patch.start()
        self.save_patch = patch("pcb_workspace_v2.save_autosave", return_value=self.temp.name)
        self.restore_patch = patch("pcb_workspace_v2.restore_autosave", return_value=0)
        self.save_patch.start()
        self.restore_patch.start()
        self.audit_patch = patch("pcb_workspace_v2.save_local_audit",
            return_value=Path(self.temp.name) / "recognition.json")
        self.audit_mock = self.audit_patch.start()

    def tearDown(self):
        self.app.close()
        self.audit_patch.stop()
        self.restore_patch.stop()
        self.save_patch.stop()
        self.thread_patch.stop()
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

    def test_finder_drop_opens_new_photo_and_runs_detector(self):
        self.assertTrue(self.app.drop_enabled, "Native drag and drop must be initialized")
        dropped = Path(self.temp.name) / "Finder Foto 2026.png"
        Image.new("RGB", (640, 420), "#206b52").save(dropped)
        detections = [{"label":"LED", "source_label":"LED",
                       "confidence":0.81, "bbox_xyxy_pixels":[30, 40, 95, 90]}]
        with patch("pcb_workspace_v2.automatic_detect", return_value=detections):
            outcome = self.app._on_drop(SimpleNamespace(data="{" + str(dropped) + "}"))
            self.wait_for_detection()
        self.assertEqual(outcome, "copy")
        self.assertEqual(Path(self.app.image_path), dropped.resolve())
        self.assertEqual(len(self.app.tasks), 1)
        self.assertIn("Diyot", self.app.mode_text.get())

    def test_invalid_drop_reports_error_without_changing_photo(self):
        with patch("pcb_workspace_v2.automatic_detect", return_value=[]):
            self.app.open_photo(self.photo)
            self.wait_for_detection()
        before = self.app.image_path
        outcome = self.app._on_drop(SimpleNamespace(data="{/tmp/nonexistent PCB.png}"))
        self.assertEqual(outcome, "refuse_drop")
        self.assertEqual(self.app.image_path, before)
        self.assertIn("DOSYA BIRAKMA HATASI", self.app.status.get())

    def test_header_actions_have_readable_dark_theme(self):
        header = self.root.winfo_children()[0]
        labels = [item for item in header.winfo_children()
                  if isinstance(item, tk.Label)]
        controls = [widget for widget in labels if widget.cget("text") == "Fotoğraf değiştir"]
        self.assertEqual(len(controls),1)
        self.assertNotEqual(controls[0].cget("foreground"), controls[0].cget("background"))
        self.assertEqual(controls[0].cget("background"), "#3C86F5")

    def test_detected_candidates_receive_evidence_only_audit(self):
        rows = [
            {"label": "Entegre", "confidence": .44, "bbox_xyxy_pixels": [10, 20, 65, 85]},
            {"label": "LED", "confidence": .42, "bbox_xyxy_pixels": [120, 50, 158, 70]},
        ]
        with patch("pcb_workspace_v2.automatic_detect", return_value=rows):
            self.app.open_photo(self.photo)
            self.wait_for_detection()
        report = self.app.recognition_report
        self.assertEqual(report["detected_candidates"], 2)
        self.assertEqual(report["requires_review"], 2)
        self.assertFalse(report["accuracy_evaluated"])
        self.assertIn("2 düşük güvenli", self.app.image_status.get())
        self.audit_mock.assert_called()

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
