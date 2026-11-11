"""Local PCB object detection with full-image and overlapping tile passes.

All boxes are unverified visual hypotheses, not component health or probe advice.
The class mapping is checked against the loaded, trained checkpoint.
"""
import math
from pathlib import Path

from dataset import CLASSES
from source_model import SOURCE_CLASSES, adapt_source_classes, mapped_label


def candidate_regions(width, height):
    """Whole board first, then four overlapping close-up tiles.

    YOLO resizing can erase small through-hole components. Tiles help preserve
    pixel detail but cannot make an unfamiliar model accurate on new boards.
    """
    yield (0, 0, width, height, 960)
    if min(width, height) < 300:
        return
    tile_width = max(192, round(width * 0.62))
    tile_height = max(192, round(height * 0.62))
    if tile_width >= width or tile_height >= height:
        return
    for top in (0, height - tile_height):
        for left in (0, width - tile_width):
            yield (left, top, left + tile_width, top + tile_height, 768)


def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    overlap = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    if not overlap:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return overlap / (area_a + area_b - overlap)


def deduplicate_detections(predictions, threshold=0.40, max_results=250):
    """Keep highest-confidence box for near-identical regions of same class.

    Different classes in the same area remain visible for technician review.
    """
    kept = []
    for item in sorted(predictions, key=lambda p: p["confidence"], reverse=True):
        if any(
            item["source_label"] == current["source_label"]
            and _iou(item["bbox_xyxy_pixels"], current["bbox_xyxy_pixels"]) >= threshold
            for current in kept
        ):
            continue
        kept.append(item)
        if len(kept) >= max_results:
            break
    return sorted(kept, key=lambda p: (p["bbox_xyxy_pixels"][1], p["bbox_xyxy_pixels"][0]))


def detect_components(image_path, weights_path, confidence=0.22):
    """Predict on the whole photo and four overlapping crops.

    Lower confidence increases recall at the expense of false positives.
    Every result remains unverified, with the exact source model class retained.
    """
    from PIL import Image, ImageOps

    image_path = Path(image_path)
    weights_path = Path(weights_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if not weights_path.is_file():
        raise FileNotFoundError(f"Trained weights not found: {weights_path}")
    if not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 < confidence <= 1:
        raise ValueError("Confidence must be a finite number in (0, 1]")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install optional dependency: python -m pip install ultralytics") from exc

    model = YOLO(str(weights_path))
    names = model.names
    class_names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
    if class_names == CLASSES:
        label_adapter = lambda name: name
    elif class_names == SOURCE_CLASSES:
        adapt_source_classes(names)
        label_adapter = mapped_label
    else:
        raise ValueError("Model class order is not the verified NOVA/PCB checkpoint order")

    with Image.open(image_path) as opened:
        board = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = board.size
    predictions = []
    for left, top, right, bottom, imgsz in candidate_regions(width, height):
        region = board.crop((left, top, right, bottom))
        result = model.predict(
            source=region,
            imgsz=imgsz,
            conf=confidence,
            max_det=300,
            verbose=False
        )[0]
        for box in result.boxes:
            class_id = int(box.cls[0])
            name = names[class_id] if isinstance(names, dict) else names[class_id]
            x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
            x1 = max(0.0, min(float(width), x1 + left))
            x2 = max(0.0, min(float(width), x2 + left))
            y1 = max(0.0, min(float(height), y1 + top))
            y2 = max(0.0, min(float(height), y2 + top))
            score = float(box.conf[0])
            if not all(map(math.isfinite, (x1, y1, x2, y2, score))):
                continue
            if x2 <= x1 or y2 <= y1:
                continue
            predictions.append({
                "label": label_adapter(str(name)),
                "source_label": str(name),
                "confidence": score,
                "bbox_xyxy_pixels": [x1, y1, x2, y2],
                "source": "model",
                "verified": False,
            })
    return deduplicate_detections(predictions)


def validate_model_classes(names):
    """Explicitly check class names before interpreting a custom model."""
    actual = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
    if actual != CLASSES:
        raise ValueError("Model classes differ from NOVA dataset classes/order")
    return True
