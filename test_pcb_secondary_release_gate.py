"""Second visual AI release gate is deliberately conservative."""
import unittest
from pcb_secondary_release_gate import evaluate


class SecondAIReleaseGateTests(unittest.TestCase):
    def base(self):
        return {
            "auto_corrected_labels":0,
            "approved_for_live_use":False,
            "counts":{
                "target_diode_gt":2,
                "target_capacitor_gt":59,
                "matched_target_boxes":30,
                "base_correct_on_matched":29,
                "actionable_helpful_conflicts":0,
                "actionable_false_alarms_on_correct":9,
            },
        }

    def test_actual_external_class_imbalance_blocks_promotion(self):
        result=evaluate("three_family",self.base())
        self.assertEqual(result["verdict"],"HOLD_NOT_APPROVED")
        self.assertFalse(result["automatic_model_promotion"])
        self.assertEqual(result["actionable_false_alarm_rate"],round(9/29,4))
        self.assertTrue(any("target_diode_gt" in x for x in result["blockers"]))
        self.assertTrue(any("false-alarm" in x for x in result["blockers"]))

    def test_no_automatic_promotion_even_when_synthetic_metrics_are_perfect(self):
        data=self.base()
        data["counts"].update(target_diode_gt=100,target_capacitor_gt=500,
                              matched_target_boxes=300,base_correct_on_matched=295,
                              actionable_helpful_conflicts=12,
                              actionable_false_alarms_on_correct=0)
        report=evaluate("research",data)
        self.assertFalse(report["automatic_model_promotion"])
        self.assertIn("licensing",report["blockers"][-1].lower())

    def test_reject_if_any_hidden_automatic_label_override(self):
        data=self.base()
        data["auto_corrected_labels"]=1
        with self.assertRaisesRegex(ValueError,"Unsafe"):
            evaluate("unsafe",data)

    def test_unsupported_report_status_rejected(self):
        data=self.base()
        data["approved_for_live_use"]=True
        with self.assertRaisesRegex(ValueError,"no live"):
            evaluate("unreviewed_approval",data)

if __name__=="__main__":
    unittest.main()
