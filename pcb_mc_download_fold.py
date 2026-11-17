"""Verified full PCB-MC source download and exact published 23-class YOLO fold extraction.

This tool streams the official 4TU 3.77 GB archive, validates its full MD5,
then extracts ONLY one published PCB-MC-C fold's train/valid images and YOLO
labels. All extracted file names are checked; no arbitrary ZIP extractall.

The prepared data is research-only. No model is promoted to Render.
"""
import argparse
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

from pcb_mc_archive_probe import (
    API, DIRECT_UUID, DOI, EXPECTED_FILENAME, EXPECTED_MD5,
    EXPECTED_SIZE, ProbeError, get_json, select_official_file
)
from pcb_mc_import import PRESENT_NAMES

MAX_SINGLE_UNCOMPRESSED = 65*1024*1024
MAX_EXTRACTED_TOTAL = 5*1024*1024*1024


def stream_official_archive(destination):
    """Fail closed on mismatched official metadata, size, or MD5."""
    destination=Path(destination).resolve()
    if destination.exists():
        if destination.stat().st_size!=EXPECTED_SIZE:
            raise ProbeError("Cached 4TU ZIP has unexpected size")
        if file_md5(destination)!=EXPECTED_MD5:
            raise ProbeError("Cached 4TU ZIP did not match published MD5")
        return destination
    article=get_json(API+"/articles/"+DIRECT_UUID)
    if not str(article.get("doi","")).startswith(DOI) or "PCB-MC" not in str(article.get("title","")):
        raise ProbeError("4TU article identity mismatch")
    files=get_json(API+"/articles/"+DIRECT_UUID+"/files")
    item=select_official_file([article],files)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_suffix(".partial")
    if temp.exists():
        temp.unlink()
    digest=hashlib.md5()
    total=0
    request=Request(item["download_url"],headers={"User-Agent":"NOVA-DCG-verified-4TU-download/1.0"})
    try:
        with urlopen(request,timeout=180) as response, temp.open("wb") as out:
            if response.status!=200 or not response.geturl().startswith("https://"):
                raise ProbeError("Official archive download was not HTTPS HTTP 200")
            while True:
                block=response.read(4*1024*1024)
                if not block:
                    break
                total+=len(block)
                if total>EXPECTED_SIZE:
                    raise ProbeError("4TU archive exceeded verified byte count")
                digest.update(block)
                out.write(block)
                if total and total%(512*1024*1024)<4*1024*1024:
                    print(f"Streamed {total//(1024*1024)} MiB of source ZIP",flush=True)
        if total!=EXPECTED_SIZE or digest.hexdigest()!=EXPECTED_MD5:
            raise ProbeError(f"4TU archive fingerprint mismatch: size={total} MD5={digest.hexdigest()}")
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return destination


def file_md5(file):
    hasher=hashlib.md5()
    with Path(file).open("rb") as handle:
        for block in iter(lambda:handle.read(4*1024*1024),b""):
            hasher.update(block)
    return hasher.hexdigest()


def _strict_yolo_label(label_file, conversion_log=None):
    """Validate detection labels and convert verified YOLO polygons to boxes.

    Publisher's fold0 contains occasional YOLO segmentation polygons among
    standard 5-column detection boxes. A polygon is exactly one class id plus
    >=3 (x,y) points. Its axis-aligned enclosing rectangle is a legitimate
    detection target, not an estimate of nominal electrical component values.
    Every converted line is recorded in the training source audit.
    """
    import math
    label_file=Path(label_file)
    rows=label_file.read_text(encoding="utf-8").splitlines()
    out=[]
    count=Counter()
    conversions=[]
    for line_number,line in enumerate(rows,1):
        fields=line.split()
        if not fields:
            continue
        try:
            class_id=int(fields[0])
        except (ValueError, IndexError) as exc:
            raise ProbeError(f"Non-numeric YOLO class {label_file.name}:{line_number}") from exc
        if class_id not in range(len(PRESENT_NAMES)):
            raise ProbeError(f"Unrecognised class in {label_file.name}:{line_number}")
        if len(fields)==5:
            try:
                cx,cy,w,h=map(float,fields[1:])
            except ValueError as exc:
                raise ProbeError(f"Non-numeric YOLO box {label_file.name}:{line_number}") from exc
        elif len(fields)>=7 and len(fields)%2==1 and len(fields)<=1001:
            try:
                points=[float(value) for value in fields[1:]]
            except ValueError as exc:
                raise ProbeError(f"Non-numeric YOLO polygon {label_file.name}:{line_number}") from exc
            if not all(math.isfinite(x) and 0<=x<=1 for x in points):
                raise ProbeError(f"Out-of-image polygon coordinate {label_file.name}:{line_number}")
            pairs=list(zip(points[::2],points[1::2]))
            if len(set(pairs))<3:
                raise ProbeError(f"Degenerate YOLO polygon {label_file.name}:{line_number}")
            xs,ys=points[::2],points[1::2]
            xmin,xmax=min(xs),max(xs)
            ymin,ymax=min(ys),max(ys)
            w,h=xmax-xmin,ymax-ymin
            cx,cy=(xmin+xmax)/2,(ymin+ymax)/2
            conversions.append({
                "file":label_file.name,
                "row":line_number,
                "source":"yolo_polygon",
                "points":len(pairs),
                "converted_class":PRESENT_NAMES[class_id],
            })
        else:
            raise ProbeError(f"Malformed YOLO row {label_file.name}:{line_number}: {len(fields)} columns")
        if not all(math.isfinite(value) for value in (cx,cy,w,h)):
            raise ProbeError(f"Non-finite YOLO coordinates {label_file.name}:{line_number}")
        if w<=0 or h<=0 or cx-w/2<-1e-5 or cy-h/2<-1e-5 or \
           cx+w/2>1+1e-5 or cy+h/2>1+1e-5:
            raise ProbeError(f"Out-of-image YOLO label in {label_file.name}:{line_number}")
        count[PRESENT_NAMES[class_id]]+=1
        if len(fields)==5:
            out.append(line.strip())
        else:
            out.append(f"{class_id} {cx:.9f} {cy:.9f} {w:.9f} {h:.9f}")
    if conversions:
        # Only rewrite once the entire original label file has passed all checks.
        label_file.write_text("\n".join(out)+("\n" if out else ""),encoding="utf-8")
    if conversion_log is not None:
        conversion_log.extend(conversions)
    return count


