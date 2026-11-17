"""Synthetic tests for 4TU PCB-MC board-aware COCO conversion, no 3.77GB download."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from pcb_mc_import import PRESENT_NAMES, import_pcb_mc, convert_bbox, load_coco, select_official_fold
from pcb_mc_train import validate_fold, train_fold


class PCBMCCOCOTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.images=self.root/"images"
        self.images.mkdir()
        for name,color in (("pcb_a.png","red"),("pcb_b.png","green"),("pcb_c.png","blue")):
            Image.new("RGB",(200,100),color).save(self.images/name)
        self.coco=self.root/"present_coco.json"
        self.manifest=self.root/"official_splits.json"
        self.source={
            "categories":[{"id":10+i,"name":label} for i,label in enumerate(PRESENT_NAMES)],
            "images":[{"id":i+1,"file_name":fname,"width":200,"height":100}
                      for i,fname in enumerate(("pcb_a.png","pcb_b.png","pcb_c.png"))],
            "annotations":[
                {"id":1,"image_id":1,"category_id":16,"bbox":[40,20,80,30]},
                {"id":2,"image_id":2,"category_id":11,"bbox":[10,10,30,30]},
                {"id":3,"image_id":3,"category_id":14,"bbox":[20,30,40,40]},
            ]
        }
        self.save_data()
        self.save_split({
            "folds":[{"fold":0,"train_images":["pcb_a.png","pcb_b.png"],
                      "valid_images":["pcb_c.png"]}]
        })

    def tearDown(self):
        self.temp.cleanup()

    def save_data(self):
        self.coco.write_text(json.dumps(self.source),encoding="utf-8")

    def save_split(self, data):
        self.manifest.write_text(json.dumps(data),encoding="utf-8")

    def test_source_categories_keep_electrolytic_vs_regular(self):
        output=self.root/"prepared"
        audit=import_pcb_mc(self.images,self.coco,self.manifest,output,link=False)
        self.assertEqual(audit["class_count"],23)
        self.assertTrue(audit["board_identity_split_from_official_manifest"])
        self.assertEqual(audit["source_train_images"],2)
        self.assertEqual(audit["source_val_images"],1)
        # Id 16 means "Electrolytic Capacitor": 16-10 = class index 6
        self.assertIn("6 ",(output/"labels/train/pcb_a.txt").read_text())
        self.assertIn("1 ",(output/"labels/train/pcb_b.txt").read_text())
        self.assertIn("4 ",(output/"labels/val/pcb_c.txt").read_text())
        self.assertIn("Electrolytic Capacitor",(output/"data.yaml").read_text())
        self.assertTrue((output/"images/train/pcb_a.png").exists())

    def separate_official_coco_files(self):
        train=self.root/"fold0_train.json"
        valid=self.root/"fold0_valid.json"
        train_data={
            "categories":self.source["categories"],
            "images":[x for x in self.source["images"] if x["file_name"]!="pcb_c.png"],
            "annotations":[x for x in self.source["annotations"] if x["image_id"] in (1,2)]
        }
        # Valid files can reuse COCO image IDs and annotation IDs from train.
        val_data={
            "categories":self.source["categories"],
            "images":[{"id":1,"file_name":"pcb_c.png","width":200,"height":100}],
            "annotations":[{"id":1,"image_id":1,"category_id":14,"bbox":[20,30,40,40]}],
        }
        train.write_text(json.dumps(train_data),encoding="utf-8")
        valid.write_text(json.dumps(val_data),encoding="utf-8")
        return train,valid

    def test_official_train_and_validation_separate_coco_supported(self):
        train,valid=self.separate_official_coco_files()
        out=self.root/"fold_from_two_coco"
        audit=import_pcb_mc(
            self.images,None,self.manifest,out,link=False,
            coco_train=train,coco_val=valid
        )
        self.assertEqual(audit["source_coco_layout"],"per_fold_train_valid")
        self.assertIn("6 ",(out/"labels/train/pcb_a.txt").read_text())
        self.assertIn("4 ",(out/"labels/val/pcb_c.txt").read_text())
        self.assertEqual(validate_fold(out)["class_order"],list(PRESENT_NAMES))

    def test_fails_closed_if_split_coco_omits_official_photo(self):
        train,valid=self.separate_official_coco_files()
        val=json.loads(valid.read_text())
        val["images"]=[]
        val["annotations"]=[]
        valid.write_text(json.dumps(val))
        with self.assertRaisesRegex(ValueError,"unannotated images"):
            import_pcb_mc(self.images,None,self.manifest,self.root/"bad",
                          coco_train=train,coco_val=valid)

    def test_fails_closed_if_split_coco_includes_wrong_side_photo(self):
        train,valid=self.separate_official_coco_files()
        train_data=json.loads(train.read_text())
        train_data["images"]=train_data["images"][:1]
        train_data["annotations"]=train_data["annotations"][:1]
        train.write_text(json.dumps(train_data))
        with self.assertRaisesRegex(ValueError,"unannotated images"):
            import_pcb_mc(self.images,None,self.manifest,self.root/"bad",
                          coco_train=train,coco_val=valid)

    def test_rejects_both_task_wide_and_split_files(self):
        train,valid=self.separate_official_coco_files()
        with self.assertRaisesRegex(ValueError,"not both"):
            import_pcb_mc(self.images,self.coco,self.manifest,self.root/"bad",
                          coco_train=train,coco_val=valid)

    def test_rejects_only_one_fold_coco(self):
        train,_=self.separate_official_coco_files()
        with self.assertRaisesRegex(ValueError,"BOTH"):
            import_pcb_mc(self.images,None,self.manifest,self.root/"bad",
                          coco_train=train)

    def test_imported_board_aware_fold_is_trainable_without_training_yet(self):
        out=self.root/"prepared"
        import_pcb_mc(self.images,self.coco,self.manifest,out,link=False)
        metadata=validate_fold(out)
        self.assertTrue(metadata["board_identity_split_from_official_manifest"])
        self.assertEqual(metadata["source_val_images"],1)
        with self.assertRaisesRegex(ValueError,"Epochs"):
            train_fold(out,self.root/"trained",epochs=0)

    def test_trainable_audit_refuses_class_order_change(self):
        out=self.root/"prepared"
        import_pcb_mc(self.images,self.coco,self.manifest,out,link=False)
        yaml=out/"data.yaml"
        yaml.write_text(yaml.read_text().replace("Electrolytic Capacitor","Unknown"),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Class names"):
            validate_fold(out)

    def test_same_board_filename_can_not_be_in_two_splits(self):
        self.save_split({"folds":[{"fold":0,"train_images":["pcb_a.png","pcb_b.png"],
                                   "valid_images":["pcb_a.png"]}]})
        with self.assertRaisesRegex(ValueError,"leakage"):
            import_pcb_mc(self.images,self.coco,self.manifest,self.root/"out")

    def test_category_drift_refused(self):
        self.source["categories"][6]["name"]="unverified-object"
        self.save_data()
        with self.assertRaisesRegex(ValueError,"23 present classes"):
            load_coco(self.coco)

    def test_path_traversal_refused(self):
        self.source["images"][0]["file_name"]="../private.png"
        self.save_data()
        with self.assertRaisesRegex(ValueError,"Unsafe source"):
            load_coco(self.coco)

    def test_bounding_box_outside_image_rejected(self):
        self.source["annotations"][0]["bbox"]=[199,10,30,40]
        self.save_data()
        with self.assertRaisesRegex(ValueError,"outside image"):
            load_coco(self.coco)

    def test_valid_bbox_normalization(self):
        normalized=convert_bbox([40,20,80,30],200,100)
        self.assertAlmostEqual(normalized[0],.4)
        self.assertAlmostEqual(normalized[1],.35)
        self.assertAlmostEqual(normalized[2],.4)
        self.assertAlmostEqual(normalized[3],.3)

    def test_unknown_fold_rejected(self):
        with self.assertRaisesRegex(ValueError,"not found"):
            select_official_fold(self.manifest,5,{})

    def test_photo_size_mismatch_rejected(self):
        Image.new("RGB",(20,20),"white").save(self.images/"pcb_a.png")
        with self.assertRaisesRegex(ValueError,"dimensions mismatch"):
            import_pcb_mc(self.images,self.coco,self.manifest,self.root/"out")


if __name__=="__main__":
    unittest.main()
