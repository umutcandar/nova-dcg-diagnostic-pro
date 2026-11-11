"""Validate component detections and export a reviewable image/JSON.

Works with a supplied compatible YOLO checkpoint; no weights bundled.
"""
import argparse
import json
import math
from pathlib import Path

def filter_detections(items,image_size,threshold=0.45):
    width,height=image_size
    if not 0<=threshold<=1:
        raise ValueError("Threshold must be 0..1")
    accepted=[]
    rejected=[]
    for item in items:
        try:
            box=[float(x) for x in item["bbox_xyxy_pixels"]]
            confidence=float(item["confidence"])
            if len(box)!=4 or not all(math.isfinite(x) for x in box+[confidence]):
                raise ValueError("Non-finite coordinate")
            x1,y1,x2,y2=box
            if not (0<=x1<x2<=width and 0<=y1<y2<=height and 0<=confidence<=1):
                raise ValueError("Invalid bounding box")
            if confidence<threshold:
                rejected.append({"detection":item,"reason":"low_confidence"})
                continue
            accepted.append({**item,"bbox_xyxy_pixels":box,"confidence":confidence,
                             "verified":False})
        except (KeyError,TypeError,ValueError) as exc:
            rejected.append({"detection":item,"reason":str(exc)})
    return accepted,rejected

def review_image(image_path,weights_path,output_dir,threshold=0.45):
    from PIL import Image,ImageDraw
    from model_inference import detect_components
    image=Image.open(image_path).convert("RGB")
    detected=detect_components(image_path,weights_path,confidence=0.01)
    accepted,rejected=filter_detections(detected,image.size,threshold)
    folder=Path(output_dir)
    folder.mkdir(parents=True,exist_ok=True)
    marked=image.copy()
    draw=ImageDraw.Draw(marked)
    for index,item in enumerate(accepted,1):
        box=item["bbox_xyxy_pixels"]
        draw.rectangle(box,outline="red",width=max(2,image.width//350))
        draw.text((box[0],max(0,box[1]-15)),f"{index} {item['label']} {item['confidence']:.2f}",fill="red")
    marked.save(folder/"detections_review.png")
    (folder/"detections.json").write_text(json.dumps(accepted,ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"rejected.json").write_text(json.dumps(rejected,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"accepted":len(accepted),"rejected":len(rejected),
            "image":str(folder/"detections_review.png"),"json":str(folder/"detections.json")}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--image",required=True)
    p.add_argument("--weights",required=True)
    p.add_argument("--output",default="review_output")
    p.add_argument("--confidence",type=float,default=0.45)
    args=p.parse_args()
    print(json.dumps(review_image(args.image,args.weights,args.output,args.confidence),ensure_ascii=False))