def _verified_coco_categories(z,fold):
    root="PCB_MC/annotations/PCB-MC-C/"
    for split in ("train","valid"):
        name=f"{root}components_only_fold{fold}_{split}_annotations.json"
        try:
            info=z.getinfo(name)
        except KeyError as exc:
            raise ProbeError("Missing original 23-class COCO provenance "+name) from exc
        if info.file_size>300*1024*1024:
            raise ProbeError("COCO provenance record unexpectedly large")
        with z.open(info) as source:
            coco=json.load(source)
        categories=coco.get("categories")
        if not isinstance(categories,list):
            raise ProbeError("Missing 23-class COCO category table")
        ordered=[x["name"] for x in sorted(categories,key=lambda x:x["id"])]
        if ordered!=list(PRESENT_NAMES):
            raise ProbeError("Published COCO class order differs from expected 23 classes")
    return True


def _verify_official_fold_manifest(zipped,fold,files_by_split):
    """Cross-check real ZIP members against the immutable publisher fold list."""
    name="PCB_MC/splits/components_only_splits.json"
    try:
        info=zipped.getinfo(name)
    except KeyError as exc:
        raise ProbeError("Publisher board-aware fold manifest missing") from exc
    if info.file_size>10*1024*1024:
        raise ProbeError("Publisher fold manifest exceeds safe size")
    with zipped.open(info) as source:
        manifest=json.load(source)
    if not isinstance(manifest.get("folds"),list):
        raise ProbeError("Invalid official PCB-MC-C fold manifest")
    fold_rows=[row for row in manifest["folds"] if row.get("fold")==fold]
    if len(fold_rows)!=1:
        raise ProbeError("Requested official board fold missing")
    row=fold_rows[0]
    train=row.get("train_images")
    valid=row.get("valid_images")
    if not isinstance(train,list) or not isinstance(valid,list):
        raise ProbeError("Official fold train/valid lists missing")
    if not all(isinstance(name,str) and name==Path(name).name for name in train+valid):
        raise ProbeError("Official fold contains path-bearing image identifiers")
    if set(train)&set(valid):
        raise ProbeError("Official board fold manifest leaks images across splits")
    for key,expected in (("train",train),("val",valid)):
        actual=set(files_by_split[key]["images"])
        if len(set(expected))!=len(expected) or actual!=set(expected):
            raise ProbeError(f"Published {key} fold images do not match authoritative manifest")
    return True


