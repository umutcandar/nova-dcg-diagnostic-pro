import unittest
from check_planner import next_checks
class CheckPlannerTests(unittest.TestCase):
    def test_short_resistance_caution(self):
        result=next_checks([{"point":"L1","mode":"Direnç (Ω)","value":0.3}])
        self.assertIn("bobin",result[0]["reason"])
    def test_fault_text(self):
        result=next_checks([],"Cihaz açılmıyor")
        self.assertTrue(any("Güç" in x["title"] for x in result))
    def test_no_definitive_verdict(self):
        self.assertTrue(next_checks([{"mode":"Diyot (V)","value":0,"point":"D1"}]))
if __name__=="__main__":
    unittest.main()
