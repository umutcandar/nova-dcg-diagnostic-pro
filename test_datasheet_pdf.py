import unittest
from datasheet_pdf import KEYWORDS,extract_pdf_candidates
class DatasheetPdfTests(unittest.TestCase):
    def test_topics(self):
        self.assertIn("electrical characteristics",KEYWORDS)
    def test_requires_pdf(self):
        with self.assertRaises((ValueError,RuntimeError)):
            extract_pdf_candidates("not-a-file.txt")
if __name__=="__main__":
    unittest.main()