def extract_official_fold(archive,destination,*,fold=0,full_md5=True):
    """Extract only one immutable published fold, not an improvised random split."""
    if fold not in range(5):
        raise ValueError("Only publisher folds 0..4 are supported")
    archive=Path(archive).resolve()
    if full_md5 and (archive.stat().st_size!=EXPECTED_SIZE or file_md5(archive)!=EXPECTED_MD5):
        raise ProbeError("PCB-MC ZIP has not passed full published MD5 verification")
    destination=Path(destination).resolve()
    if destination==archive.parent or archive in destination.parents:
        raise ValueError("Dataset output may not contain the ZIP itself")
    counts={"train":Counter(),"val":Counter()}
    polygon_conversions={"train":[],"val":[]}
    files_by_split={"train":{"images":{},"labels":{}},"val":{"images":{},"labels":{}}}
    source_prefix=f"PCB_MC/images/PCB-MC-C/kfold_data/fold_{fold}/"
    with ZipFile(archive) as zipped:
        _verified_coco_categories(zipped,fold)
        for info in zipped.infolist():
            if not info.filename.startswith(source_prefix) or info.is_dir():
                continue
            remainder=info.filename[len(source_prefix):]
            parts=remainder.split("/")
            if len(parts)!=3:
                continue
            split,kind,name=parts
            if split not in ("train","valid") or kind not in ("images","labels"):
                continue
            target_split="train" if split=="train" else "val"
            if kind=="images" and Path(name).suffix.lower() not in (".jpg",".jpeg",".png"):
                continue
            if kind=="labels" and Path(name).suffix.lower()!=".txt":
                continue
            if (not name or name.startswith(".") or
                name in (".","..") or "/" in name or "\\" in name):
                raise ProbeError("Unsafe ZIP component file name")
            if info.file_size>MAX_SINGLE_UNCOMPRESSED:
                raise ProbeError("Oversize ZIP image/label entry")
            if name in files_by_split[target_split][kind]:
                raise ProbeError("Duplicate ZIP member within one official fold")
            files_by_split[target_split][kind][name]=info
        _verify_official_fold_manifest(zipped,fold,files_by_split)
        for split in ("train","val"):
            imgs=files_by_split[split]["images"]
            labels=files_by_split[split]["labels"]
            if len(imgs)<80 or len(labels)<80:
                raise ProbeError(f"Publisher fold {split} has unexpectedly few image/label entries")
            imstems={Path(n).stem for n in imgs}
            labstems={Path(n).stem for n in labels}
            if len(imstems)!=len(imgs) or len(labstems)!=len(labels):
                raise ProbeError("Duplicate YOLO image/label stems")
            if imstems!=labstems:
                raise ProbeError(f"Unmatched source image/label names in official {split} fold")
        declared_bytes=sum(info.file_size for split in files_by_split.values()
                           for kind in split.values() for info in kind.values())
        if declared_bytes>MAX_EXTRACTED_TOTAL:
            raise ProbeError("Fold extraction exceeds safe size limit")
        destination.mkdir(parents=True,exist_ok=True)
        for split,data in files_by_split.items():
            for kind,files in data.items():
                folder=destination/kind/split
                folder.mkdir(parents=True,exist_ok=True)
                for name,info in files.items():
                    target=folder/name
                    with zipped.open(info) as source, target.open("wb") as out:
                        shutil.copyfileobj(source,out,1024*1024)
                    if target.stat().st_size!=info.file_size:
                        raise ProbeError("Extracted file size differs from ZIP catalog")
                    if kind=="labels":
                        counts[split].update(_strict_yolo_label(target,polygon_conversions[split]))
    if not counts["train"] or not counts["val"]:
        raise ProbeError("Expected non-empty class labels in train and validation")
    # We use the author's existing YOLO files, not a guessed COCO class index.
    classes=json.dumps(list(PRESENT_NAMES),ensure_ascii=False)
    (destination/"data.yaml").write_text(
        f"path: {destination}\ntrain: images/train\nval: images/val\nnc: 23\nnames: {classes}\n",
        encoding="utf-8",
    )
    audit={
        "source":"PCB-MC-C 23 existing components, official published 5-fold layout",
        "doi":DOI,
        "source_archive_name":EXPECTED_FILENAME,
        "full_zip_md5_verified":bool(full_md5),
        "source_zip_md5":EXPECTED_MD5 if full_md5 else None,
        "official_fold":fold,
        "source_coco_layout":"official_per_fold_train_valid",
        "board_identity_split_from_official_manifest":True,
        "train_count":len(files_by_split["train"]["images"]),
        "val_count":len(files_by_split["val"]["images"]),
        "source_train_images":len(files_by_split["train"]["images"]),
        "source_val_images":len(files_by_split["val"]["images"]),
        "class_order":list(PRESENT_NAMES),
        "labels_per_split":{s:dict(counts[s]) for s in counts},
        "polygon_rows_converted_to_detection_boxes":{
            split:len(items) for split,items in polygon_conversions.items()
        },
        "polygon_conversion_examples":{
            split:items[:25] for split,items in polygon_conversions.items()
        },
        "polygon_conversion_method":"min/max normalized x/y -> enclosing box; original label bytes remain in source ZIP",
        "training_completed":False,
        "live_model_unchanged":True,
    }
    (destination/"import_audit.json").write_text(
        json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    return audit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--zip",required=True,help="Path to the verified official PCB_MC.zip")
    parser.add_argument("--output",required=True)
    parser.add_argument("--fold",type=int,default=0)
    parser.add_argument("--download",action="store_true",help="Download official full 3.77GB 4TU archive if absent")
    args=parser.parse_args()
    source=stream_official_archive(args.zip) if args.download else Path(args.zip)
    print(json.dumps(extract_official_fold(source,args.output,fold=args.fold),
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
