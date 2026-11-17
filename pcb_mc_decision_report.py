"""Human-readable class coverage and release-hold audit for real PCB-MC reports.

Never loads any .pt pickle, never advertises benchmark mAP as field accuracy,
never automatically promotes the 23-class research model to NOVA live server.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from pcb_mc_import import PRESENT_NAMES

FOCUS = ("Capacitor", "Electrolytic Capacitor", "Diode", "Zener Diode")
RESEARCH_SAMPLE_ALERT = 200  # prioritization heuristic only, NOT success threshold
RESEARCH_VALIDATION_ALERT = 30


class CandidateEvidenceError(ValueError):
    pass


def review(report, model_file=None):
    if not isinstance(report, dict) or report.get("trained") is not True:
        raise CandidateEvidenceError("A completed training report is required")
    if report.get("approved_for_live_use") is not False:
        raise CandidateEvidenceError("Research model must remain explicitly unapproved")
    source = report.get("source_fold", {})
    if source.get("full_zip_md5_verified") is not True:
        raise CandidateEvidenceError("Official 4TU source archive checksum verification missing")
    if source.get("class_order") != list(PRESENT_NAMES):
        raise CandidateEvidenceError("Unexpected source model class ordering")
    if source.get("board_identity_split_from_official_manifest") is not True:
        raise CandidateEvidenceError("Model source requires official board-aware fold")
    if source.get("source_train_images", 0) < 1 or source.get("source_val_images", 0) < 1:
        raise CandidateEvidenceError("Empty source train/validation split")
    if report.get("validation", {}).get("split") != "publisher_official_board_aware_validation":
        raise CandidateEvidenceError("Unexpected validation protocol")
    raw_metrics = report["validation"].get("metrics", {})
    required = ("metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)", "metrics/mAP50-95(B)")
    if any(key not in raw_metrics or not isinstance(raw_metrics[key], (int, float))
           or not math.isfinite(raw_metrics[key]) or not 0 <= raw_metrics[key] <= 1
           for key in required):
        raise CandidateEvidenceError("Missing or invalid class detection metric")
    classes = report["validation"].get("by_class", [])
    per_class = {p.get("class"): p.get("mAP50_95") for p in classes if isinstance(p, dict)}
    if set(per_class) != set(PRESENT_NAMES) or len(classes) != len(PRESENT_NAMES):
        raise CandidateEvidenceError("Missing/duplicate validation class names")
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) or not 0<=x<=1
           for x in per_class.values()):
        raise CandidateEvidenceError("Invalid class-wise mAP values")
    counts = source.get("labels_per_split", {})
    train, val = counts.get("train"), counts.get("val")
    if not isinstance(train, dict) or not isinstance(val, dict):
        raise CandidateEvidenceError("Class-wise train/validation support counts missing")
    if (set(train) | set(val)) - set(PRESENT_NAMES):
        raise CandidateEvidenceError("Unknown dataset category")
    rows = []
    for name in PRESENT_NAMES:
        tr, va = train.get(name, 0), val.get(name, 0)
        if not isinstance(tr, int) or not isinstance(va, int) or tr < 0 or va < 0:
            raise CandidateEvidenceError("Invalid class support count")
        rows.append({
            "name": name,
            "train_objects": tr,
            "validation_objects": va,
            "map50_95": per_class[name],
            "research_collection_priority": (
                "new_verified_board_photos_needed"
                if tr < RESEARCH_SAMPLE_ALERT or va < RESEARCH_VALIDATION_ALERT
                else "assess_visual_confusions"
            ),
            "validation_support_missing": va == 0,
        })
    checkpoint = report.get("best_checkpoint", {})
    digest = checkpoint.get("sha256", "")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise CandidateEvidenceError("Training checkpoint SHA256 is absent/invalid")
    checkpoint_verified = False
    if model_file is not None:
        image = Path(model_file)
        hasher = hashlib.sha256()
        with image.open("rb") as fd:
            for block in iter(lambda: fd.read(1024*1024), b""):
                hasher.update(block)
        if hasher.hexdigest() != digest:
            raise CandidateEvidenceError("Downloaded checkpoint does not match training SHA256")
        checkpoint_verified = True
    focus = [next(row for row in rows if row["name"] == name) for name in FOCUS]
    return {
        "result": "research_only_no_production_release",
        "trained_classes": 23,
        "source_fold": source.get("official_fold"),
        "source_image_counts": {"train": source["source_train_images"], "val": source["source_val_images"]},
        "training_parameters": report.get("parameters"),
        "validation_metrics": {k: raw_metrics[k] for k in required},
        "all_class_coverage": rows,
        "priority_capacitor_diode_evidence": focus,
        "rare_class_count": sum(row["research_collection_priority"] == "new_verified_board_photos_needed" for row in rows),
        "source_full_archive_md5_verified": True,
        "checkpoint_sha256": digest,
        "checkpoint_sha256_verified": checkpoint_verified,
        "can_replace_live_21class_detector": False,
        "reasons_no_production_release": [
            "This 23-class research ONNX/pt interface is not the pinned 21-class live detector.",
            "Independent NOVA unseen service-board evaluation has not been performed.",
            "Model redistribution/network service licensing review has not been completed.",
            "3-epoch proof-of-pipeline model has very low recall; per-class support is highly uneven.",
        ],
        "note": (
            "Object instances are not distinct boards; thresholds of 200/30 are optional "
            "data-collection priorities, not acceptance criteria. No image code is inferred."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = review(json.loads(Path(args.report).read_text(encoding="utf-8")),
                    model_file=args.checkpoint)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "result": result["result"],
        "metrics": result["validation_metrics"],
        "priority": result["priority_capacitor_diode_evidence"],
        "rare_class_count": result["rare_class_count"],
        "checkpoint_sha256_verified": result["checkpoint_sha256_verified"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
