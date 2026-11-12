"""Local private autosaves for photo-guided measurement sessions.

No network or cloud storage. Recovery matches original image identity and
near-identical detector boxes to avoid copying measurements to wrong parts.
"""
import hashlib
import json
import math
from pathlib import Path

from measurement_guides import instruction_for

SAFE_FIELDS = (
    "measurement_history", "reading", "status", "technician_verified_type",
    "component", "source_label", "part_number", "part_number_verified_by_user",
    "probe_points", "pin_mapping", "reference_result", "reference_source",
)


def autosave_path(image_path, folder=None):
    image = Path(image_path).resolve()
    info = image.stat()
    identity = f"{image}|{info.st_size}|{info.st_mtime_ns}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    base = Path(folder) if folder is not None else Path.home() / ".nova_dcg" / "autosave"
    return base / f"{digest}.json"


def save_autosave(image_path, tasks, folder=None):
    target = autosave_path(image_path, folder)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "nova-dcg-autosave-v2",
        "image": str(Path(image_path).resolve()),
        "tasks": tasks,
        "note": "Local technician session, includes unverified model proposals.",
    }
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)
    return target


def _overlap(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter = max(0, min(ax2,bx2)-max(ax1,bx1))*max(0, min(ay2,by2)-max(ay1,by1))
    area = (ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-inter
    return inter/area if area > 0 else 0


def restore_autosave(image_path, fresh_tasks, folder=None):
    target = autosave_path(image_path, folder)
    if not target.exists():
        return 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("format") != "nova-dcg-autosave-v2":
        return 0
    if payload.get("image") != str(Path(image_path).resolve()):
        return 0
    old_tasks = payload.get("tasks", [])
    if not isinstance(old_tasks,list):
        return 0
    matches = 0
    consumed = set()
    for task in fresh_tasks:
        source = task.get("model_source_label", task.get("source_label"))
        bbox = task["bbox_xyxy_pixels"]
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in bbox):
            continue
        candidate = None
        score = .80
        for i, previous in enumerate(old_tasks):
            if i in consumed or not isinstance(previous,dict):
                continue
            prev_source = previous.get("model_source_label",previous.get("source_label"))
            if source != prev_source:
                continue
            old_box = previous.get("bbox_xyxy_pixels",[])
            if len(old_box)!=4:
                continue
            overlap = _overlap(bbox, old_box)
            if overlap > score:
                candidate, score = i, overlap
        if candidate is None:
            continue
        previous = old_tasks[candidate]
        consumed.add(candidate)
        for field in SAFE_FIELDS:
            if field in previous:
                task[field] = previous[field]
        if task.get("technician_verified_type"):
            task["mode"], description = instruction_for(task["component"])
            task["instruction"] = description + " Kart enerjisiz ve deşarj edilmiş olmalı."
        matches += 1
    return matches
