"""Auditable NOVA DCG PCB training pipeline (no fabricated training results).

Only explicitly technician-verified annotations qualify. Different photos of
the same physical PCB use the same board_id to avoid validation/test leakage.
Training is opt-in and requires genuinely labeled images and local weights.
"""
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dataset import CLASSES, validate_annotation
from prepare_dataset import prepare


def audit_annotations(source_dir):
    source = Path(source_dir)
    if not source.is_dir():
        raise FileNotFoundError(f"Eğitim fotoğraf/etiket klasörü yok: {source}")
    files = sorted(source.rglob("*.json"))
    records = []
    seen_images = {}
    counts = Counter()
    boards = defaultdict(list)
    for file in files:
        item = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or "regions" not in item:
            continue
        if item.get("technician_verified") is not True:
            raise ValueError(f"Teknisyen onayı eksik: {file}")
        board_id = str(item.get("board_id") or "").strip()
        if not board_id:
            raise ValueError(f"board_id eksik: {file}")
        if not item.get("image"):
            raise ValueError(f"image alanı eksik: {file}")
        image = Path(item["image"])
        if not image.is_absolute():
            image = file.parent / image
        image = image.resolve()
        if not image.is_file():
            raise FileNotFoundError(f"Görüntü bulunamadı: {image}")
        old_board = seen_images.get(image)
        if old_board is not None and old_board != board_id:
            raise ValueError(f"Aynı fotoğraf iki kart kimliğiyle etiketlenmiş: {image}")
        seen_images[image] = board_id
        checked = validate_annotation(item)
        if not checked:
            raise ValueError(f"Komponent kutusu içermeyen etiket: {file}")
        for index, *_ in checked:
            counts[CLASSES[index]] += 1
        boards[board_id].append(str(image))
        records.append((file, board_id, image))
    if len(boards) < 3:
        raise ValueError("Eğitim / doğrulama / test için en az 3 farklı fiziksel kart gerekir.")
    if not records:
        raise ValueError("Doğrulanmış etiketli fotoğraf yok.")
    warnings = []
    if len(boards) < 30:
        warnings.append("30'dan az ayrı PCB var. Gerçek dünya performansı için çok daha fazla farklı kart toplayın.")
    if len(records) < 150:
        warnings.append("150'den az etiketli fotoğraf var. Veri çeşitliliğini artırın.")
    for cls in CLASSES:
        if cls == "Bilinmiyor":
            continue
        if counts[cls] == 0:
            warnings.append(f"Hiç {cls} örneği yok; model bu sınıfı güvenilir öğrenemez.")
        elif counts[cls] < 50:
            warnings.append(f"{cls}: yalnızca {counts[cls]} örnek. Daha fazla etiket toplayın.")
    if counts["Bilinmiyor"]:
        warnings.append("Bilinmiyor sınıfı içeriliyor; emin olunmayan parçaları eğitim verisinden ayırın.")
    return {
        "board_count": len(boards), "image_count": len(records),
        "box_count": sum(counts.values()), "classes": list(CLASSES),
        "labels": dict(counts), "warnings": warnings,
        "verified": True, "board_ids": sorted(boards),
    }


def train_verified(
    annotations_dir, output_dir, base_model, *,
    epochs=70, imgsz=960, batch=8, device="auto", seed=42,
):
    if not isinstance(epochs,int) or epochs < 1 or epochs > 1000:
        raise ValueError("epochs 1–1000 arasında olmalı")
    if not isinstance(imgsz,int) or imgsz < 320 or imgsz > 2048 or imgsz % 32:
        raise ValueError("imgsz 320–2048 arasında 32'nin katı olmalı")
    if not isinstance(batch,int) or batch < 1:
        raise ValueError("batch pozitif olmalı")
    weights = Path(base_model).expanduser().resolve()
    if not weights.is_file():
        raise FileNotFoundError(f"Yerel başlangıç modeli yok: {weights}")
    audit = audit_annotations(annotations_dir)
    out = Path(output_dir).expanduser().resolve()
    if Path(annotations_dir).resolve() == out:
        raise ValueError("Veri giriş ve çıkış klasörleri ayrı olmalı")
    summary = prepare(annotations_dir, out, seed=seed)
    from ultralytics import YOLO
    model = YOLO(str(weights))
    options = {
        "data": str(out / "data.yaml"), "epochs": epochs,
        "imgsz": imgsz, "batch": batch, "seed": seed,
        "project": str(out / "training_runs"), "name": "pcb_v2",
        "exist_ok": False,
    }
    if device != "auto":
        options["device"] = device
    model.train(**options)
    result = model.val(data=str(out / "data.yaml"), split="test", imgsz=imgsz)
    metrics = {}
    for key, value in getattr(result, "results_dict", {}).items():
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            metrics[str(key)] = float(value)
    checksum = hashlib.sha256()
    with weights.open("rb") as fd:
        for chunk in iter(lambda: fd.read(1024 * 1024), b""):
            checksum.update(chunk)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "training_did_run": True,
        "evaluation_split": "test",
        "metrics": metrics,
        "dataset": audit,
        "prepared": summary,
        "base_model_sha256": checksum.hexdigest(),
        "parameters": {key: str(value) for key,value in options.items()},
        "warning": "Unseen-board benchmark and human error review required before service claims.",
    }
    (out / "training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", help="Verified per-board image+JSON directory")
    parser.add_argument("output", help="A separate directory for split dataset and trained model")
    parser.add_argument("--base-model", required=True, help="Local pretrained .pt checkpoint")
    parser.add_argument("--epochs", type=int, default=70)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="auto", help="auto, cpu, mps, or cuda:0")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--audit-only", action="store_true")
    args=parser.parse_args()
    if args.audit_only:
        report=audit_annotations(args.annotations)
    else:
        report=train_verified(
            args.annotations, args.output, args.base_model,
            epochs=args.epochs, imgsz=args.imgsz,
            batch=args.batch, device=args.device, seed=args.seed,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
