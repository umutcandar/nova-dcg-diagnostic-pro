"""NOVA DCG second-AI release gate: automatically HOLD unsafe research models.

This is an evidence gate, not another classifier. Production promotion is
ALWAYS a separate explicitly reviewed step. A small, incomplete source
validation cannot certify real PCB field accuracy or electrical health.
"""
import argparse
import json
from pathlib import Path


def evaluate(name,report):
    if not isinstance(report,dict) or report.get("auto_corrected_labels")!=0:
        raise ValueError("Unsafe or unrecognized second-AI audit")
    counts=report.get("counts")
    if not isinstance(counts,dict):
        raise ValueError("Missing independent real-photo metric counts")
    if report.get("approved_for_live_use") is not False:
        raise ValueError("Research audit must have no live release approval")
    minimums={
        "target_diode_gt":30,
        "target_capacitor_gt":100,
        "matched_target_boxes":100,
        "actionable_helpful_conflicts":5,
    }
    blockers=[]
    for field,minimum in minimums.items():
        actual=counts.get(field,0)
        if not isinstance(actual,int) or actual<minimum:
            blockers.append(f"{field}: {actual} (required at least {minimum})")
    correct=max(1,counts.get("base_correct_on_matched",0))
    false_alarms=counts.get("actionable_false_alarms_on_correct",0)
    false_rate=false_alarms/correct
    if false_rate>.05:
        blockers.append(f"actionable false-alarm rate {false_rate:.3f} > 0.050")
    benefit=counts.get("actionable_helpful_conflicts",0)-false_alarms
    if benefit<=0:
        blockers.append(f"net actionable benefit must be positive; observed {benefit}")
    # Training source is published and separately held out, but does not
    # establish the independent 13-photo test's physical board identity.
    blockers.append("Unseen NOVA technician-verified real boards have not been evaluated.")
    blockers.append("Binary/three-way crop model cannot establish no-component background false positives.")
    blockers.append("Commercial distribution/service licensing check required.")
    return {
        "name":name,
        "verdict":"HOLD_NOT_APPROVED",
        "automatic_model_promotion":False,
        "detector_21class_unchanged":True,
        "actionable_false_alarm_rate":round(false_rate,4),
        "net_actionable_benefit":benefit,
        "blockers":blockers,
        "counts":counts,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--v1",required=True)
    parser.add_argument("--v2",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    reports={
        "binary_reviewer_v1":json.loads(Path(args.v1).read_text(encoding="utf-8")),
        "three_family_reviewer_v2":json.loads(Path(args.v2).read_text(encoding="utf-8")),
    }
    decision={
        "schema":"nova-secondary-model-release-hold-v1",
        "results":[evaluate(name,r) for name,r in reports.items()],
        "automatic_deployment_permitted":False,
        "recommended_next_training_step":"Add real background/non-component negative crops, more diodes from distinct boards and independently validate on actual YOLO boxes.",
    }
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(decision,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
