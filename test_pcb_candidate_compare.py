"""Synthetic tests for fair cross-model ONNX evaluation, no downloads."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pcb_candidate_compare import LABEL_MAP, decode_candidate, verify_candidate
from pcb_train_candidate import NAMES, sha256


class CompareCandidateTests(unittest.TestCase):
    def empty(self):
        return np.zeros((1,14,8400),dtype=np.float32)

    def test_capacitor_second_choice_when_model_guesses_diode(self):
        output=self.empty()
        i=100
        output[0,0,i]=300
        output[0,1,i]=280
        output[0,2,i]=100
        output[0,3,i]=60
        output[0,4+2,i]=.6 # diode
        output[0,4+1,i]=.4 # capacitor
        result=decode_candidate(output,640,640,1,0,0)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["label"],"Diyot")
        self.assertEqual(result[0]["alternatives"][1]["label"],"Kondansatör")
        self.assertEqual(result[0]["bbox_xyxy_pixels"],[250.,250.,350.,310.])

    def test_letterbox_coordinates_preserved_and_low_conf_filtered(self):
        output=self.empty()
        output[0,0,100]=300
        output[0,1,100]=220
        output[0,2,100]=50
        output[0,3,100]=70
        output[0,4+1,100]=.8
        output[0,4+2,200]=.01
        result=decode_candidate(output,1280,800,.5,0,120)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["label"],"Kondansatör")
        self.assertEqual(result[0]["bbox_xyxy_pixels"],[550.,130.,650.,270.])

    def test_same_class_duplicates_suppressed(self):
        output=self.empty()
        for i,score in ((100,.87),(200,.47)):
            output[0,0,i]=300
            output[0,1,i]=290
            output[0,2,i]=90
            output[0,3,i]=80
            output[0,4+1,i]=score
        result=decode_candidate(output,640,640,1,0,0)
        self.assertEqual(len(result),1)
        self.assertAlmostEqual(result[0]["confidence"],.87,places=5)

    def test_bad_shape_and_nonfinite_scores_rejected(self):
        with self.assertRaisesRegex(ValueError,"output shape"):
            decode_candidate(np.zeros((1,15,8400)),640,640,1,0,0)
        raw=self.empty()
        raw[0,7,33]=np.inf
        with self.assertRaisesRegex(ValueError,"non-finite"):
            decode_candidate(raw,640,640,1,0,0)

    def test_training_report_sha_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            filename=root/"candidate10.onnx"
            filename.write_bytes(b"dummy ONNX bytes")
            report={
                "trained":True, "approved_for_live_use":False,
                "source_audit":{
                    "pinned_source_sha":"0d7ae7310fa607389779b6132285336ad73e96e1",
                    "annotations":{"train":{label:1 for label in NAMES}}
                },
                "export":{
                    "file":"candidate10.onnx",
                    "sha256":sha256(filename),
                    "bytes":filename.stat().st_size,
                },
            }
            (root/"training_report.json").write_text(json.dumps(report))
            actual,_=verify_candidate(root)
            self.assertEqual(actual,filename)
            filename.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"digest"):
                verify_candidate(root)
            filename.write_bytes(b"dummy ONNX bytes")
            report["approved_for_live_use"]=True
            (root/"training_report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"non-production"):
                verify_candidate(root)

    def test_all_source_ids_explicitly_mapped_not_silently_conflated(self):
        self.assertEqual(set(LABEL_MAP),set(range(len(NAMES))))
        self.assertEqual(LABEL_MAP[1],"Kondansatör")
        self.assertEqual(LABEL_MAP[9],"Test noktası")
        self.assertNotEqual(LABEL_MAP[7],LABEL_MAP[5])


if __name__=="__main__":
    unittest.main()
