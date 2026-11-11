import unittest
from tempfile import TemporaryDirectory
from datasheet_catalog import normalize_part_number,save_verified_entry,load_entry,interpret_measurement
class DatasheetCatalogTests(unittest.TestCase):
    def test_roundtrip(self):
        with TemporaryDirectory() as d:
            save_verified_entry(d,"IRF540N","Example Manufacturer","https://example.com/datasheet.pdf")
            data=load_entry(d,"IRF540N")
            self.assertEqual(data["measurement_limits"],None)
            self.assertEqual(interpret_measurement(data,"Diyot (V)",0.5)["status"],"Ek doğrulama gerekli")
    def test_reject_unsafe_name(self):
        with self.assertRaises(ValueError):
            normalize_part_number("../escape")
if __name__=="__main__":
    unittest.main()
