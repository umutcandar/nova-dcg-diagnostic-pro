"""Tests for Finder-style Tcl photo drops, including paths containing spaces."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from photo_drop import select_dropped_photo, decode_drop_file


class PhotoDropTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.jpg = self.folder / "PCB test board 01.JPG"
        self.jpg.write_bytes(b"placeholder")
        self.png = self.folder / "second.png"
        self.png.write_bytes(b"placeholder")
        self.text = self.folder / "notes.txt"
        self.text.write_text("not an image")
        self.tcl = tk.Tcl()

    def tearDown(self):
        self.tmp.cleanup()

    def test_path_with_spaces_in_tcl_braces(self):
        result = select_dropped_photo("{" + str(self.jpg) + "}", self.tcl.splitlist)
        self.assertEqual(result, str(self.jpg.resolve()))

    def test_multiple_files_find_first_supported_photo(self):
        payload = self.tcl.call("list", str(self.text), str(self.png))
        self.assertEqual(select_dropped_photo(payload, self.tcl.splitlist), str(self.png.resolve()))

    def test_encoded_file_url(self):
        url = self.jpg.resolve().as_uri()
        self.assertEqual(decode_drop_file(url), str(self.jpg.resolve()))

    def test_reject_remote_urls_and_missing_files(self):
        self.assertIsNone(decode_drop_file("https://example.org/picture.png"))
        self.assertIsNone(decode_drop_file("file://other-host/my.png"))
        self.assertIsNone(decode_drop_file(str(self.folder / "missing.png")))

    def test_reject_nonimages(self):
        with self.assertRaisesRegex(ValueError, "fotoğraf"):
            select_dropped_photo("{" + str(self.text) + "}", self.tcl.splitlist)


if __name__ == "__main__":
    unittest.main()
