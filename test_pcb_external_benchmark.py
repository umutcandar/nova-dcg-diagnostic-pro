"""Offline independent benchmark contract tests; no public data downloaded."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from pcb_external_benchmark import parse_labels, match_detections, benchmark, SURE_CLASS_MAP


class ExternalBenchmarkTests(unittest.TestCase):
    def test_ambiguous_taxonomy_is_never_counted_as_truth(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"a.txt"
            path.write_text("1 0.5 0.5 0.4 0.4\n6 0.2 0.2 0.1 0.1\n7 0.6 0.6 0.1 0.1\n8 0.6 0.6 0.1 0.1\n9 0.6 0.6 0.1 0.1\n", encoding="utf-8")
            labels,ignored=parse_labels(path,100,100)
        self.assertEqual([x["class"] for x in labels],["Kondansatör"])
        self.assertEqual(ignored,4)
        self.assertNotIn(6,SURE_CLASS_MAP)
        self.assertNotIn(7,SURE_CLASS_MAP)

    def test_bad_annotations_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"a.txt"
            path.write_text("1 0.99 0.5 0.5 0.1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"invalid source annotation"):
                parse_labels(path,100,100)

    def test_recognizes_capacitor_as_second_guess_without_claiming_top1_correct(self):
        truth=[{"class":"Kondansatör","box":[10,12,30,45]}]
        guesses=[{
            "label":"Diyot","bbox_xyxy_pixels":[9,11,31,47],"confidence":.48,
            "alternatives":[{"label":"Diyot","confidence":.48},
                            {"label":"Kondansatör","confidence":.38}]
        }]
        result=match_detections(truth,guesses)
        self.assertEqual(len(result),1)
        self.assertFalse(result[0]["correct_class"])
        self.assertTrue(result[0]["in_top_three"])

    def test_duplicate_predictions_can_not_count_one_target_twice(self):
        truth=[{"class":"Direnç","box":[0,0,20,20]}]
        guesses=[{"label":"Direnç","bbox_xyxy_pixels":[0,0,20,20]},
                 {"label":"Direnç","bbox_xyxy_pixels":[1,1,20,20]}]
        self.assertEqual(len(match_detections(truth,guesses)),1)

    def test_end_to_end_fake_detector_reports_bounded_label_recall(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"dataset/images/val").mkdir(parents=True)
            (root/"dataset/labels/val").mkdir(parents=True)
            Image.new("RGB",(100,80),"red").save(root/"dataset/images/val/board.jpg")
            (root/"dataset/labels/val/board.txt").write_text(
                "1 0.5 0.5 0.2 0.4\n2 0.1 0.1 0.1 0.1\n",encoding="utf-8")
            def fake(_):
                return [{"label":"Kondansatör","bbox_xyxy_pixels":[40,24,60,56],
                         "alternatives":[{"label":"Kondansatör"}]}]
            report=benchmark(root,predict=fake)
        self.assertEqual(report["counts"]["ground_truth"],2)
        self.assertEqual(report["counts"]["matched_boxes"],1)
        self.assertEqual(report["counts"]["correct_class"],1)
        self.assertEqual(report["correct_label_recall"],.5)
        self.assertIsNone(report["classes"]["Direnç"]["correct_class_recall_at_iou_0_5"])


if __name__=="__main__":
    unittest.main()
