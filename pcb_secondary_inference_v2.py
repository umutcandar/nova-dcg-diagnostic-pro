"""Independent three-way PCB reviewer inference: capacitor / diode / OTHER.

Research-only unless independently audited and explicitly released.
The "other" class contains other ANNOTATED components, not background
negatives; no claim of automatic false-positive elimination or health test.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from pcb_secondary_inference import (
    LABEL_TO_FAMILY,MAX_REVIEW_CROPS,SecondaryModelError,
    preprocess_crop
)

LABELS=("capacitor","diode","other")


def verify_model(report,model):
    data=json.loads(Path(report).read_text(encoding="utf-8"))
    if data.get("schema")!="nova-independent-capacitor-diode-other-reviewer-v2":
        raise SecondaryModelError("Unexpected three-class evidence schema")
    if data.get("labels")!=list(LABELS):
        raise SecondaryModelError("Independent source class order mismatch")
    audit=data.get("source_audit",{})
    if audit.get("full_zip_md5_verified") is not True or (
        audit.get("board_identity_split_from_official_manifest") is not True
    ):
        raise SecondaryModelError("Publisher board-level dataset provenance missing")
    if data.get("approved_for_live_use") is not False:
        raise SecondaryModelError("This research artifact must not be production-approved")
    info=data.get("model",{})
    if info.get("file")!=Path(model).name or info.get("bytes")!=Path(model).stat().st_size:
        raise SecondaryModelError("Independent ONNX artifact filename or size mismatch")
    hasher=hashlib.sha256()
    with Path(model).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            hasher.update(chunk)
    if hasher.hexdigest()!=info.get("sha256"):
        raise SecondaryModelError("Independent ONNX artifact SHA256 mismatch")
    return data


@lru_cache(maxsize=1)
def load_model(report,model):
    verify_model(report,model)
    import onnxruntime as ort
    options=ort.SessionOptions()
    options.intra_op_num_threads=1
    options.inter_op_num_threads=1
    session=ort.InferenceSession(str(model),sess_options=options,providers=["CPUExecutionProvider"])
    if len(session.get_inputs())!=1 or session.get_inputs()[0].shape!=[1,3,160,160]:
        raise SecondaryModelError("Unexpected three-way input shape")
    if len(session.get_outputs())!=1 or session.get_outputs()[0].shape!=[1,3]:
        raise SecondaryModelError("Unexpected three-way output shape")
    return session


def family_scores(session,image,box):
    import numpy as np
    arr=session.run(None,{session.get_inputs()[0].name:preprocess_crop(image,box)})[0]
    scores=np.asarray(arr)
    if scores.shape!=(1,3) or not np.isfinite(scores).all():
        raise SecondaryModelError("Bad independent ONNX logits")
    exp=np.exp(scores[0]-float(np.max(scores[0])))
    normalized=exp/float(np.sum(exp))
    return {key:round(float(normalized[i]),5) for i,key in enumerate(LABELS)}


def examine(image,detections,session,limit=MAX_REVIEW_CROPS):
    """Only draw attention to conflicts; DO NOT change detector label."""
    if not isinstance(detections,list) or not 1<=limit<=MAX_REVIEW_CROPS:
        raise ValueError("Invalid reviewer input")
    width,height=image.size
    eligible=[
        det for det in detections
        if isinstance(det,dict) and det.get("label") in LABEL_TO_FAMILY
        and det.get("verified") is not True
    ]
    eligible.sort(key=lambda x:(not x.get("review_required",False),
                                x.get("confidence") or 0))
    reviewed=0
    for det in eligible[:limit]:
        bbox=det.get("bbox_xyxy_pixels")
        if not isinstance(bbox,(list,tuple)) or len(bbox)!=4:
            continue
        import math
        if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in bbox):
            continue
        x1,y1,x2,y2=bbox
        if not (0<=x1<x2<=width and 0<=y1<y2<=height):
            continue
        box=((x1+x2)/(2*width),(y1+y2)/(2*height),(x2-x1)/width,(y2-y1)/height)
        scores=family_scores(session,image,box)
        preferred=max(scores,key=scores.get)
        base_family=LABEL_TO_FAMILY[det["label"]]
        agrees=preferred==base_family
        strong_conflict=(not agrees and scores[preferred]>=.78 and
                         scores[preferred]-scores[base_family]>=.45)
        evidence={
            "model":"independent_mobilenetv3_three_family_reviewer",
            "scope":"capacitor_diode_or_other_annotated_component",
            "label_family":preferred,
            "relative_scores":scores,
            "agrees_with_detector":agrees,
            "actionable_disagreement":strong_conflict,
            "technician_verified":False,
            "no_electrical_health_claim":True,
            "note":"Uncalibrated score on cropped component; NOT background/fault diagnosis.",
        }
        det["secondary_evidence"]=evidence
        if strong_conflict:
            det["review_required"]=True
            msg=("İkinci model başka bir komponent ailesi önerdi; kontrol et."
                 if preferred!="other" else
                 "İkinci model bu bölgenin başka bir komponent olabileceğini düşünüyor; kontrol et.")
            det["review_note"]=(det.get("review_note","")+" "+msg).strip()[:300]
        reviewed+=1
    return reviewed
