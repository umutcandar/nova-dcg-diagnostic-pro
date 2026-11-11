"""Prepare an auditable PCB dataset from manual annotations.

Splits by board ID to reduce leakage. No training or downloads.
"""
import argparse
import hashlib
import json
import random
import shutil
from collections import Counter
from pathlib import Path
from dataset import validate_annotation, CLASSES

def prepare(source_dir, output_dir, seed=42):
    source=Path(source_dir).resolve()
    out=Path(output_dir).resolve()
    if source==out or source in out.parents and out.name=="annotations":
        raise ValueError("Choose a separate output directory")
    if not source.is_dir():
        raise FileNotFoundError(source)
    records=[]
    for annotation in sorted(source.rglob("*.json")):
        data=json.loads(annotation.read_text(encoding="utf-8"))
        if "regions" not in data:
            continue
        labels=validate_annotation(data)
        image=Path(data["image"])
        if not image.is_absolute():
            image=(annotation.parent/image).resolve()
        if not image.is_file():
            raise FileNotFoundError(f"Missing image: {image}")
        board_id=str(data.get("board_id","")).strip()
        if not board_id:
            raise ValueError(f"board_id required to avoid train/test leakage: {annotation}")
        records.append((annotation,image,board_id,labels))
    if not records:
        raise ValueError("No annotated images found")
    groups=sorted(set(r[2] for r in records))
    if len(groups)<3:
        raise ValueError("At least three distinct board_id values are required for train/val/test")
    rng=random.Random(seed)
    rng.shuffle(groups)
    n=len(groups)
    ntest=max(1,round(n*0.15))
    nval=max(1,round(n*0.15))
    if n-ntest-nval<1:
        raise ValueError("Not enough boards for a training split")
    split_map={board:("test" if i<ntest else "val" if i<ntest+nval else "train")
               for i,board in enumerate(groups)}
    summary={"boards":len(groups),"images":len(records),"splits":{},"classes":CLASSES,
             "warning":"Manual labels require human review before training."}
    for split in ("train","val","test"):
        (out/"images"/split).mkdir(parents=True,exist_ok=True)
        (out/"labels"/split).mkdir(parents=True,exist_ok=True)
        summary["splits"][split]={"images":0,"boards":len([x for x in groups if split_map[x]==split]),"labels":{}}
    for annotation,image,board,labels in records:
        split=split_map[board]
        key=hashlib.sha256(str(annotation).encode()).hexdigest()[:12]
        name=f"{annotation.stem}_{key}"
        destination=out/"images"/split/(name+image.suffix.lower())
        shutil.copy2(image,destination)
        lines=[]
        for cls,cx,cy,w,h in labels:
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            counts=summary["splits"][split]["labels"]
            counts[CLASSES[cls]]=counts.get(CLASSES[cls],0)+1
        (out/"labels"/split/(name+".txt")).write_text("\n".join(lines)+("\n" if lines else ""),encoding="utf-8")
        summary["splits"][split]["images"]+=1
    yaml_lines=["path: "+str(out),"train: images/train","val: images/val","test: images/test",
                "names:"]+[f"  {i}: '{name}'" for i,name in enumerate(CLASSES)]
    (out/"data.yaml").write_text("\n".join(yaml_lines)+"\n",encoding="utf-8")
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--seed",type=int,default=42)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source_dir,args.output_dir,args.seed),ensure_ascii=False,indent=2))
