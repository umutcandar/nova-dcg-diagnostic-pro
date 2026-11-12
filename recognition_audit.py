"""Evidence-only quality report for PCB detection, without fabricated accuracy.

Model confidence is NOT the same as classification accuracy. This report does
not claim recall, precision, electrical health, or missing component counts.
"""
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def summarize_detections(detections, image_size):
    width, height = image_size
    if width < 1 or height < 1:
        raise ValueError("Invalid image dimensions")
    counts = Counter()
    confidence_values = []
    review_indices = []
    invalid_indices = []
    for i, item in enumerate(detections):
        if not isinstance(item, dict):
            invalid_indices.append(i)
            continue
        label = str(item.get("label") or "Bilinmiyor")
        box = item.get("bbox_xyxy_pixels")
        try:
            coordinates = [float(v) for v in box]
            if len(coordinates) != 4 or not all(math.isfinite(v) for v in coordinates):
                raise ValueError
            x1, y1, x2, y2 = coordinates
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise ValueError
        except (TypeError, ValueError):
            invalid_indices.append(i)
            continue
        score = item.get("confidence")
        if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            invalid_indices.append(i)
            continue
        confidence_values.append(float(score))
        counts[label] += 1
        if score < 0.5 or label == "Bilinmiyor":
            review_indices.append(i)
    n = len(confidence_values)
    warnings = []
    if not n:
        warnings.append("Model görüntüde geçerli komponent adayı bulamadı. Bu, kartta parça olmadığı anlamına gelmez.")
    if review_indices:
        warnings.append(f"{len(review_indices)} aday düşük güvenli veya bilinmiyor: teknisyen doğrulaması gerekli.")
    if invalid_indices:
        warnings.append(f"{len(invalid_indices)} geçersiz tespit sonucu sayılmadı.")
    warnings.append("Model güven puanları doğruluk oranı değildir; kaçırılan komponent sayısı bu verilerden hesaplanamaz.")
    return {
        "schema": "nova-dcg-recognition-audit-v1",
        "image_size": {"width": width, "height": height},
        "detected_candidates": n,
        "source_candidates": len(detections),
        "class_counts": dict(sorted(counts.items())),
        "mean_model_confidence": round(sum(confidence_values) / n, 4) if n else None,
        "min_model_confidence": round(min(confidence_values), 4) if n else None,
        "requires_review": len(review_indices),
        "requires_review_indices": review_indices,
        "invalid_indices": invalid_indices,
        "warnings": warnings,
        "ground_truth_available": False,
        "accuracy_evaluated": False,
    }


def save_local_audit(photo_path, summary, folder=None):
    """Save the diagnostic report locally without copying or uploading the photo."""
    import hashlib
    image = Path(photo_path).resolve()
    stat = image.stat()
    key = hashlib.sha256(f"{image}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8")).hexdigest()
    directory = Path(folder) if folder else Path.home() / ".nova_dcg" / "diagnostics"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{key}.json"
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "photo_filename": image.name,
        "report": summary,
    }
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return target
