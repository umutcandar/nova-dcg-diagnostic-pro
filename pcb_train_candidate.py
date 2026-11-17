"""Train an auditable *auxiliary* 10-class PCB detector candidate on licensed public data.

NOT a replacement for NOVA's 21-class ONNX model. The 130-image source does
not establish physical-board-disjoint train/val groups; reported val results
are exploration only. Candidate weights require separate board-level QA and
a licensing decision before any live integration.

Source CC BY 4.0: https://github.com/wangshnegqi/pcb-component-detection-dataset-yolo
Pinned to commit 0d7ae7310fa607389779b6132285336ad73e96e1.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE_SHA = "0d7ae7310fa607389779b6132285336ad73e96e1"
SOURCE = "https://github.com/wangshnegqi/pcb-component-detection-dataset-yolo"
NAMES = [
    "Resistor", "Capacitor", "Diode", "LED", "IC",
    "Connector", "Switch/Button", "Header", "Crystal", "Debug/TP"
]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_source(root, *, expected_train=100, expected_val=10):
    root = Path(root).resolve()
    data = root / "dataset"
    text = (root / "LICENSE-DATASET").read_text(encoding="utf-8")
    if "Creative Commons Attribution 4.0" not in text or "CC BY 4.0" not in text:
        raise ValueError("Expected source dataset CC BY 4.0 license is absent")
    source_yaml = (data / "data.yaml").read_text(encoding="utf-8")
    import yaml
    settings = yaml.safe_load(source_yaml)
    if settings.get("nc") != len(NAMES) or settings.get("names") != NAMES:
        raise ValueError("Unexpected source class order; refusing silent remap")
    counter = Counter()
    images = {}
    duplicate_fingerprints = {}
    for split in ("train", "val"):
        image_dir = data / "images" / split
        label_dir = data / "labels" / split
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise FileNotFoundError(f"Missing {split} images/labels")
        files = sorted(x for x in image_dir.iterdir()
                       if x.suffix.lower() in {".jpg", ".jpeg", ".png"})
        if len(files) < (expected_train if split == "train" else expected_val):
            raise ValueError(f"Insufficient {split} photos for proposed benchmark")
        image_stems = {p.stem for p in files}
        label_stems = {p.stem for p in label_dir.iterdir() if p.suffix == ".txt"}
        if image_stems != label_stems:
            raise ValueError(f"Image-label mismatch in {split}")
        images[split] = len(files)
        for photo in files:
            digest = sha256(photo)
            previous = duplicate_fingerprints.get(digest)
            if previous and previous[0] != split:
                raise ValueError(f"Exact train/val image leakage: {previous[1]} vs {photo}")
            duplicate_fingerprints[digest] = (split, photo.name)
            for n, line in enumerate((label_dir / (photo.stem + ".txt")).read_text().splitlines(), 1):
                columns = line.split()
                if not columns:
                    continue
                if len(columns) != 5:
                    raise ValueError(f"{photo.name}:{n} malformed YOLO label")
                try:
                    classid = int(columns[0])
                    numbers = [float(x) for x in columns[1:]]
                except ValueError as exc:
                    raise ValueError(f"{photo.name}:{n} invalid label") from exc
                x, y, w, h = numbers
                if classid not in range(len(NAMES)) or not all(map(math.isfinite,numbers)) \
                    or not (w > 0 and h > 0 and 0 <= x-w/2 < x+w/2 <= 1
                         and 0 <= y-h/2 < y+h/2 <= 1):
                    raise ValueError(f"{photo.name}:{n} invalid region/class")
                counter[(split, NAMES[classid])] += 1
    return {
        "source_repo": SOURCE,
        "pinned_source_sha": SOURCE_SHA,
        "license": "CC BY 4.0 (source dataset), citation and attribution required",
        "images": images,
        "annotations": {
            split: {cls: counter[(split,cls)] for cls in NAMES}
            for split in ("train","val")
        },
        "exact_cross_split_duplicate_check": "passed",
        "board_identity_split_verified": False,
        "warnings": [
            "Near-duplicate boards and multiple photos of one PCB are not audited.",
            "Original 13-image validation set is small, not production-grade independent test.",
            "Some labels may be incomplete; partial annotation may bias candidate detector.",
            "Model only detects 10 source classes, NOT full NOVA 21-class coverage.",
        ],
    }


def create_training_yaml(root, out):
    import yaml
    root = Path(root).resolve()
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "path": str(root / "dataset"),
        "train": "images/train",
        "val": "images/val",
        "nc": 10,
        "names": NAMES,
    }
    out.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    return out


def train_candidate(source_root, output, *, epochs=8, imgsz=512, batch=4, device="cpu"):
    if not isinstance(epochs,int) or not 1 <= epochs <= 120:
        raise ValueError("Epochs 1–120 required")
    if not isinstance(imgsz,int) or imgsz < 320 or imgsz > 1280 or imgsz%32:
        raise ValueError("Image size must be 320–1280 and multiple of 32")
    if not isinstance(batch,int) or not 1 <= batch <= 32:
        raise ValueError("Batch 1–32 required")
    out=Path(output).resolve()
    out.mkdir(parents=True,exist_ok=True)
    audit=audit_source(source_root)
    (out/"source_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),
                                         encoding="utf-8")
    data_yaml=create_training_yaml(source_root,out/"data.yaml")
    from ultralytics import YOLO
    model=YOLO("yolov8n.pt")  # Official pretrained general-object model, NOT untrusted third-party pickle.
    model.train(
        data=str(data_yaml), epochs=epochs, imgsz=imgsz, batch=batch, device=device,
        workers=0, optimizer="AdamW", seed=42, deterministic=True, plots=False,
        project=str(out/"runs"), name="candidate10", exist_ok=True, cache=False,
        save=True, val=True, verbose=False,
    )
    best=Path(model.trainer.best).resolve()
    if not best.is_file():
        raise RuntimeError("No genuine trained checkpoint produced")
    trained=YOLO(str(best))
    actual=trained.names
    names=[actual[i] for i in range(len(actual))] if isinstance(actual,dict) else list(actual)
    if names != NAMES:
        raise RuntimeError("Checkpoint class names do not match source dataset")
    validation=trained.val(data=str(data_yaml),split="val",imgsz=imgsz,
                           device=device,workers=0,plots=False)
    metrics={
        str(k):float(v) for k,v in getattr(validation,"results_dict",{}).items()
        if isinstance(v,(int,float)) and math.isfinite(float(v))
    }
    if not metrics:
        raise RuntimeError("No real validation metrics produced")
    import shutil
    target=out/"candidate10.pt"
    shutil.copy2(best,target)
    report={
        "trained":True,
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "purpose":"research_auxiliary_10class_candidate_not_live",
        "source_audit":audit,
        "parameters":{"epochs":epochs,"imgsz":imgsz,"batch":batch,"device":device,
                      "base":"official_yolov8n.pt","seed":42},
        "validation":{"split":"original_source_val",
                      "physical_board_disjoint":False,"metrics":metrics},
        "checkpoint":{"file":target.name,"sha256":sha256(target),"bytes":target.stat().st_size},
        "approved_for_live_use":False,
        "license_attention":"Ultralytics AGPL-3.0 conditions need legal review before commercial integration.",
        "next_step":"Board-disjoint evaluation and comparison against pinned 21-class baseline.",
    }
    try:
        onnx_path=Path(trained.export(format="onnx",imgsz=imgsz,opset=12,
                                      simplify=False,dynamic=False,device="cpu"))
        if onnx_path.is_file():
            dest=out/"candidate10.onnx"
            shutil.copy2(onnx_path,dest)
            report["export"]={"file":dest.name,"sha256":sha256(dest),
                              "bytes":dest.stat().st_size}
    except Exception as exc:
        report["export_error"]=f"{type(exc).__name__}: ONNX export unavailable; PT checkpoint remains."
    (out/"training_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--epochs",type=int,default=8)
    parser.add_argument("--imgsz",type=int,default=512)
    parser.add_argument("--batch",type=int,default=4)
    parser.add_argument("--device",default="cpu")
    parser.add_argument("--audit-only",action="store_true")
    args=parser.parse_args()
    if args.audit_only:
        result=audit_source(args.source)
    else:
        result=train_candidate(args.source,args.output,epochs=args.epochs,
                                imgsz=args.imgsz,batch=args.batch,device=args.device)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
