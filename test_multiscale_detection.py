"""Offline regression tests for multiscale PCB detection and source labels."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from detection_review import review_detections
from guided_measurement import measurement_plan
from model_inference import candidate_regions, deduplicate_detections, detect_components
from source_model import SOURCE_CLASSES


class DetectionTests(unittest.TestCase):
    def test_overlapping_regions_cover_small_parts(self):
        regions = list(candidate_regions(1200, 800))
        self.assertEqual(len(regions), 5)
        self.assertEqual(regions[0][:4], (0, 0, 1200, 800))
        self.assertIn((0, 0, 744, 496, 768), regions)
        self.assertIn((456, 304, 1200, 800, 768), regions)

    def test_near_identical_same_class_deduplicated(self):
        base = {"label":"Direnç", "source_label":"Resistor", "confidence":.90,
                "bbox_xyxy_pixels":[10,10,60,30]}
        weaker = dict(base, confidence=.45, bbox_xyxy_pixels=[12,11,62,31])
        different = dict(base, source_label="Capacitor", label="Kondansatör")
        result = deduplicate_detections([weaker, different, base])
        self.assertEqual(len(result), 2)
        self.assertEqual(sorted(x["source_label"] for x in result), ["Capacitor", "Resistor"])

    def test_capacitor_diode_collision_becomes_one_unverified_candidate(self):
        cap = {"label": "Kondansatör", "source_label": "Capacitor", "confidence": .78,
               "bbox_xyxy_pixels": [10, 10, 60, 40]}
        diode = {"label": "Diyot", "source_label": "Diode", "confidence": .72,
                 "bbox_xyxy_pixels": [11, 10, 61, 40]}
        result = deduplicate_detections([cap, diode])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "Bilinmiyor")
        self.assertEqual(result[0]["candidate_labels"], ["Kondansatör", "Diyot"])
        self.assertFalse(result[0]["verified"])
        review = review_detections(result)
        self.assertIn("belirsiz", review[0]["display_label"])
        self.assertIn("çakışması", review[0]["review_note"])
        task = measurement_plan(review)[0]
        self.assertEqual(task["component"], "Bilinmiyor")
        self.assertEqual(task["mode"], "Doğrulama gerekli")

    def test_separated_capacitor_diode_and_other_class_overlap_remain_visible(self):
        cap = {"label": "Kondansatör", "source_label": "Capacitor", "confidence": .89,
               "bbox_xyxy_pixels": [10, 10, 30, 40]}
        diode = {"label": "Diyot", "source_label": "Diode", "confidence": .74,
                 "bbox_xyxy_pixels": [50, 50, 80, 70]}
        result = deduplicate_detections([cap, diode])
        self.assertEqual(len(result), 2)
        resistor = {"label": "Direnç", "source_label": "Resistor", "confidence": .8,
                    "bbox_xyxy_pixels": [10, 10, 30, 40]}
        self.assertEqual(len(deduplicate_detections([cap, resistor])), 2)

    def test_unknown_source_class_displayed_without_invented_measurements(self):
        detection = {
            "label": "Diğer: Proprietary", "source_label": "Proprietary",
            "confidence": .36, "bbox_xyxy_pixels": [2, 4, 40, 60]
        }
        task = measurement_plan(review_detections([detection]))[0]
        self.assertEqual(task["component"], "Bilinmiyor")
        self.assertEqual(task["source_label"], "Proprietary")

    def test_predicts_full_image_and_four_tiles(self):
        class Box:
            cls = [3]
            conf = [.70]
            xyxy = [types.SimpleNamespace(tolist=lambda: [12.0, 12.0, 50.0, 40.0])]

        class FakeYOLO:
            instances = []
            def __init__(self, weights):
                self.names = {i: name for i, name in enumerate(SOURCE_CLASSES)}
                self.calls = []
                FakeYOLO.instances.append(self)
            def predict(self, **kwargs):
                self.calls.append(kwargs)
                return [types.SimpleNamespace(boxes=[Box()])]

        module = types.ModuleType("ultralytics")
        module.YOLO = FakeYOLO
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "board.png"
            weights = Path(temp) / "weights.pt"
            Image.new("RGB", (900, 600), "green").save(image)
            weights.write_bytes(b"dummy weights for offline test")
            with patch.dict(sys.modules, {"ultralytics":module}):
                detections = detect_components(image, weights)
        self.assertEqual(len(FakeYOLO.instances[0].calls), 5)
        self.assertGreaterEqual(len(detections), 2)
        self.assertTrue(all(item["label"] == "LED" for item in detections))
        self.assertTrue(all(not item["verified"] for item in detections))
        self.assertTrue(all(
            0 <= d["bbox_xyxy_pixels"][0] < d["bbox_xyxy_pixels"][2] <= 900
            and 0 <= d["bbox_xyxy_pixels"][1] < d["bbox_xyxy_pixels"][3] <= 600
            for d in detections
        ))


if __name__ == "__main__":
    unittest.main()
