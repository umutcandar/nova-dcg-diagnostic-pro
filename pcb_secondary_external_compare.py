"""Evaluate real YOLO proposals with an independent local capacitor/diode reviewer.

Uses public 13-photo Wangshnegqi CC BY 4.0 val photos never used to train
the secondary PCB-MC crop model. Object labels are incomplete and only TWO
diodes are annotated: report limitations, don't claim production accuracy.
The reviewer never relabels the main detector automatically.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

from pcb_external_benchmark import parse_labels,box_iou
from pcb_secondary_inference import load_session,evaluate_detections,MAX_REVIEW_CROPS
from web_onnx_detector import detailed_detect
from web_studio import normalize_detections


def compare(dataset,report_path,weights_path,predict=detailed_detect,session=None,
            reviewer=None,model_version="v1"):
    root=Path(dataset)
    images=root/"dataset/images/val"
    labels=root/"dataset/labels/val"
    if not images.is_dir() or not labels.is_dir():
        raise FileNotFoundError("Independent external PCB validation set absent")
    if model_version not in ("v1","v2"):
        raise ValueError("Unknown secondary reviewer model version")
    if reviewer is None:
        if model_version=="v2":
            from pcb_secondary_inference_v2 import examine
            reviewer=examine
        else:
            reviewer=evaluate_detections
    if session is None:
        if model_version=="v2":
            from pcb_secondary_inference_v2 import load_model
            session=load_model(str(Path(report_path).resolve()),str(Path(weights_path).resolve()))
        else:
            session=load_session(str(Path(report_path).resolve()),str(Path(weights_path).resolve()),False)
    rows=[]
    totals=Counter()
    eligible_labels=frozenset(("Kondansatör","Diyot"))
    photos=sorted(x for x in images.iterdir() if x.suffix.lower() in (".jpg",".jpeg",".png"))
    if not photos:raise ValueError("External dataset has no photos")
    for photo in photos:
        annotation=labels/(photo.stem+".txt")
        if not annotation.is_file():
            raise FileNotFoundError(f"External ground-truth missing: {annotation}")
        with Image.open(photo) as opened:
            board=ImageOps.exif_transpose(opened).convert("RGB")
        width,height=board.size
        ground,ignored=parse_labels(annotation,width,height)
        targets=[x for x in ground if x["class"] in eligible_labels]
        totals["target_gt"]+=len(targets)
        totals["target_capacitor_gt"]+=sum(x["class"]=="Kondansatör" for x in targets)
        totals["target_diode_gt"]+=sum(x["class"]=="Diyot" for x in targets)
        predicted=normalize_detections(predict(photo),width,height)
        targets_pred=[x for x in predicted if x["label"] in eligible_labels]
        reviewed=reviewer(board,predicted,session,MAX_REVIEW_CROPS)
        totals["images"]+=1
        totals["all_model_predictions"]+=len(predicted)
        totals["main_cap_diode_predictions"]+=len(targets_pred)
        totals["secondary_reviewed"]+=reviewed
        eligible=[p for p in predicted if p.get("secondary_evidence")]
        totals["secondary_disagreements"]+=sum(
            p["secondary_evidence"]["agrees_with_detector"] is False for p in eligible
        )
        totals["second_model_other"]+=sum(
            p["secondary_evidence"]["label_family"]=="other" for p in eligible
        )
        totals["actionable_secondary_disagreements"]+=sum(
            p["secondary_evidence"].get("actionable_disagreement",False) for p in eligible
        )
        candidates=[]
        for pred_id,pred in enumerate(eligible):
            for truth_id,gt in enumerate(targets):
                value=box_iou(pred["bbox_xyxy_pixels"],gt["box"])
                if value>=.5:
                    candidates.append((value,pred_id,truth_id))
        claimed_predictions=set()
        claimed_truth=set()
        outcomes=[]
        for overlap,pi,ti in sorted(candidates,reverse=True):
            if pi in claimed_predictions or ti in claimed_truth:continue
            claimed_predictions.add(pi)
            claimed_truth.add(ti)
            proposal=eligible[pi]
            truth=targets[ti]
            base_correct=proposal["label"]==truth["class"]
            reviewer_correct=(proposal["secondary_evidence"]["label_family"] ==
                                ("capacitor" if truth["class"]=="Kondansatör" else "diode"))
            conflict=proposal["secondary_evidence"]["agrees_with_detector"] is False
            totals["matched_target_boxes"]+=1
            if base_correct:totals["base_correct_on_matched"]+=1
            if reviewer_correct:totals["secondary_correct_on_matched"]+=1
            if conflict and not base_correct and reviewer_correct:
                totals["helpful_conflicts"]+=1
            if conflict and base_correct:
                totals["false_conflicts_on_correct"]+=1
            if proposal["secondary_evidence"].get("actionable_disagreement"):
                totals["actionable_conflicts_on_matched"]+=1
                if base_correct:
                    totals["actionable_false_alarms_on_correct"]+=1
                elif reviewer_correct:
                    totals["actionable_helpful_conflicts"]+=1
            if proposal["secondary_evidence"]["label_family"]=="other":
                totals["other_on_matched_cap_or_diode"]+=1
            outcomes.append({
                "truth":truth["class"],"model":proposal["label"],
                "secondary":proposal["secondary_evidence"]["label_family"],
                "base_correct":base_correct,
                "secondary_correct":reviewer_correct,
                "conflict":conflict,
                "actionable_conflict":proposal["secondary_evidence"].get("actionable_disagreement",False),
                "overlap":round(overlap,3),
            })
        rows.append({
            "photo":photo.name,
            "gt_cap_diodes":len(targets),
            "yolo_predictions":len(predicted),
            "secondary_crops":reviewed,
            "matched_gt_cap_diodes":len(outcomes),
            "wrong_examples":[x for x in outcomes if not x["base_correct"] or x["conflict"]][:12],
        })
    return {
        "schema":"nova-secondary-external-yolo-crop-eval-v1",
        "status":"external_exploratory_second_model_requires_more_test_boards",
        "data_source":"wangshnegqi/pcb-component-detection-dataset-yolo 13 validation images CC BY 4.0",
        "model_source":"PCB-MC-C fold0 MobileNetV3 independently trained",
        "second_model_version":model_version,
        "method":"YOLO tiled predictions then independent MobileNet crop; IoU >=.5 matching to separate source labels",
        "counts":dict(totals),
        "case_studies":rows,
        "auto_corrected_labels":0,
        "approved_for_live_use":False,
        "limitations":[
            "Only two diode GT boxes on the external 13-photo set. Diode validation statistically inadequate.",
            "The model is binary capacitor vs diode; it does NOT detect other/background false positives.",
            "Only YOLO proposals already classified as capacitor or diode are reviewed (max 32/image).",
            "The independent second model sees imperfect YOLO crops, unlike ideal GT crop training.",
            "Missing source labels mean unmatched detections are not assumed false positives.",
            "No proof of technician-validated user/service boards or production reliability.",
        ],
    }


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset",required=True)
    parser.add_argument("--report",required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--version",choices=("v1","v2"),default="v1")
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    result=compare(args.dataset,args.report,args.model,model_version=args.version)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"counts":result["counts"],"auto_corrected_labels":0,
                      "approved_for_live_use":False},
                     ensure_ascii=False,indent=2))
