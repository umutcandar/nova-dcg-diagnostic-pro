"""Evaluate PCB detections only against exhaustive, verified, held-out boards.

This is an offline evaluation harness, not a claim of measured model quality.
Each annotation must have annotation_complete and technician_verified true.
Physical board IDs are selected explicitly to avoid accidental train/test reuse.
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps
from dataset import CLASSES, validate_annotation
from model_inference import _iou, deduplicate_detections


def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def _box(box, size):
    try:
        values = [float(v) for v in box]
        if len(values) != 4 or not all(math.isfinite(v) for v in values):
            raise ValueError
        x1, y1, x2, y2 = values
        if not (0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1]):
            raise ValueError
        return values
    except (TypeError, ValueError):
        raise ValueError("Geçersiz veya fotoğraf dışı piksel kutusu") from None


def load_holdout_ids(filename):
    path = Path(filename)
    if not path.is_file():
        raise FileNotFoundError(path)
    ids = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
           if line.strip() and not line.lstrip().startswith("#")}
    if not ids:
        raise ValueError("Bağımsız test kartı listesi boş")
    return ids


def load_verified_records(annotations_dir, holdout_ids):
    folder = Path(annotations_dir).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    records = []
    seen_boards = set()
    for path in sorted(folder.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "regions" not in data:
            continue
        board_id = str(data.get("board_id") or "").strip()
        if board_id not in holdout_ids:
            continue
        if data.get("technician_verified") is not True:
            raise ValueError(f"Teknisyen onayı yok: {path}")
        if data.get("annotation_complete") is not True:
            raise ValueError(f"Tüm parçalar etiketlenmemiş: {path}")
        regions = validate_annotation(data)
        if any(CLASSES[row[0]] == "Bilinmiyor" for row in regions):
            raise ValueError(f"Bilinmiyor sınıfı olan kartta precision ölçülemez: {path}")
        image_ref = data.get("image")
        if not isinstance(image_ref, str) or not image_ref:
            raise ValueError(f"image alanı eksik: {path}")
        image = Path(image_ref)
        if not image.is_absolute():
            image = path.parent / image
        image = image.resolve()
        if not image.is_file():
            raise FileNotFoundError(image)
        with Image.open(image) as img:
            size = ImageOps.exif_transpose(img).size
        if (data.get("image_width"), data.get("image_height")) != size:
            raise ValueError(f"Fotoğraf boyutu veya EXIF yönü etiketten farklı: {path}")
        gt = []
        for index, cx, cy, w, h in regions:
            gt.append({
                "label": CLASSES[index],
                "bbox": [(cx - w / 2) * size[0], (cy - h / 2) * size[1],
                         (cx + w / 2) * size[0], (cy + h / 2) * size[1]],
            })
        records.append({"annotation": path, "image": image, "board_id": board_id,
                        "size": size, "gt": gt,
                        "relative_path": path.relative_to(folder)})
        seen_boards.add(board_id)
    missing = holdout_ids - seen_boards
    if missing:
        raise ValueError("Etiketlenmiş test kartı bulunamadı: " + ", ".join(sorted(missing)))
    return records


def _load_predictions(record, weights=None, predictions_dir=None):
    if weights is not None:
        from model_inference import detect_components
        rows = detect_components(record["image"], weights, confidence=0.05, postprocess=False)
    else:
        path = Path(predictions_dir) / record["relative_path"].with_suffix(".predictions.json")
        if not path.is_file():
            raise FileNotFoundError(f"Tahmin dosyası bulunamadı: {path}")
        rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Tahminler JSON listesi olmalı")
    result = []
    for index, item in enumerate(rows, 1):
        if not isinstance(item, dict) or item.get("label") not in CLASSES:
            raise ValueError(f"Tanımsız tahmin etiketi ({record['image']} #{index})")
        score = item.get("confidence")
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"Geçersiz model güveni ({record['image']} #{index})")
        result.append({"label": item["label"],
                       "source_label": str(item.get("source_label") or item["label"]),
                       "confidence": score,
                       "bbox": _box(item.get("bbox_xyxy_pixels"), record["size"])})
    return result


def score_predictions(records, threshold=0.45, iou_threshold=0.50):
    """Greedy one-to-one class-agnostic spatial matching.

    A wrong class at the right location is counted as a class error, not a
    phantom object. Unmatched predictions are false-positive candidates.
    """
    if not (0 <= threshold <= 1 and 0 < iou_threshold <= 1):
        raise ValueError("Eşikler 0..1 aralığında olmalı")
    aggregate = Counter()
    confusion = Counter()
    per_class = {label: Counter() for label in CLASSES}
    board_stats = {}
    for record in records:
        gt = record["gt"]
        # Filter first, then apply the exact application postprocessing at
        # each threshold. Otherwise low-score alternatives distort calibration.
        thresholded = [{**p, "bbox_xyxy_pixels": p["bbox"]}
                       for p in record["predictions"] if p["confidence"] >= threshold]
        preds = [{**p, "bbox": p["bbox_xyxy_pixels"]}
                 for p in deduplicate_detections(thresholded)]
        pairs = sorted(
            ((iou, preds[pi]["confidence"], gi, pi)
             for gi, truth in enumerate(gt) for pi, pred in enumerate(preds)
             if (iou := _iou(truth["bbox"], pred["bbox"])) >= iou_threshold),
            reverse=True,
        )
        used_gt, used_pred = set(), set()
        local = Counter()
        for _, _, gi, pi in pairs:
            if gi in used_gt or pi in used_pred:
                continue
            used_gt.add(gi)
            used_pred.add(pi)
            truth, pred = gt[gi]["label"], preds[pi]["label"]
            confusion[(truth, pred)] += 1
            local["localized_matches"] += 1
            if truth == pred:
                local["correct_class"] += 1
                per_class[truth]["tp"] += 1
            else:
                local["class_errors"] += 1
                per_class[truth]["fn"] += 1
                per_class[pred]["fp"] += 1
                if truth == "Kondansatör" and pred == "Diyot":
                    local["capacitor_as_diode"] += 1
                if truth == "Diyot" and pred == "Kondansatör":
                    local["diode_as_capacitor"] += 1
        for gi, truth in enumerate(gt):
            if gi not in used_gt:
                per_class[truth["label"]]["fn"] += 1
                confusion[(truth["label"], "(kaçırıldı)")] += 1
        for pi, pred in enumerate(preds):
            if pi not in used_pred:
                per_class[pred["label"]]["fp"] += 1
                confusion[("(arka plan)", pred["label"])] += 1
        local["gt"] = len(gt)
        local["predictions"] = len(preds)
        local["false_candidates"] = len(preds) - len(used_pred)
        local["missed_objects"] = len(gt) - len(used_gt)
        aggregate.update(local)
        b = board_stats.setdefault(record["board_id"], Counter())
        b.update(local)
    gt_count = aggregate["gt"]
    pred_count = aggregate["predictions"]
    matches = aggregate["localized_matches"]
    correct = aggregate["correct_class"]
    class_results = {}
    for label, row in per_class.items():
        support = row["tp"] + row["fn"]
        if support == 0 and row["fp"] == 0:
            continue
        class_results[label] = {
            "support": support, "tp": row["tp"], "fp": row["fp"], "fn": row["fn"],
            "precision": _rate(row["tp"], row["tp"] + row["fp"]),
            "recall": _rate(row["tp"], support),
        }
    return {
        "threshold": threshold, "iou_threshold": iou_threshold,
        "image_count": len(records), "board_count": len(board_stats),
        "gt_components": gt_count, "predicted_candidates": pred_count,
        "matched_locations": matches, "correct_classes": correct,
        "false_positive_candidates": aggregate["false_candidates"],
        "missed_components": aggregate["missed_objects"],
        "classification_errors": aggregate["class_errors"],
        "capacitor_as_diode": aggregate["capacitor_as_diode"],
        "diode_as_capacitor": aggregate["diode_as_capacitor"],
        "candidate_precision": _rate(matches, pred_count),
        "candidate_recall": _rate(matches, gt_count),
        "class_precision": _rate(correct, pred_count),
        "class_recall": _rate(correct, gt_count),
        "per_class": class_results,
        "confusion": [
            {"actual": a, "predicted": b, "count": count}
            for (a, b), count in sorted(confusion.items())
        ],
        "per_board": {key: dict(value) for key, value in sorted(board_stats.items())},
    }


def run_benchmark(annotations, holdout_boards, *, weights=None,
                  predictions_dir=None, thresholds=(0.22, 0.35, 0.45, 0.55, 0.65),
                  iou_threshold=0.50):
    if (weights is None) == (predictions_dir is None):
        raise ValueError("Model ağırlığı veya tahmin klasöründen yalnızca birini seçin")
    if weights is not None and not Path(weights).is_file():
        raise FileNotFoundError(weights)
    if predictions_dir is not None and not Path(predictions_dir).is_dir():
        raise FileNotFoundError(predictions_dir)
    if not thresholds or any(not isinstance(t, (int, float)) or
                             not math.isfinite(t) or not 0 <= t <= 1 for t in thresholds):
        raise ValueError("Confidence eşikleri geçersiz")
    holdout_ids = load_holdout_ids(holdout_boards)
    records = load_verified_records(annotations, holdout_ids)
    for record in records:
        record["predictions"] = _load_predictions(
            record, weights=weights, predictions_dir=predictions_dir
        )
    return {
        "schema": "nova-dcg-heldout-benchmark-v1",
        "ground_truth_available": True,
        "accuracy_evaluated": True,
        "holdout_board_ids": sorted(holdout_ids),
        "source": "local_model" if weights is not None else "saved_predictions",
        "results": [score_predictions(records, float(threshold), iou_threshold)
                    for threshold in thresholds],
        "caveat": "Yalnızca etiketlenmiş ve bağımsız seçilmiş kartlara ilişkin sonuçlardır. "
                  "Modelin eğitiminde aynı kartların kullanılmadığını ayrıca doğrulayın. "
                  "Sınıf doğruluğu elektriksel sağlamlığı kanıtlamaz.",
    }


def main():
    parser = argparse.ArgumentParser(description="Held-out PCB detection evaluation")
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--holdout-boards", required=True, help="One physical board_id per line")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--weights", help="Local compatible .pt model")
    source.add_argument("--predictions-dir", help="Mirrored *.predictions.json files")
    parser.add_argument("--thresholds", default="0.22,0.35,0.45,0.55,0.65")
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--output", default="pcb_holdout_report.json")
    args = parser.parse_args()
    report = run_benchmark(
        args.annotations, args.holdout_boards, weights=args.weights,
        predictions_dir=args.predictions_dir,
        thresholds=tuple(float(s.strip()) for s in args.thresholds.split(",")),
        iou_threshold=args.iou,
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(target), "boards": len(report["holdout_board_ids"]),
                      "results": report["results"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
