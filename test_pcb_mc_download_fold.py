"""Offline smoke tests for real 4TU fold layout, not a 3.77 GB download."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image

from pcb_mc_download_fold import ProbeError, extract_official_fold
from pcb_mc_import import PRESENT_NAMES
from pcb_mc_train import validate_fold


class OfficialPCBMCFoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.zippath=self.root/"small.zip"
        picture=io.BytesIO()
        Image.new("RGB",(12,12),(20,100,40)).save(picture,format="JPEG")
        self.picture=picture.getvalue()

    def tearDown(self):
        self.tmp.cleanup()

    def source_zip(self, bad_manifest=False, bad_coco=False, bad_labels=False):
        counts=80
        names={}
        manifest={"folds":[{"fold":0}]}
        for split in ("train","valid"):
            names[split]=[f"{split}_{n:03d}.jpg" for n in range(counts)]
            manifest["folds"][0]["train_images" if split=="train" else "valid_images"]=list(names[split])
        if bad_manifest:
            manifest["folds"][0]["valid_images"].append("phantom.jpg")
        classes=[{"id":i,"name":name} for i,name in enumerate(PRESENT_NAMES)]
        if bad_coco:
            classes[6]["name"]="Unknown"
        with ZipFile(self.zippath,"w",ZIP_DEFLATED) as z:
            z.writestr("PCB_MC/splits/components_only_splits.json",json.dumps(manifest))
            for split in ("train","valid"):
                base=f"PCB_MC/images/PCB-MC-C/kfold_data/fold_0/{split}/"
                coco={
                    "categories":classes,
                    "images":[{"id":i,"file_name":name,"width":12,"height":12}
                              for i,name in enumerate(names[split])],
                    "annotations":[],
                }
                z.writestr(
                    f"PCB_MC/annotations/PCB-MC-C/components_only_fold0_{split}_annotations.json",
                    json.dumps(coco)
                )
                for name in names[split]:
                    z.writestr(base+"images/"+name,self.picture)
                    cid=("999" if bad_labels else "6") if split=="train" else "4"
                    z.writestr(base+"labels/"+name.replace(".jpg",".txt"),
                               f"{cid} 0.5 0.5 0.3 0.3\n")
        return self.zippath

    def test_fold_import_passes_verified_class_taxonomy_without_full_md5_in_test(self):
        data=self.source_zip()
        output=self.root/"prepared"
        result=extract_official_fold(data,output,full_md5=False)
        self.assertEqual((result["train_count"],result["val_count"]),(80,80))
        self.assertEqual(result["labels_per_split"]["train"]["Electrolytic Capacitor"],80)
        self.assertTrue((output/"images/train/train_000.jpg").exists())
        self.assertEqual(validate_fold(output)["class_order"],list(PRESENT_NAMES))

    def test_manifest_disagreement_refused(self):
        with self.assertRaisesRegex(ProbeError,"manifest"):
            extract_official_fold(self.source_zip(bad_manifest=True),self.root/"out",full_md5=False)

    def test_class_drift_refused(self):
        with self.assertRaisesRegex(ProbeError,"COCO class order"):
            extract_official_fold(self.source_zip(bad_coco=True),self.root/"out",full_md5=False)

    def test_unknown_class_refused(self):
        with self.assertRaisesRegex(ProbeError,"Unrecognised class"):
            extract_official_fold(self.source_zip(bad_labels=True),self.root/"out",full_md5=False)

    def test_non_official_archive_digest_refused(self):
        with self.assertRaisesRegex(ProbeError,"MD5"):
            extract_official_fold(self.source_zip(),self.root/"out",full_md5=True)


if __name__=="__main__":
    unittest.main()
