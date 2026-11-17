"""Training audit tests never download data or run expensive training."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import yaml
from pcb_train_candidate import NAMES, audit_source, create_training_yaml, train_candidate


class TrainingCandidateTests(unittest.TestCase):
    def setUp(self):
        self.workspace=tempfile.TemporaryDirectory()
        self.root=Path(self.workspace.name)
        self.data=self.root/"dataset"
        for split in ("train","val"):
            (self.data/"images"/split).mkdir(parents=True)
            (self.data/"labels"/split).mkdir(parents=True)
        (self.root/"LICENSE-DATASET").write_text(
            "Creative Commons Attribution 4.0 International (CC BY 4.0)", encoding="utf-8")
        (self.data/"data.yaml").write_text(yaml.safe_dump({
            "path":".","train":"images/train","val":"images/val",
            "nc":10,"names":NAMES,
        }),encoding="utf-8")
        Image.new("RGB",(40,40),"red").save(self.data/"images/train/1.jpg")
        Image.new("RGB",(40,40),"blue").save(self.data/"images/val/2.jpg")
        (self.data/"labels/train/1.txt").write_text("1 0.5 0.5 0.3 0.3\n",encoding="utf-8")
        (self.data/"labels/val/2.txt").write_text("2 0.5 0.5 0.2 0.2\n",encoding="utf-8")

    def tearDown(self):
        self.workspace.cleanup()

    def test_source_audit_checks_cc_by_class_order_and_leakage(self):
        x=audit_source(self.root,expected_train=1,expected_val=1)
        self.assertEqual(x["images"]["train"],1)
        self.assertEqual(x["images"]["val"],1)
        self.assertEqual(x["annotations"]["train"]["Capacitor"],1)
        self.assertFalse(x["board_identity_split_verified"])

    def test_identical_photo_in_train_and_val_rejected(self):
        (self.data/"images/val/2.jpg").write_bytes(
            (self.data/"images/train/1.jpg").read_bytes())
        with self.assertRaisesRegex(ValueError,"image leakage"):
            audit_source(self.root,expected_train=1,expected_val=1)

    def test_invalid_source_raises_instead_of_swapping_class_mapping(self):
        yaml_file=self.data/"data.yaml"
        yaml_file.write_text(yaml.safe_dump({"nc":10,"names":NAMES[::-1]}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Unexpected source class order"):
            audit_source(self.root,expected_train=1,expected_val=1)

    def test_invalid_box_is_rejected(self):
        (self.data/"labels/val/2.txt").write_text("2 1.0 0.5 0.5 0.2\n")
        with self.assertRaisesRegex(ValueError,"invalid region"):
            audit_source(self.root,expected_train=1,expected_val=1)

    def test_training_yaml_uses_absolute_source_path(self):
        config=create_training_yaml(self.root,self.root/"out/training.yaml")
        o=yaml.safe_load(config.read_text())
        self.assertEqual(o["names"],NAMES)
        self.assertEqual(o["path"],str(self.data.resolve()))

    def test_hyperparameters_checked_before_executing_any_trainer(self):
        with self.assertRaisesRegex(ValueError,"Epochs"):
            train_candidate(self.root,self.root/"out",epochs=0)
        with self.assertRaisesRegex(ValueError,"Image size"):
            train_candidate(self.root,self.root/"out",imgsz=123)


if __name__=="__main__":
    unittest.main()
