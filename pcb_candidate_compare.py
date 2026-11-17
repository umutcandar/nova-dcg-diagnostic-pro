"""Compare experimental 10-class ONNX vs live 21-class on IDENTICAL labeled PCB photos.

The experimental model is *only* an auxiliary research candidate. It never
changes the deployed NOVA web model. Both model outputs are measured with
the same IoU>=0.5, confidence>=0.28, six-common-class scoring contract.
Source validation photographs are small (13) and not board-disjoint certified.
"""
import argparse
import ast
import json
import math
from pathlib import Path

from PIL import Image, ImageOps

from pcb_external_benchmark import benchmark, SURE_CLASS_MAP
from pcb_train_candidate import NAMES
from web_onnx_detector import detailed_detect, automatic_detect, _iou

LABEL_MAP = {
    0: "Direnç",
    1: "Kondansatör",
    2: "Diyot",
    3: "LED",
    4: "Entegre",
    5: "Konnektör",
    6: "Anahtar (karışık)",
    7: "Header",
    8: "Kristal",
    9: "Test noktası",
}
COMMON_CLASSES = tuple(SURE_CLASS_MAP[k][1] for k in sorted(SURE_CLASS_MAP))


def verify_candidate(model_dir):
    """Reject missing, altered, class-drifted, or supposedly approved artifacts."""
    from pcb_train_candidate import sha256
    directory = Path(model_dir)
    report = json.loads((directory / "training_report.json").read_text(encoding="utf-8"))
    checkpoint = report.get("export") or {}
    if report.get("trained") is not True or report.get("approved_for_live_use") is not False:
        raise ValueError("Experimental training report must be completed and explicitly non-production")
    names = report.get("source_audit", {}).get("annotations", {}).get("train", {})
    if not all(label in names for label in NAMES):
        raise ValueError("Candidate training report has unknown class taxonomy")
    if report.get("source_audit", {}).get("pinned_source_sha") != \
            "0d7ae7310fa607389779b6132285336ad73e96e1":
        raise ValueError("Training data provenance changed")
    file = directory / str(checkpoint.get("file", "missing.onnx"))
    if not file.is_file() or file.suffix != ".onnx":
        raise FileNotFoundError("Candidate ONNX artifact missing")
    if sha256(file) != checkpoint.get("sha256") or file.stat().st_size != checkpoint.get("bytes"):
        raise ValueError("Candidate ONNX digest/size does not match actual training report")
    return file, report


def decode_candidate(output, w, h, scale, px, py, min_conf=.28):
    import numpy as np
    raw = np.asarray(output)
    if raw.shape == (1, 14, 8400):
        raw = raw[0].T
    elif raw.shape == (1, 8400, 14):
        raw = raw[0]
    else:
        raise ValueError(f"Unknown candidate ONNX output shape: {raw.shape}")
    if not np.isfinite(raw).all():
        raise ValueError("Candidate output has non-finite scores")
    score=raw[:,4:]
    labels=score.argmax(axis=1)
    confidence=score[np.arange(len(score)),labels]
    mask=confidence>=min_conf
    if not mask.any():
        return []
    boxes=raw[mask,:4]
    scores=score[mask];labels=labels[mask];confidence=confidence[mask]
    x1=(boxes[:,0]-boxes[:,2]/2-px)/scale
    y1=(boxes[:,1]-boxes[:,3]/2-py)/scale
    x2=(boxes[:,0]+boxes[:,2]/2-px)/scale
    y2=(boxes[:,1]+boxes[:,3]/2-py)/scale
    rect=np.stack((x1,y1,x2,y2),axis=1)
    rect[:,(0,2)]=np.clip(rect[:,(0,2)],0,w)
    rect[:,(1,3)]=np.clip(rect[:,(1,3)],0,h)
    legal=(rect[:,2]-rect[:,0]>=2)&(rect[:,3]-rect[:,1]>=2)
    rect=rect[legal];scores=scores[legal];labels=labels[legal];confidence=confidence[legal]
    chosen=[]
    for i in np.argsort(confidence)[::-1]:
        if any(labels[i]==labels[j] and _iou(rect[i],rect[j:j+1])[0]>.48 for j in chosen):
            continue
        chosen.append(int(i))
        if len(chosen)>=200:
            break
    result=[]
    for i in chosen:
        idx=int(labels[i])
        result.append({
            "label":LABEL_MAP[idx],
            "source_label":NAMES[idx],
            "confidence":float(confidence[i]),
            "bbox_xyxy_pixels":rect[i].astype(float).tolist(),
            "alternatives":[
                {"label":LABEL_MAP[int(index)],"confidence":float(scores[i,index])}
                for index in np.argsort(scores[i])[::-1][:3]
                if scores[i,index]>=.08
            ],
        })
    return sorted(result,key=lambda x:(x["bbox_xyxy_pixels"][1],x["bbox_xyxy_pixels"][0]))


