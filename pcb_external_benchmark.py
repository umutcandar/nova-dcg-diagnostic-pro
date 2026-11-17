"""NOVA DCG: independently audit the current 21-class detector on third-party PCB photos.

Dataset: wangshnegqi/pcb-component-detection-dataset-yolo, CC BY 4.0, pinned
commit 0d7ae7310fa607389779b6132285336ad73e96e1 (NOT the base model data).
This small split is an exploratory sanity check, NOT validated board-disjoint QA.

Only six directly interchangeable classes are evaluated. "Header" is NOT
assumed to equal "connector", "Crystal" not "clock", Debug/TP not "pads",
and Switch/Button not only "switch". This prevents false benchmark inflation.
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path
from PIL import Image

from web_onnx_detector import automatic_detect, EXPECTED_SHA256

# Source YOLO ID -> model English source class and Turkish UI label.
# Uncertain mappings 6,7,8,9 are intentionally excluded.
SURE_CLASS_MAP = {
    0: ("resistor", "Direnç"),
    1: ("capacitor", "Kondansatör"),
    2: ("diode", "Diyot"),
    3: ("led", "LED"),
    4: ("ic", "Entegre"),
    5: ("connector", "Konnektör"),
}
SOURCE_NAMES = (
    "Resistor", "Capacitor", "Diode", "LED", "IC", "Connector",
    "Switch/Button", "Header", "Crystal", "Debug/TP",
)
SOURCE_REPOSITORY = "https://github.com/wangshnegqi/pcb-component-detection-dataset-yolo"
SOURCE_COMMIT = "0d7ae7310fa607389779b6132285336ad73e96e1"


def box_iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    overlap = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    denom = area_a + area_b - overlap
    return overlap / denom if denom > 0 else 0.0


def parse_labels(path, width, height):
    """Read only labeled classes with unambiguous correspondence."""
    records = []
    ignored = 0
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 5:
            raise ValueError(f"{path}:{n} expected YOLO 5-column label")
        try:
            class_id = int(fields[0])
            cx, cy, w, h = [float(x) for x in fields[1:]]
        except ValueError as exc:
            raise ValueError(f"{path}:{n} bad value") from exc
        if class_id not in range(len(SOURCE_NAMES)) or not all(
            math.isfinite(value) for value in (cx, cy, w, h)
        ) or not (0 < w <= 1 and 0 < h <= 1 and
                  0 <= cx - w / 2 < cx + w / 2 <= 1 and
                  0 <= cy - h / 2 < cy + h / 2 <= 1):
            raise ValueError(f"{path}:{n} invalid source annotation")
        if class_id not in SURE_CLASS_MAP:
            ignored += 1
            continue
        records.append({
            "class": SURE_CLASS_MAP[class_id][1],
            "box": [
                (cx - w / 2) * width, (cy - h / 2) * height,
                (cx + w / 2) * width, (cy + h / 2) * height,
            ],
        })
    return records, ignored


def match_detections(truth, predicted, iou_threshold=0.5):
    """Class-agnostic geometric assignment, then independently score labels."""
    possible = []
    for ti, target in enumerate(truth):
        for pi, prediction in enumerate(predicted):
            box = prediction.get("bbox_xyxy_pixels")
            if not isinstance(box, list) or len(box) != 4:
                continue
            overlap = box_iou(target["box"], box)
            if overlap >= iou_threshold:
                possible.append((overlap, ti, pi))
    assigned_truth, assigned_predictions, matches = set(), set(), []
    for overlap, ti, pi in sorted(possible, reverse=True):
        if ti in assigned_truth or pi in assigned_predictions:
            continue
        assigned_truth.add(ti)
        assigned_predictions.add(pi)
        p = predicted[pi]
        matches.append({
            "ground_truth": truth[ti]["class"],
            "predicted": p["label"],
            "correct_class": p["label"] == truth[ti]["class"],
            "in_top_three": truth[ti]["class"] in [
                item["label"] for item in p.get("alternatives", [])
            ],
            "iou": round(overlap, 4),
            "score": p.get("confidence", None),
        })
    return matches


def benchmark(dataset_root, limit=None, predict=automatic_detect):
    root = Path(dataset_root).resolve()
    image_dir = root / "dataset/images/val"
    label_dir = root / "dataset/labels/val"
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise FileNotFoundError("Source dataset/ images/val and labels/val required")
    photos = sorted(
        p for p in image_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        photos = photos[:limit]
    if not photos:
        raise ValueError("No independent validation images")
    totals = Counter()
    by_class = {name: Counter() for _, name in SURE_CLASS_MAP.values()}
    confusion = Counter()
    cases = []
    for photo in photos:
        annotation = label_dir / (photo.stem + ".txt")
        if not annotation.is_file():
            raise FileNotFoundError(f"Missing label: {annotation.name}")
        with Image.open(photo) as image:
            width, height = image.size
        truth, excluded = parse_labels(annotation, width, height)
        predictions = predict(photo)
        matches = match_detections(truth, predictions)
        totals["images"] += 1
        totals["ground_truth"] += len(truth)
        totals["excluded_ambiguous_ground_truth"] += excluded
        totals["matched_boxes"] += len(matches)
        totals["correct_class"] += sum(x["correct_class"] for x in matches)
        totals["correct_in_top3"] += sum(x["in_top_three"] for x in matches)
        matched_truth = Counter(x["ground_truth"] for x in matches)
        for row in truth:
            by_class[row["class"]]["ground_truth"] += 1
        for name, count in matched_truth.items():
            by_class[name]["localized"] += count
        for entry in matches:
            confusion[(entry["ground_truth"], entry["predicted"])] += 1
            if entry["correct_class"]:
                by_class[entry["ground_truth"]]["correct"] += 1
            if entry["in_top_three"]:
                by_class[entry["ground_truth"]]["top3"] += 1
        cases.append({
            "photo": photo.name,
            "ground_truth": len(truth),
            "matched": len(matches),
            "correct": sum(x["correct_class"] for x in matches),
            "mislabels": [x for x in matches if not x["correct_class"]][:12],
        })
    def fraction(n, denom):
        return round(n / denom, 4) if denom else None
    classes = {
        name: {
            "gt": row["ground_truth"],
            "localization_recall_at_iou_0_5": fraction(row["localized"], row["ground_truth"]),
            "correct_class_recall_at_iou_0_5": fraction(row["correct"], row["ground_truth"]),
            "correct_class_in_top3_recall": fraction(row["top3"], row["ground_truth"]),
        }
        for name, row in by_class.items()
    }
    return {
        "status": "exploratory_external_validation_only",
        "method": "class-agnostic greedy IoU>=0.5 pairing; correct-class recall on matched labels",
        "source": {
            "repo": SOURCE_REPOSITORY, "commit": SOURCE_COMMIT,
            "license": "CC BY 4.0",
            "subset": "dataset/images/val",
            "source_class_order": list(SOURCE_NAMES),
        },
        "model": {"name": "original_21class_onnx", "sha256": EXPECTED_SHA256},
        "counts": dict(totals),
        "localization_recall": fraction(totals["matched_boxes"], totals["ground_truth"]),
        "correct_label_recall": fraction(totals["correct_class"], totals["ground_truth"]),
        "top3_correct_label_recall": fraction(totals["correct_in_top3"], totals["ground_truth"]),
        "classes": classes,
        "confusion": [
            {"expected": expected, "predicted": got, "count": count}
            for (expected, got), count in sorted(confusion.items())
        ],
        "cases": cases,
        "caveats": [
            "Source val is only a small third-party split, and physical PCB identity across splits is not independently audited.",
            "Only six unambiguous labels counted; four source categories deliberately excluded.",
            "Incomplete source annotations may hide valid components; false-positive precision and mAP are not claimed.",
            "This is not NOVA field accuracy, a production pass/fail threshold, nor a substitute for a blinded held-out board set.",
        ],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    report = benchmark(args.dataset, limit=args.limit)
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "counts": report["counts"], "correct_label_recall": report["correct_label_recall"],
        "classes": report["classes"],
    }, ensure_ascii=False))
