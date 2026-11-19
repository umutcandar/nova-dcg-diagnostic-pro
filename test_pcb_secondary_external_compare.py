"""External YOLO-box disagreement test with independent synthetic verified labels."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from pcb_secondary_external_compare import compare


class IndependentPhotoComparisonTests(unittest.TestCase):
    def test_second_visual_model_catches_wrong_diode_label_without_rewriting_it(self):
        class DummyInput:
            name="image"
        class FakeSession:
            def get_inputs(self):return [DummyInput()]
            def run(self,outputs,feeds):
                import numpy as np
                self.last_shape=feeds["image"].shape
                return [np.array([[4.,1.]],dtype="float32")]  # capacitor
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"dataset/images/val").mkdir(parents=True)
            (root/"dataset/labels/val").mkdir(parents=True)
            pic=root/"dataset/images/val/real_pcb.jpg"
            Image.new("RGB",(200,150),(44,55,65)).save(pic)
            (root/"dataset/labels/val/real_pcb.txt").write_text(
                "1 0.5 0.5 0.5 0.5\n",encoding="utf-8"
            )
            def fake_onnx(_):
                return [{"label":"Diyot","bbox_xyxy_pixels":[50,37.5,150,112.5],
                         "confidence":.49,"source_label":"diode",
                         "alternatives":[{"label":"Kondansatör","confidence":.4}]}]
            session=FakeSession()
            output=compare(root,None,None,predict=fake_onnx,session=session)
        self.assertEqual(output["counts"]["target_capacitor_gt"],1)
        self.assertEqual(output["counts"]["secondary_reviewed"],1)
        self.assertEqual(output["counts"]["matched_target_boxes"],1)
        self.assertEqual(output["counts"]["helpful_conflicts"],1)
        self.assertEqual(output["auto_corrected_labels"],0)
        self.assertFalse(output["approved_for_live_use"])
        self.assertEqual(session.last_shape,(1,3,160,160))

    def test_missing_external_annotations_is_never_marked_as_false_positive(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"dataset/images/val").mkdir(parents=True)
            (root/"dataset/labels/val").mkdir(parents=True)
            Image.new("RGB",(120,120),"red").save(root/"dataset/images/val/x.jpg")
            class FakeSession:
                def get_inputs(self):return [type("I",(),{"name":"image"})()]
                def run(self,o,feed):
                    import numpy as np
                    return [np.array([[2.,1.]],dtype="float32")]
            def fake_onnx(_):return [{"label":"Kondansatör",
                                     "bbox_xyxy_pixels":[1,1,25,25],
                                     "confidence":.87}]
            with self.assertRaises(FileNotFoundError):
                compare(root,None,None,predict=fake_onnx,session=FakeSession())

if __name__=="__main__":
    unittest.main()