class CandidateDetector:
    def __init__(self,model_dir):
        path,self.report=verify_candidate(model_dir)
        import onnxruntime as ort
        options=ort.SessionOptions()
        options.intra_op_num_threads=1
        options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=["CPUExecutionProvider"])
        inputs=self.session.get_inputs()
        outputs=self.session.get_outputs()
        if len(inputs)!=1 or inputs[0].shape!=[1,3,640,640]:
            raise ValueError("Unexpected candidate ONNX input shape")
        if len(outputs)!=1 or outputs[0].shape not in ([1,14,8400],[1,8400,14]):
            raise ValueError("Unexpected candidate ONNX output shape")
        md=self.session.get_modelmeta().custom_metadata_map
        names=ast.literal_eval(md.get("names",""))
        source_names=tuple(names[i] for i in range(len(names))) if isinstance(names,dict) else tuple(names)
        if source_names != tuple(NAMES):
            raise ValueError("Candidate ONNX class metadata differs from trained 10-class labels")

    def __call__(self,photo):
        import numpy as np
        with Image.open(photo) as img:
            board=ImageOps.exif_transpose(img).convert("RGB")
        w,h=board.size
        scale=min(640/w,640/h)
        nw,nh=round(w*scale),round(h*scale)
        px,py=(640-nw)//2,(640-nh)//2
        canvas=Image.new("RGB",(640,640),(114,114,114))
        canvas.paste(board.resize((nw,nh),Image.Resampling.BILINEAR),(px,py))
        input=np.asarray(canvas,dtype=np.float32).transpose(2,0,1)[None]/255.
        raw=self.session.run(None,{self.session.get_inputs()[0].name:input})[0]
        return decode_candidate(raw,w,h,scale,px,py)


def compare(dataset_dir,model_dir):
    candidate=CandidateDetector(model_dir)
    reports={
        "old_standard":benchmark(dataset_dir,predict=automatic_detect),
        "old_tiled":benchmark(dataset_dir,predict=detailed_detect),
        "candidate10_standard":benchmark(dataset_dir,predict=candidate),
    }
    if len({r["counts"]["ground_truth"] for r in reports.values()})!=1:
        raise ValueError("Inconsistent compared ground-truth label coverage")
    totals={
        tag:{
            "source_images":report["counts"]["images"],
            "gt_objects":report["counts"]["ground_truth"],
            "located":report["counts"]["matched_boxes"],
            "correct_class":report["counts"]["correct_class"],
            "localized_recall":report["localization_recall"],
            "correct_class_recall":report["correct_label_recall"],
            "capacitor_recall":report["classes"]["Kondansatör"]["correct_class_recall_at_iou_0_5"],
            "diode_recall":report["classes"]["Diyot"]["correct_class_recall_at_iou_0_5"],
        }
        for tag,report in reports.items()
    }
    # Do not auto-enable model based on this val set alone, regardless of outcome.
    return {
        "status":"exploratory_holdout_not_certified",
        "shared_dataset":"wangshnegqi/pcb-component-detection-dataset-yolo original validation",
        "training_artifact_sha256":candidate.report["export"]["sha256"],
        "same_threshold_iou":0.5,
        "same_threshold_confidence":0.28,
        "summary":totals,
        "full_reports":reports,
        "production_model_unchanged":True,
        "promotion_approved":False,
        "warnings":[
            "Source validation photographs were used during candidate training for model selection.",
            "This is a 13-image set without independently verified disjoint board identities.",
            "The candidate knows only 10 source classes; it is not a 21-class detector replacement.",
            "Absolute correct-class recall and official Ultralytics mAP measure different things.",
            "License and full unseen-board tests required for production, independent of these numbers.",
        ],
    }


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset",required=True)
    ap.add_argument("--candidate",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    obj=compare(args.dataset,args.candidate)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(obj["summary"],ensure_ascii=False,indent=2))
