"""Synthetic tests for 4TU PCB-MC board-aware COCO conversion, no 3.77GB download."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from pcb_mc_import import PRESENT_NAMES, import_pcb_mc, convert_bbox, load_coco, select_official_fold


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
