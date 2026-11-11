import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
import download_and_test_model as module

class DownloadValidationTests(unittest.TestCase):
    def test_rejects_lfs_pointer(self):
        pointer=b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\n"
        with tempfile.TemporaryDirectory() as folder:
            with patch("urllib.request.urlopen",return_value=BytesIO(pointer)):
                with self.assertRaises(ValueError):
                    module.download(Path(folder)/"weights.pt")
            self.assertFalse((Path(folder)/"weights.pt").exists())

    def test_rejects_wrong_size(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("urllib.request.urlopen",return_value=BytesIO(b"x"*2048)):
                with self.assertRaisesRegex(ValueError,"size mismatch"):
                    module.download(Path(folder)/"weights.pt")
            self.assertFalse((Path(folder)/"weights.pt").exists())

if __name__=="__main__":
    unittest.main()
