import unittest
from tempfile import TemporaryDirectory
from service_records import save_job,load_job,list_jobs,safe_job_id

class ServiceRecordsTests(unittest.TestCase):
    def test_roundtrip(self):
        with TemporaryDirectory() as d:
            save_job(d,"JOB_001","LC-20AD","Pump board",[{"point":"F1","value":"open"}])
            self.assertEqual(load_job(d,"JOB_001")["measurements"][0]["point"],"F1")
            self.assertEqual(list_jobs(d)[0]["job_id"],"JOB_001")
    def test_reject_traversal(self):
        for value in ("../escape","a/b",""):
            with self.assertRaises(ValueError):
                safe_job_id(value)
    def test_empty_folder(self):
        with TemporaryDirectory() as d:
            self.assertEqual(list_jobs(d+"/missing"),[])
if __name__=="__main__":
    unittest.main()
