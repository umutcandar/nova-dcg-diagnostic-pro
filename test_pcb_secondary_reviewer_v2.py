"""Synthetic tests for three-family independent PCB visual review curriculum."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from pcb_secondary_reviewer_v2 import CAP_IDS,DIODE_IDS,OTHERS,CLASSES,choose_dataset,score


class SecondVisionV2Tests(unittest.TestCase):
    def test_secondary_model_has_a_real_other_component_family(self):
        self.assertEqual(CLASSES,("capacitor","diode","other"))
        self.assertEqual(CAP_IDS,(1,6))
        self.assertEqual(DIODE_IDS,(4,22))
        self.assertIn(18,OTHERS)  # resistor
        self.assertIn(11,OTHERS)  # IC
        self.assertNotIn(6,OTHERS)

    def test_source_preserves_rare_zener_and_electrolytic(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for split in ("train","val"):
                (root/"images"/split).mkdir(parents=True)
                (root/"labels"/split).mkdir(parents=True)
                pic=root/"images"/split/"board.png"
                Image.new("RGB",(200,200),"white").save(pic)
                labels=[]
                labels.extend(["1 .5 .5 .2 .2"]*190)
                labels.extend(["6 .5 .5 .2 .2"]*10)
                labels.extend(["4 .5 .5 .2 .2"]*35)
                labels.extend(["22 .5 .5 .2 .2"]*4)
                labels.extend(["18 .5 .5 .2 .2"]*130)
                labels.extend(["11 .5 .5 .2 .2"]*135)
                labels.extend(["8 .5 .5 .2 .2"]*135)
                labels.extend(["9 .5 .5 .2 .2"]*135)
                (root/"labels"/split/"board.txt").write_text("\n".join(labels))
            train,meta=choose_dataset(root,"train")
            self.assertEqual(meta["electrolytic_examples_preserved"],10)
            self.assertEqual(meta["zener_examples_preserved"],4)
            self.assertEqual(meta["sampled_by_family"]["diode"],39)
            self.assertEqual(meta["sampled_by_family"]["other"],380)
            self.assertEqual(meta["sampled_by_family"]["capacitor"],200)
            val,validation=choose_dataset(root,"val")
            self.assertEqual(validation["sampled_by_family"]["other"],128)
            self.assertEqual(validation["sampled_by_family"]["diode"],39)
            self.assertNotEqual(train[0][0],val[0][0])

    def test_macrof1_does_not_hide_failures_in_rare_diode_family(self):
        rows=[
            (Path("a.jpg"),(.5,.5,.2,.2),0,1),
            (Path("b.jpg"),(.5,.5,.2,.2),1,4),
            (Path("c.jpg"),(.5,.5,.2,.2),2,18),
        ]
        result=score([0,1,2],[0,0,2],rows)
        self.assertEqual(result["confusion_matrix"],[[1,0,0],[1,0,0],[0,0,1]])
        self.assertEqual(result["by_family"]["diode"]["recall"],0)
        self.assertLess(result["macro_f1"],.7)
        self.assertEqual(result["source_label_accuracy"]["Diode"]["correct"],0)

if __name__=="__main__":
    unittest.main()
