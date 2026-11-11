import unittest
from measurement_history import record_measurement, history_text
from fault_review import review_queue

class MeasurementWorkflowTests(unittest.TestCase):
    def test_separate_histories_and_order(self):
        c1={"id":1,"component":"Kondansatör","mode":"Kapasitans (F)"}
        r1={"id":2,"component":"Direnç","mode":"Direnç (Ω)"}
        record_measurement(c1,"10,2","Ek ölçüm gerekli")
        record_measurement(c1,"9.8","Referans dışında")
        record_measurement(r1,"100","Ek ölçüm gerekli")
        self.assertEqual(len(c1["measurement_history"]),2)
        self.assertEqual(len(r1["measurement_history"]),1)
        self.assertEqual(review_queue([r1,c1])[0]["index"],1)
        self.assertIn("10.2",history_text(c1))
    def test_non_finite_rejected(self):
        task={"id":1}
        for reading in ("nan","inf","-inf","hello"):
            with self.subTest(reading=reading):
                with self.assertRaises(ValueError):
                    record_measurement(task,reading,"Ek ölçüm gerekli")
        self.assertNotIn("measurement_history",task)
    def test_unmeasured_and_reference_priorities(self):
        tasks=[{"id":1},{"id":2,"reference_result":{"status":"Referans dışında"}}]
        result=review_queue(tasks)
        self.assertEqual(result[0]["index"],1)
        self.assertEqual(result[1]["priority"],2)
    def test_history_does_not_claim_health(self):
        task={"id":1}
        record_measurement(task,5,"Ek ölçüm gerekli")
        self.assertIn("tek başına sağlamlık kanıtı değildir",review_queue([task])[0]["reason"])
if __name__=="__main__":
    unittest.main()
