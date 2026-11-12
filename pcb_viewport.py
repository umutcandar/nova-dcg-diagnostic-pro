"""Pixel-accurate image viewport transforms for the NOVA DCG V2 workspace.

Image coordinates always refer to the EXIF-normalized original photo.
Only visible image pixels are rendered, keeping zoom usable on large photos.
"""
from dataclasses import dataclass
import math


@dataclass
class Viewport:
    image_width: int = 1
    image_height: int = 1
    canvas_width: int = 800
    canvas_height: int = 600
    scale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0

    MIN_SCALE = 0.025
    MAX_SCALE = 8.0

    def fit(self, padding=28):
        w = max(1, self.canvas_width - padding * 2)
        h = max(1, self.canvas_height - padding * 2)
        self.scale = min(w / self.image_width, h / self.image_height, self.MAX_SCALE)
        self.offset_x = (self.canvas_width - self.image_width * self.scale) / 2
        self.offset_y = (self.canvas_height - self.image_height * self.scale) / 2
        return self.scale

    def to_canvas(self, x, y):
        return self.offset_x + x * self.scale, self.offset_y + y * self.scale

    def to_image(self, x, y):
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def zoom(self, factor, anchor_x, anchor_y):
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("Invalid zoom factor")
        old_image_x, old_image_y = self.to_image(anchor_x, anchor_y)
        self.scale = min(self.MAX_SCALE, max(self.MIN_SCALE, self.scale * factor))
        self.offset_x = anchor_x - old_image_x * self.scale
        self.offset_y = anchor_y - old_image_y * self.scale
        return self.scale

    def pan(self, dx, dy):
        self.offset_x += dx
        self.offset_y += dy

    def visible_crop(self):
        """Integer source rectangle (left, top, right, bottom), or None."""
        left = max(0, math.floor(-self.offset_x / self.scale))
        top = max(0, math.floor(-self.offset_y / self.scale))
        right = min(self.image_width, math.ceil((self.canvas_width - self.offset_x) / self.scale))
        bottom = min(self.image_height, math.ceil((self.canvas_height - self.offset_y) / self.scale))
        if left >= right or top >= bottom:
            return None
        return left, top, right, bottom

    def find_box(self, boxes, canvas_x, canvas_y):
        x, y = self.to_image(canvas_x, canvas_y)
        found = []
        for index, bounds in enumerate(boxes):
            x1, y1, x2, y2 = bounds
            if x1 <= x <= x2 and y1 <= y <= y2:
                found.append(((x2 - x1) * (y2 - y1), index))
        return min(found)[1] if found else None
