import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from preflight import check_syntax, FILES

class PreflightTests(unittest.TestCase):
    def test_syntax_checker_flags_bad_code(self):
        with TemporaryDirectory() as directory:
            for name in FILES:
                (Path(directory)/name).write_text("x = 1\n",encoding="utf-8")
            (Path(directory)/"gui.py").write_text("def broken(:\n",encoding="utf-8")
            results=check_syntax(directory)
            errors=[x["file"] for x in results if x["status"]=="error"]
            self.assertEqual(errors,["gui.py"])

if __name__=="__main__":
    unittest.main()
