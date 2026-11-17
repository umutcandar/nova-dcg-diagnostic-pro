"""Import published PCB-MC *present-components* COCO with its official board-aware folds.

This is a local/offline converter, NOT a dataset downloader. User must obtain
the CC BY 4.0 research data from the official 4TU deposit, keep source license
and manifests, and verify the original 3.77GB ZIP MD5 before extraction.

An official fold prevents layout leakage. This tool refuses inferred random
splits and preserves 23 source classes, especially "Electrolytic Capacitor"
versus "Capacitor" and "Zener Diode" versus "Diode".
"""
import argparse
import hashlib
import json
import math
import os
import shutil
from collections import Counter
from pathlib import Path
from PIL import Image

SOURCE_DOI = "10.4121/7c6e5bda-eecf-4feb-8a3a-7f823b1b0140.v2"
SOURCE_LICENSE = "CC BY 4.0"
SOURCE_ZIP_MD5 = "1533d1ca6d54c37b19c1a94297c0745c"
PRESENT_NAMES = (
    "Button", "Capacitor", "Clock", "Connector", "Diode",
    "Display", "Electrolytic Capacitor", "EM", "Ferrite Bead",
    "Fuse", "Heatsink", "IC", "Inductor", "Jumper", "LED",
    "Pads", "Pins", "Potentiometer", "Resistor", "Switch",
    "Test Point", "Transistor", "Zener Diode",
)
# Never infer arbitrary mappings. These represent UI names only, not ML class IDs.
NOVA_DISPLAY_NAMES = {
    "Button": "Anahtar", "Capacitor": "Kondansatör", "Clock": "Kristal",
    "Connector": "Konnektör", "Diode": "Diyot", "Display": "Ekran",
    "Electrolytic Capacitor": "Elektrolitik Kondansatör",
    "EM": "EM (belirsiz)", "Ferrite Bead": "Ferrit Boncuk",
    "Fuse": "Sigorta", "Heatsink": "Soğutucu", "IC": "Entegre",
    "Inductor": "Bobin", "Jumper": "Jumper", "LED": "LED",
    "Pads": "Pad", "Pins": "Pin", "Potentiometer": "Trimpot",
    "Resistor": "Direnç", "Switch": "Anahtar", "Test Point": "Test noktası",
    "Transistor": "Transistör", "Zener Diode": "Zener Diyot",
}


def safe_filename(name):
    if not isinstance(name, str) or not name or Path(name).name != name or \
       "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError(f"Unsafe source photo filename: {name!r}")
    return name


def as_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Non-finite/non-numeric COCO label: {value!r}")
    return float(value)


def convert_bbox(rect, width, height):
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        raise ValueError("Expected COCO [x,y,width,height] box")
    x, y, w, h = map(as_number, rect)
    if width <= 0 or height <= 0 or w <= 0 or h <= 0:
        raise ValueError("Invalid COCO box size")
    # Truncate at image edges only within harmless subpixel label rounding.
    if x < -0.5 or y < -0.5 or x+w > width+0.5 or y+h > height+0.5:
        raise ValueError(f"COCO bounding box outside image: {rect!r}")
    x1,y1 = max(0.0,x),max(0.0,y)
    x2,y2 = min(float(width),x+w),min(float(height),y+h)
    if x2<=x1 or y2<=y1:
        raise ValueError("Degenerate COCO box after clipping")
    return ((x1+x2)/(2*width),(y1+y2)/(2*height),(x2-x1)/width,(y2-y1)/height)


