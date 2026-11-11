import unittest
from component_library import COMPONENTS,component_info
class ComponentLibraryTests(unittest.TestCase):
    def test_all_have_safety_caution(self):
        for name in COMPONENTS:
            info=component_info(name)
            self.assertTrue(info["checks"])
            self.assertTrue(info["caution"])
    def test_unknown_rejected(self):
        with self.assertRaises(KeyError):
            component_info("Bilinmiyor")
if __name__=="__main__":
    unittest.main()
