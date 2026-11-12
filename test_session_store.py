import tempfile
import unittest
from pathlib import Path
from PIL import Image

from session_store import save_autosave, restore_autosave, autosave_path


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.photo = self.folder / "board.png"
        Image.new("RGB",(200,200),"green").save(self.photo)
        self.storage = self.folder / "private_backup"

    def tearDown(self):
        self.tmp.cleanup()

    def task(self, label="Direnç", bbox=None):
        return {
            "component":label,
            "source_label":label,
            "model_source_label":"Resistor",
            "bbox_xyxy_pixels": bbox or [20,30,50,45],
            "mode":"Direnç (Ω)", "measurement_history":[],
        }

    def test_restore_one_known_box_with_history(self):
        measured = self.task()
        measured["measurement_history"]=[{"value":100,"status":"Ek ölçüm gerekli"}]
        measured["reading"]=100
        measured["technician_verified_type"]=True
        save_autosave(self.photo,[measured],folder=self.storage)
        fresh = self.task(bbox=[21,31,51,46])
        count = restore_autosave(self.photo,[fresh],folder=self.storage)
        self.assertEqual(count,1)
        self.assertEqual(fresh["reading"],100)
        self.assertEqual(len(fresh["measurement_history"]),1)

    def test_does_not_copy_readings_to_unrelated_parts(self):
        measured = self.task()
        measured["reading"]=100
        save_autosave(self.photo,[measured],folder=self.storage)
        different=self.task(bbox=[120,130,150,145])
        self.assertEqual(restore_autosave(self.photo,[different],folder=self.storage),0)
        self.assertNotIn("reading",different)

    def test_new_photo_bytes_invalidate_backup(self):
        a=autosave_path(self.photo,self.storage)
        Image.new("RGB",(220,190),"blue").save(self.photo)
        b=autosave_path(self.photo,self.storage)
        self.assertNotEqual(a,b)

if __name__=="__main__":
    unittest.main()