def load_coco(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("categories","images","annotations"):
        if not isinstance(data.get(key),list):
            raise ValueError(f"COCO {key} missing")
    catmap={}
    for item in data["categories"]:
        if not isinstance(item, dict) or item.get("id") in catmap:
            raise ValueError("Duplicate/non-dict COCO category")
        catmap[item["id"]]=item.get("name")
    if set(catmap.values()) != set(PRESENT_NAMES) or len(catmap)!=len(PRESENT_NAMES):
        raise ValueError("Dataset categories must exactly match PCB-MC-C 23 present classes")
    id_to_idx={key:PRESENT_NAMES.index(name) for key,name in catmap.items()}
    photos={}
    for item in data["images"]:
        if not isinstance(item,dict) or item.get("id") in photos:
            raise ValueError("Duplicate COCO image ID")
        fname=safe_filename(item.get("file_name"))
        w,h=item.get("width"),item.get("height")
        if not isinstance(w,int) or not isinstance(h,int) or w<1 or h<1:
            raise ValueError(f"Invalid image dimensions for {fname}")
        photos[item["id"]]={"filename":fname,"width":w,"height":h}
    if len({p["filename"] for p in photos.values()}) != len(photos):
        raise ValueError("Duplicate photo filenames")
    by_name={p["filename"]:[] for p in photos.values()}
    seen_annotation_ids=set()
    for annotation in data["annotations"]:
        if not isinstance(annotation,dict) or annotation.get("id") in seen_annotation_ids:
            raise ValueError("Duplicate COCO annotation ID")
        seen_annotation_ids.add(annotation.get("id"))
        cid=annotation.get("category_id")
        pid=annotation.get("image_id")
        if cid not in id_to_idx or pid not in photos:
            raise ValueError("Unknown category or image reference in COCO annotation")
        photo=photos[pid]
        box=convert_bbox(annotation.get("bbox"),photo["width"],photo["height"])
        by_name[photo["filename"]].append((id_to_idx[cid],box))
    return by_name,photos


def select_official_fold(manifest_path,fold_number,labels):
    manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(manifest.get("folds"),list):
        raise ValueError("Official PCB-MC fold manifest missing folds")
    selected=[f for f in manifest["folds"] if f.get("fold")==fold_number]
    if len(selected)!=1:
        raise ValueError(f"Official fold {fold_number} not found exactly once")
    f=selected[0]
    train=f.get("train_images");valid=f.get("valid_images")
    if not isinstance(train,list) or not isinstance(valid,list) or not train or not valid:
        raise ValueError("Both official train and validation photo lists required")
    safe_train=[safe_filename(x) for x in train]
    safe_valid=[safe_filename(x) for x in valid]
    if len(set(safe_train))!=len(safe_train) or len(set(safe_valid))!=len(safe_valid):
        raise ValueError("Duplicate image listed inside an official split")
    if set(safe_train) & set(safe_valid):
        raise ValueError("Official fold has train/validation image leakage")
    missing=(set(safe_train)|set(safe_valid))-set(labels)
    if missing:
        raise ValueError(f"Official split references unannotated images: {sorted(missing)[:4]}")
    return {"train":safe_train,"val":safe_valid}


def import_pcb_mc(images_dir,coco_file,fold_manifest,out_dir,*,fold=0,link=True):
    images=Path(images_dir).resolve()
    out=Path(out_dir).resolve()
    if not images.is_dir():
        raise FileNotFoundError(images)
    if out==images or images in out.parents:
        raise ValueError("Output must not be inside source photo folder")
    labels,photos=load_coco(coco_file)
    selection=select_official_fold(fold_manifest,fold,labels)
    if not selection["train"] or not selection["val"]:
        raise ValueError("Both train and val required")
    counts={"train":Counter(),"val":Counter()}
    for subset,filenames in selection.items():
        imgdir=out/"images"/subset; labdir=out/"labels"/subset
        imgdir.mkdir(parents=True,exist_ok=True)
        labdir.mkdir(parents=True,exist_ok=True)
        for name in filenames:
            source=images/name
            if not source.is_file():
                raise FileNotFoundError(f"Official photo absent: {name}")
            with Image.open(source) as img:
                w,h=img.size
            for photo in photos.values():
                if photo["filename"]==name:
                    if (w,h)!=(photo["width"],photo["height"]):
                        raise ValueError(f"COCO/photo dimensions mismatch: {name}")
                    break
            target=imgdir/name
            if not target.exists():
                if link:
                    target.symlink_to(source)
                else:
                    shutil.copy2(source,target)
            data=labels[name]
            lines=[" ".join([str(cls)]+[f"{x:.9f}" for x in bbox])
                   for cls,bbox in data]
            (labdir/(Path(name).stem+".txt")).write_text(
                "\n".join(lines)+("\n" if lines else ""),encoding="utf-8")
            counts[subset].update(PRESENT_NAMES[cls] for cls,_ in data)
    # A deterministic, explicitly source-scoped class mapping.
    config=("path: "+str(out)+"\ntrain: images/train\nval: images/val\n"
            "names:\n"+"\n".join("  "+str(i)+": "+json.dumps(name,ensure_ascii=False)
                                 for i,name in enumerate(PRESENT_NAMES))+"\n")
    (out/"data.yaml").write_text(config,encoding="utf-8")
    audit={
        "source": "PCB-MC components-only (PCB-MC-C)",
        "doi": SOURCE_DOI,
        "license": SOURCE_LICENSE,
        "source_zip_md5": SOURCE_ZIP_MD5,
        "official_fold": fold,
        "class_count": len(PRESENT_NAMES),
        "class_order": list(PRESENT_NAMES),
        "nova_labels_for_display_only": NOVA_DISPLAY_NAMES,
        "source_train_images": len(selection["train"]),
        "source_val_images": len(selection["val"]),
        "labels_per_split": {name:dict(counts[name]) for name in ("train","val")},
        "board_identity_split_from_official_manifest": True,
        "training_completed": False,
        "warning": "Original ZIP checksum and annotation package must be verified before trusting fold provenance. Publication metadata not independently audited.",
    }
    (out/"import_audit.json").write_text(
        json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    return audit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--images-dir",required=True)
    parser.add_argument("--coco-file",required=True)
    parser.add_argument("--fold-manifest",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--fold",type=int,default=0)
    parser.add_argument("--copy",action="store_true",help="Copy instead of symlink")
    args=parser.parse_args()
    print(json.dumps(import_pcb_mc(
        args.images_dir,args.coco_file,args.fold_manifest,args.output,
        fold=args.fold,link=not args.copy
    ),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
