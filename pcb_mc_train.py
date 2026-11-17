"""Optional multi-fold supervised 23-class PCB-MC training on verified local data.

This program never fetches the 3.77GB archive, never modifies the live
21-class model, and never silently re-splits board layouts. Each fold must
be imported from the publisher's official train/validation manifest.

Model replacement requires independent multi-board evaluation, license
review, and an explicit decision outside this script.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from pcb_mc_import import PRESENT_NAMES


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fd:
        for buf in iter(lambda:fd.read(1024*1024),b""):
            h.update(buf)
    return h.hexdigest()


def validate_fold(prepared):
    prepared=Path(prepared).resolve()
    data=prepared/"data.yaml"
    audit=prepared/"import_audit.json"
    if not data.is_file() or not audit.is_file():
        raise FileNotFoundError("Official PCB-MC import_audit.json and data.yaml required")
    metadata=json.loads(audit.read_text(encoding="utf-8"))
    if metadata.get("board_identity_split_from_official_manifest") is not True:
        raise ValueError("Unofficial/random board split is forbidden")
    if metadata.get("class_order") != list(PRESENT_NAMES):
        raise ValueError("23-class order mismatch")
    if metadata.get("source_train_images",0)<1 or metadata.get("source_val_images",0)<1:
        raise ValueError("Empty official split")
    import yaml
    config=yaml.safe_load(data.read_text(encoding="utf-8"))
    names=config.get("names",{})
    if isinstance(names,dict):
        entries=[names[i] for i in range(len(names))]
    elif isinstance(names,list):
        entries=names
    else:
        raise ValueError("Invalid class mapping in data YAML")
    if entries!=list(PRESENT_NAMES):
        raise ValueError("Class names in YAML must match imported 23-class taxonomy")
    for name in ("images/train","images/val","labels/train","labels/val"):
        if not (prepared/name).is_dir():
            raise FileNotFoundError(f"Missing prepared images or labels: {name}")
    return metadata


def train_fold(prepared,output,*,epochs=60,imgsz=960,batch=4,device="cpu"):
    if not isinstance(epochs,int) or not 1<=epochs<=300:
        raise ValueError("Epochs must be within 1–300")
    if not isinstance(imgsz,int) or not 320<=imgsz<=1536 or imgsz%32:
        raise ValueError("imgsz must be 320–1536, divisible by 32")
    if not isinstance(batch,int) or not 1<=batch<=32:
        raise ValueError("batch must be 1–32")
    metadata=validate_fold(prepared)
    prepared=Path(prepared).resolve()
    output=Path(output).resolve()
    if output==prepared or output in prepared.parents:
        raise ValueError("Training output must be separate from immutable source data")
    output.mkdir(parents=True,exist_ok=True)

    from ultralytics import YOLO
    model=YOLO("yolov8n.pt")
    model.train(
        data=str(prepared/"data.yaml"),epochs=epochs,imgsz=imgsz,
        batch=batch,device=device,workers=0,seed=42,deterministic=True,
        project=str(output/"training_runs"),name="pcb_mc_23class",
        exist_ok=True,save=True,plots=False,
    )
    path=Path(model.trainer.best).resolve()
    if not path.is_file():
        raise RuntimeError("Training did not create best checkpoint")
    verified=YOLO(str(path))
    names=verified.names
    actual=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
    if actual!=list(PRESENT_NAMES):
        raise RuntimeError("Trained model 23-class order differs from the source dataset")
    val=verified.val(data=str(prepared/"data.yaml"),split="val",
                     imgsz=imgsz,device=device,workers=0,plots=False)
    metrics={str(k):float(v) for k,v in val.results_dict.items()
             if isinstance(v,(int,float)) and math.isfinite(float(v))}
    if not metrics:
        raise RuntimeError("No real validation metrics returned")
    by_class=[]
    box=getattr(val,"box",None)
    if box is not None and getattr(box,"maps",None) is not None:
        for label,value in zip(PRESENT_NAMES,box.maps):
            by_class.append({"class":label,"mAP50_95":float(value)})
    report={
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "trained":True,
        "model":"experimental_PCB_MC_C_23class_yolov8n",
        "source_fold":metadata,
        "parameters":{"epochs":epochs,"imgsz":imgsz,"batch":batch,"device":device},
        "validation":{
            "split":"publisher_official_board_aware_validation",
            "metrics":metrics,
            "by_class":by_class,
        },
        "best_checkpoint":{"path":str(path),"sha256":sha256(path)},
        "approved_for_live_use":False,
        "license_review_required":True,
        "caution":"Official folds are for validation; reserve separate truly unseen NOVA service boards for rollout gate.",
    }
    (output/"training_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--prepared",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--epochs",type=int,default=60)
    parser.add_argument("--imgsz",type=int,default=960)
    parser.add_argument("--batch",type=int,default=4)
    parser.add_argument("--device",default="cpu")
    parser.add_argument("--audit-only",action="store_true")
    args=parser.parse_args()
    report=validate_fold(args.prepared) if args.audit_only else train_fold(
        args.prepared,args.output,epochs=args.epochs,imgsz=args.imgsz,
        batch=args.batch,device=args.device
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
