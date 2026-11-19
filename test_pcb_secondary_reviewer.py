"""Offline tests for standalone capacitor-vs-diode visual reviewer data contract."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from pcb_secondary_reviewer import (
    CLASS_NAMES, TARGET_GROUPS, collect_records, crop_region, parse_box_label,
    precache_crops, precision_recall_f1_counts, sha256,
)


class SecondVisualAIDataTests(unittest.TestCase):
    def test_only_real_capacitor_and_diode_families_are_comparable(self):
        self.assertEqual(TARGET_GROUPS,{"capacitor":(1,6),"diode":(4,22)})
        self.assertEqual(CLASS_NAMES,("capacitor","diode"))
        self.assertEqual(parse_box_label("6 0.5 0.5 .2 .4","test")[0],6)
        self.assertEqual(parse_box_label("22 0.5 0.5 .2 .4","test")[0],22)
        with self.assertRaisesRegex(ValueError,"5-column"):
            parse_box_label("4 .2 .2 .7 .5 .7 .7","segmentation")

    def test_normalized_geometry_and_context_preserves_center(self):
        board=Image.new("RGB",(400,200),"white")
        crop=crop_region(board,(.5,.5,.25,.5),side=160)
        self.assertEqual(crop.size,(160,160))
        self.assertEqual(crop.getpixel((80,80)),(255,255,255))

    def test_bad_polygon_crop_unknown_class_rejected(self):
        with self.assertRaises(ValueError):
            parse_box_label("99 .5 .5 .2 .1","unknown")
        with self.assertRaises(ValueError):
            parse_box_label("1 1.2 .5 .2 .1","outside")
        with self.assertRaises(ValueError):
            parse_box_label("1 nan .5 .2 .1","nan")

    def test_macro_f1_detects_diode_miss_despite_many_capacitor_hits(self):
        gt=[0]*100+[1]*20
        predicted=[0]*120
        metrics=precision_recall_f1_counts(gt,predicted)
        self.assertEqual(metrics["by_class"]["diode"]["recall"],0)
        self.assertLess(metrics["macro_f1"],.50)
        self.assertEqual(metrics["by_class"]["diode"]["fn"],20)

    def test_cropping_cache_only_saves_small_local_image_snippets(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"board.png"
            Image.new("RGB",(500,300),(40,50,60)).save(p)
            records=[
                (p,(.25,.5,.2,.2),0,1),
                (p,(.75,.5,.1,.3),1,4),
            ]
            cache=precache_crops(records,Path(tmp)/"cached")
            self.assertEqual(len(cache),2)
            for cut,label,source in cache:
                with Image.open(cut) as im:
                    self.assertEqual(im.size,(160,160))
            self.assertEqual([x[1] for x in cache],[0,1])

    def test_read_only_independent_splits_and_class_sampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for split in ("train","val"):
                (root/"images"/split).mkdir(parents=True)
                (root/"labels"/split).mkdir(parents=True)
                pic=root/"images"/split/"board.png"
                Image.new("RGB",(200,200),(30,20,10)).save(pic)
                labels=(["1 0.5 0.5 0.2 0.2"]*140+
                        ["6 0.5 0.5 0.2 0.2"]*3+
                        ["4 0.5 0.5 0.2 0.2"]*34+
                        ["22 0.5 0.5 0.2 0.2"]*2)
                (root/"labels"/split/"board.txt").write_text("\n".join(labels))
            train,summary=collect_records(root,"train",limit_cap=110,seed=10)
            val,vsummary=collect_records(root,"val",limit_cap=100,seed=10)
            self.assertEqual(summary["sampled_capacitors"],110)
            self.assertEqual(summary["sampled_diodes"],36)
            self.assertEqual(vsummary["sampled_diodes"],36)
            self.assertEqual(len(train),146)
            self.assertEqual(len(val),136)
            self.assertNotEqual(train[0][0],val[0][0])

if __name__=="__main__":
    unittest.main()
