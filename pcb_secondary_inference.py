"""Local second PCB vision model: transparent, research-gated crop disagreement aid.

Only enables with a separately evaluated and SHA256-verified local
MobileNetV3 ONNX. No photo is uploaded to an external API. Never changes
the main YOLO class label or technician confirmations. Binary softmax scores
are UNCALIBRATED and cannot establish electrical health or reject false
positive component detections; they merely route disagreement to review.
"""
import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

LABEL_TO_FAMILY = {
    "Kondansatör": "capacitor",
    "Elektrolitik Kondansatör": "capacitor",
    "Diyot": "diode",
    "Zener Diyot": "diode",
}
FAMILIES = ("capacitor","diode")
MEAN = (.485,.456,.406)
STD = (.229,.224,.225)
SIDE = 160
MAX_REVIEW_CROPS = 32


class SecondaryModelError(RuntimeError):
    pass


def verify_artifact(report_path, model_path, require_release=False):
    report=json.loads(Path(report_path).read_text(encoding="utf-8"))
    if report.get("schema")!="nova-independent-capacitor-diode-reviewer-v1":
        raise SecondaryModelError("Unknown independent visual reviewer report")
    if report.get("labels")!=list(FAMILIES):
        raise SecondaryModelError("Unexpected capacitor/diode source class order")
    if report.get("independent_board_disjoint") is not True or (
        report.get("source_audit",{}).get("full_zip_md5_verified") is not True
    ):
        raise SecondaryModelError("Official board-disjoint data evidence missing")
    if require_release and report.get("approved_for_live_use") is not True:
        raise SecondaryModelError("Independent reviewer has no production approval")
    if not require_release and report.get("approved_for_live_use") not in (True,False):
        raise SecondaryModelError("Research/release status unknown")
    m=report.get("model",{})
    file=Path(model_path)
    if m.get("file")!=file.name:
        raise SecondaryModelError("Artifact filename does not match training report")
    if m.get("bytes")!=file.stat().st_size:
        raise SecondaryModelError("Artifact byte count mismatches training report")
    digest=hashlib.sha256()
    with file.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            digest.update(chunk)
    if digest.hexdigest()!=m.get("sha256"):
        raise SecondaryModelError("Independent model SHA256 check failed")
    return report


@lru_cache(maxsize=1)
def load_session(report_path,model_path,require_release=True):
    report=verify_artifact(report_path,model_path,require_release=require_release)
    import onnxruntime as ort
    opt=ort.SessionOptions()
    opt.intra_op_num_threads=1
    opt.inter_op_num_threads=1
    session=ort.InferenceSession(str(Path(model_path)),sess_options=opt,
                                 providers=["CPUExecutionProvider"])
    inp=session.get_inputs()
    out=session.get_outputs()
    if len(inp)!=1 or len(out)!=1 or inp[0].shape != [1,3,SIDE,SIDE]:
        raise SecondaryModelError("Independent model input dimensions changed")
    if out[0].shape != [1,2]:
        raise SecondaryModelError("Independent model output dimensions changed")
    return session


def preprocess_crop(image,box):
    """Same normalized square crop recipe used for the independent training."""
    import numpy as np
    from pcb_secondary_reviewer import crop_region
    cut=crop_region(image,box,side=SIDE)
    img=np.asarray(cut,dtype=np.float32)/255.0
    img=(img-np.asarray(MEAN,dtype=np.float32))/np.asarray(STD,dtype=np.float32)
    return np.ascontiguousarray(img.transpose(2,0,1)[None])


def score_image_region(session,image,box):
    """Return model-relative scores, NOT calibrated real-world probabilities."""
    import numpy as np
    raw=session.run(None,{session.get_inputs()[0].name:preprocess_crop(image,box)})[0]
    logits=np.asarray(raw)
    if logits.shape!=(1,2) or not np.isfinite(logits).all():
        raise SecondaryModelError("Invalid independent ONNX model output")
    stable=logits[0]-float(np.max(logits[0]))
    scores=np.exp(stable)
    scores=scores/float(np.sum(scores))
    return {family:round(float(scores[i]),5) for i,family in enumerate(FAMILIES)}


def evaluate_detections(image,detections,session,limit=MAX_REVIEW_CROPS):
    """Only annotate disagreement; never auto-correct the detector's label."""
    if limit<1 or limit>MAX_REVIEW_CROPS:
        raise ValueError("Invalid number of reviewable candidates")
    if not isinstance(detections,list):
        raise ValueError("Expected detection list")
    width,height=image.size
    candidates=[(i,d) for i,d in enumerate(detections)
                if isinstance(d,dict) and d.get("label") in LABEL_TO_FAMILY
                and d.get("verified") is not True]
    # Favor already-uncertain predictions; bounded CPU work.
    candidates.sort(key=lambda p:(not p[1].get("review_required",False),
                                   p[1].get("confidence") or 0))
    detailed=0
    for index,region in candidates[:limit]:
        bbox=region.get("bbox_xyxy_pixels")
        if not isinstance(bbox,(tuple,list)) or len(bbox)!=4:
            continue
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in bbox):
            continue
        x1,y1,x2,y2=bbox
        if not (0<=x1<x2<=width and 0<=y1<y2<=height):
            continue
        cx=(x1+x2)/(2*width)
        cy=(y1+y2)/(2*height)
        bw=(x2-x1)/width
        bh=(y2-y1)/height
        scores=score_image_region(session,image,(cx,cy,bw,bh))
        proposed=max(scores,key=scores.get)
        original=LABEL_TO_FAMILY[region["label"]]
        conflict=original!=proposed
        evidence={
            "model":"independent_mobilenetv3_crop_reviewer",
            "scope":"capacitor_vs_diode_only",
            "label_family":proposed,
            "relative_scores":scores,
            "agrees_with_detector":not conflict,
            "technician_verified":False,
            "no_electrical_health_claim":True,
            "note":"Relative visual model scores; not calibrated probabilities.",
        }
        region["secondary_evidence"]=evidence
        if conflict:
            region["review_required"]=True
            prior=region.get("review_note","")
            message="İkinci görsel model farklı parça ailesi öneriyor; manuel kontrol gerekli."
            region["review_note"]=(prior+" "+message).strip()[:300]
        detailed+=1
    return detailed


def run_if_approved(image_path,detections):
    """Production-off by default; no API key or external image transfer."""
    if os.environ.get("NOVA_SECONDARY_REVIEWER_ENABLED")!="1":
        return {"state":"not_enabled","candidates_reviewed":0}
    model_path=os.environ.get("NOVA_SECONDARY_MODEL_PATH","")
    report_path=os.environ.get("NOVA_SECONDARY_REPORT_PATH","")
    if not model_path or not report_path:
        return {"state":"not_configured","candidates_reviewed":0}
    try:
        session=load_session(str(Path(report_path).resolve()),
                             str(Path(model_path).resolve()),True)
        with Image.open(image_path) as opened:
            image=ImageOps.exif_transpose(opened).convert("RGB")
        reviewed=evaluate_detections(image,detections,session)
        return {"state":"independent_reviewer_used","candidates_reviewed":reviewed}
    except (OSError,ValueError,SecondaryModelError,RuntimeError):
        # Do not block normal PCB analysis on optional second-model failure.
        return {"state":"reviewer_unavailable","candidates_reviewed":0}
