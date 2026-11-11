import unittest
from source_model import SOURCE_CLASSES, adapt_source_classes, mapped_label
class SourceModelTests(unittest.TestCase):
    def test_expected_names(self):
        self.assertTrue(adapt_source_classes({i:n for i,n in enumerate(SOURCE_CLASSES)}))
    def test_reject_wrong_order(self):
        with self.assertRaises(ValueError):
            adapt_source_classes(list(reversed(SOURCE_CLASSES)))
    def test_unmapped_preserved(self):
        self.assertEqual(mapped_label("Crystal"),"Kristal")
if __name__=="__main__":
    unittest.main()
