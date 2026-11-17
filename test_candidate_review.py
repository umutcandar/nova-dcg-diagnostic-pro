import unittest
from candidate_review import review_summary, set_candidate_rejected


class CandidateReviewTests(unittest.TestCase):
    def test_manual_false_positive_rejection_is_reversible(self):
        task = {"component": "Diyot"}
        set_candidate_rejected(task)
        self.assertTrue(task["technician_rejected_candidate"])
        set_candidate_rejected(task, False)
        self.assertFalse(task["technician_rejected_candidate"])

    def test_counts_are_manual_decisions_not_accuracy_metrics(self):
        tasks = [
            {"component": "Diyot", "technician_rejected_candidate": True},
            {"component": "Kondansatör", "technician_verified_type": True},
            {"component": "Bilinmiyor", "needs_review": True},
        ]
        result = review_summary(tasks)
        self.assertEqual(result["visible_candidates"], 2)
        self.assertEqual(result["manually_rejected"], 1)
        self.assertEqual(result["technician_verified_types"], 1)
        self.assertEqual(result["unresolved_unknowns"], 1)
        self.assertNotIn("accuracy", result)
        self.assertNotIn("precision", result)

    def test_invalid_rejection_flag_rejected(self):
        with self.assertRaises(ValueError):
            set_candidate_rejected({}, "yes")


if __name__ == "__main__":
    unittest.main()
