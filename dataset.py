"""Validate manually labeled PCB regions and export YOLO training labels.

No automatic detection or model training is performed by this module.
"""
import json
from pathlib import Path

CLASSES = ["Direnç", "Kondansatör", "Diyot", "Entegre", "Transistör", "Bobin", "Konnektör", "Bilinmiyor"]

def validate_annotation(data):
    if data.get("coordinate_system") != "xyxy_normalized":
        raise ValueError("Expected xyxy_normalized coordinates")
    if not isinstance(data.get("regions"), list):
        raise ValueError("Missing regions list")
    output=[]
    for index, region in enumerate(data["regions"], 1):
        label=region.get("label")
        box=region.get("bbox_xyxy_normalized")
        if label not in CLASSES:
            raise ValueError(f"Region {index}: unknown label {label!r}")
        if not isinstance(box, list) or len(box) != 4 or any(type(v) not in (int,float) for v in box):
            raise ValueError(f"Region {index}: invalid box")
        x1,y1,x2,y2=box
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError(f"Region {index}: coordinates out of range")
        output.append((CLASSES.index(label), (x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1))
    return output

def export_yolo(annotation_json, output_txt):
    data=json.loads(Path(annotation_json).read_text(encoding="utf-8"))
    rows=validate_annotation(data)
    lines=[" ".join([str(cls), *(f"{v:.6f}" for v in box)]) for cls,*box in rows]
    Path(output_txt).write_text("\n".join(lines)+("\n" if lines else ""), encoding="utf-8")
    return len(rows)

def main():
    import argparse
    parser=argparse.ArgumentParser(description="Validate NOVA DCG labels and export YOLO txt")
    parser.add_argument("annotation_json")
    parser.add_argument("output_txt")
    args=parser.parse_args()
    print(f"Exported {export_yolo(args.annotation_json,args.output_txt)} labels")

if __name__=="__main__":
    main()
