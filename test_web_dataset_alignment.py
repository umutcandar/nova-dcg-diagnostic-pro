"""Regression tests for matching browser EXIF-transposed boxes to training photos."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from prepare_dataset import prepare


class WebDatasetAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make(self, index, *, size=(20, 40), verified=True):
        location = self.base / "source" / f"board{index}"
        location.mkdir(parents=True)
        image = location / "original.jpg"
        exif = Image.Exif()
        exif[274] = 6  # Browser shows 20 x 40 after rotating 40 x 20 raw pixels.
        Image.new("RGB", (40, 20), (20, 110, 120)).save(image, exif=exif)
        annotation = {
            "board_id": f"physical-{index}",
            "image": "original.jpg",
            "technician_verified": verified,
            "image_coordinate_space": "exif_transposed",
            "image_width": size[0],
            "image_height": size[1],
            "coordinate_system": "xyxy_normalized",
            "regions": [{
                "label": "Direnç",
                "bbox_xyxy_normalized": [0.1, 0.1, 0.8, 0.9],
            }]
        }
        (location / "review.json").write_text(json.dumps(annotation), encoding="utf-8")
        return location

    def test_prepared_images_are_oriented_like_browser_boxes(self):
        for i in range(3):
            self.make(i)
        dest = self.base / "output"
        result = prepare(self.base / "source", dest)
        self.assertEqual(result["images"], 3)
        photos = list((dest / "images").rglob("*.jpg"))
        self.assertEqual(len(photos), 3)
        for file in photos:
            with Image.open(file) as img:
                self.assertEqual(img.size, (20, 40))
                self.assertIsNone(img.getexif().get(274))
        self.assertEqual(len(list((dest / "labels").rglob("*.txt"))), 3)

    def test_dimension_mismatch_is_not_silently_trained(self):
        for i in range(3):
            self.make(i, size=(40, 20))
        with self.assertRaisesRegex(ValueError, "yönü veya boyutu"):
            prepare(self.base / "source", self.base / "output")

    def test_unverified_web_annotations_are_not_prepared(self):
        for i in range(3):
            self.make(i, verified=(i != 1))
        with self.assertRaisesRegex(ValueError, "teknisyen onayı"):
            prepare(self.base / "source", self.base / "output")


if __name__ == "__main__":
    unittest.main()
