"""Independent PCB second vision AI v2: capacitor, diode, OTHER/background-like components.

Why v2: a forced binary capacitor/diode reviewer generated false review alarms
on actual YOLO boxes. This additional "other component" family can abstain
from the binary choice. It is NOT a full background detector; candidate
component boxes can still be false positives. Never auto-relabel.

Uses 4TU PCB-MC-C board-aware fold 0. Preserve *all* rare electrolyte and
Zener examples; sample common categories with a deterministic budget.
"""
import argparse
import json
import math
import random
from collections import Counter,defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from pcb_mc_import import PRESENT_NAMES
from pcb_mc_train import validate_fold
from pcb_secondary_reviewer import (
    SIDE,RESEARCH_SEED,parse_box_label,precache_crops,make_dataset,sha256
)

CLASSES = ("capacitor","diode","other")
CAP_IDS = (1,6)
DIODE_IDS = (4,22)
OTHERS = tuple(i for i in range(len(PRESENT_NAMES))
               if i not in CAP_IDS and i not in DIODE_IDS)


def choose_dataset(root,split,seed=RESEARCH_SEED):
    root=Path(root)
    files=sorted((root/"images"/split).glob("*"))
    by_source=defaultdict(list)
    source_counts=Counter()
    for photo in files:
        if photo.suffix.lower() not in (".jpg",".jpeg",".png"):continue
        labels=root/"labels"/split/(photo.stem+".txt")
        if not labels.is_file():raise FileNotFoundError(labels)
        for line_number,line in enumerate(labels.read_text(encoding="utf-8").splitlines(),1):
            if not line.strip():continue
            i,box=parse_box_label(line,f"{photo.name}:{line_number}")
            if i in CAP_IDS: group=0
            elif i in DIODE_IDS: group=1
            else:group=2
            by_source[i].append((photo,box,group,i))
            source_counts[PRESENT_NAMES[i]]+=1
    rng=random.Random(seed)
    def select(source,limit):
        values=by_source[source]
        return list(values) if len(values)<=limit else rng.sample(values,limit)

    cap_limit=1400 if split=="train" else 450
    # Preserve every rare electrolytic capacitor; fill with common caps.
    cap_electro=select(6,cap_limit)
    cap_regular=select(1,max(0,cap_limit-len(cap_electro)))
    # Preserve all annotated diode and Zener examples; 54 in validation.
    diode=list(by_source[4])+list(by_source[22])
    # Other-category quota prevents the dominant IC/resistor classes from
    # eliminating ferrite beads, fuses, transistors, pads, etc.
    other_quota=95 if split=="train" else 32
    other=[]
    for source_id in OTHERS:
        other.extend(select(source_id,other_quota))
    rows=cap_electro+cap_regular+diode+other
    rng.shuffle(rows)
    totals=Counter(row[2] for row in rows)
    if totals[0]<100 or totals[1]<30 or totals[2]<100:
        raise ValueError(f"Insufficient independent three-class source support: {dict(totals)}")
    return rows,{
        "source_label_instances":dict(source_counts),
        "sampled_by_family":{CLASSES[i]:totals[i] for i in range(3)},
        "electrolytic_examples_preserved":len(cap_electro),
        "zener_examples_preserved":len(by_source[22]),
        "other_source_classes":len([i for i in OTHERS if by_source[i]]),
    }


def score(expected,predicted,records):
    if len(expected)!=len(predicted) or len(records)!=len(expected):
        raise ValueError("Predicted/validation example count mismatch")
    confusion=[[0]*3 for _ in range(3)]
    subgroup=defaultdict(lambda:Counter())
    for y,p,item in zip(expected,predicted,records):
        if y not in (0,1,2) or p not in (0,1,2):
            raise ValueError("Unsupported class prediction")
        confusion[y][p]+=1
        source=items_source_name(item)
        subgroup[source]["gt"]+=1
        if y==p:subgroup[source]["correct"]+=1
    rows={}
    for i,name in enumerate(CLASSES):
        tp=confusion[i][i]
        gt=sum(confusion[i])
        proposed=sum(row[i] for row in confusion)
        precision=tp/proposed if proposed else 0.0
        recall=tp/gt if gt else 0.0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
        rows[name]={
            "gt":gt,"tp":tp,"precision":round(precision,4),
            "recall":round(recall,4),"f1":round(f1,4),
        }
    return {
        "by_family":rows,
        "confusion_matrix":confusion,
        "macro_f1":round(sum(row["f1"] for row in rows.values())/3,4),
        "source_label_accuracy":{
            name:{"gt":counts["gt"],"correct":counts["correct"],
                  "accuracy":round(counts["correct"]/counts["gt"],4)}
            for name,counts in subgroup.items()
        },
        "validation_examples":len(expected),
    }


def items_source_name(record):
    return PRESENT_NAMES[record[3]]


def train(prepared,output,epochs=12,batch_size=32,device="cpu"):
    if not isinstance(epochs,int) or not 1<=epochs<=100:raise ValueError("epochs range 1..100")
    if not isinstance(batch_size,int) or not 2<=batch_size<=128:raise ValueError("batch size range 2..128")
    audit=validate_fold(prepared)
    if audit.get("full_zip_md5_verified") is not True or audit.get("official_fold")!=0:
        raise ValueError("Official MD5-verified publisher fold0 required")
    train_records,train_summary=choose_dataset(prepared,"train")
    val_records,val_summary=choose_dataset(prepared,"val")
    if set(r[0] for r in train_records)&set(r[0] for r in val_records):
        raise ValueError("Physical photo appears in both source splits")

    import torch
    from torch import nn
    from torch.utils.data import DataLoader,WeightedRandomSampler
    from torchvision.models import MobileNet_V3_Small_Weights,mobilenet_v3_small
    torch.manual_seed(RESEARCH_SEED)
    torch.set_num_threads(2)
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    cached_train=precache_crops(train_records,output/"crops/train")
    cached_val=precache_crops(val_records,output/"crops/val")
    training=make_dataset(cached_train,True)
    validation=make_dataset(cached_val,False)
    counts=Counter(row[2] for row in train_records)
    sampler=WeightedRandomSampler(
        [1/counts[x[2]] for x in train_records],num_samples=len(train_records),
        replacement=True,generator=torch.Generator().manual_seed(RESEARCH_SEED)
    )
    loader=DataLoader(training,batch_size=batch_size,sampler=sampler,num_workers=0)
    evaluator=DataLoader(validation,batch_size=batch_size,shuffle=False,num_workers=0)
    model=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    for weight in model.features.parameters():weight.requires_grad_(False)
    model.classifier[3]=nn.Linear(model.classifier[3].in_features,len(CLASSES))
    model=model.to(device)
    optimizer=torch.optim.AdamW(model.classifier.parameters(),lr=.001,weight_decay=.012)
    loss_fn=nn.CrossEntropyLoss(label_smoothing=.02)
    history=[]
    best_f1=-1.0
    best_model=output/"reviewer_v2_weights.pt"
    for epoch in range(epochs):
        model.train()
        loss_total=0.0
        n=0
        for x,y in loader:
            x,y=x.to(device),y.to(device)
            logits=model(x)
            loss=loss_fn(logits,y)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            n+=len(y)
            loss_total+=float(loss.item())*len(y)
        predicted=[]
        truth=[]
        model.eval()
        with torch.inference_mode():
            for x,y in evaluator:
                p=model(x.to(device)).argmax(dim=1).cpu().tolist()
                predicted.extend(p)
                truth.extend(y.tolist())
        info=score(truth,predicted,val_records)
        info["epoch"]=epoch+1
        info["training_loss"]=round(loss_total/n,6)
        history.append(info)
        print(f"secondary-v2 epoch {epoch+1}/{epochs} macro_f1={info['macro_f1']:.4f} "
              f"diode_recall={info['by_family']['diode']['recall']:.4f} "
              f"other_recall={info['by_family']['other']['recall']:.4f}",flush=True)
        if info["macro_f1"]>best_f1:
            best_f1=info["macro_f1"]
            torch.save(model.state_dict(),best_model)
    model.load_state_dict(torch.load(best_model,map_location=device,weights_only=True))
    model=model.to("cpu").eval()
    onnx_path=output/"reviewer_cap_diode_other.onnx"
    torch.onnx.export(model,torch.randn(1,3,SIDE,SIDE),onnx_path,
                      input_names=["image"],output_names=["logits"],
                      opset_version=13,do_constant_folding=True)
    import onnxruntime as ort
    import numpy as np
    session=ort.InferenceSession(str(onnx_path),providers=["CPUExecutionProvider"])
    arr=session.run(None,{"image":np.zeros((1,3,SIDE,SIDE),dtype=np.float32)})[0]
    if arr.shape!=(1,3):raise RuntimeError("Unexpected independent three-class ONNX output shape")
    best=max(history,key=lambda item:item["macro_f1"])
    report={
        "schema":"nova-independent-capacitor-diode-other-reviewer-v2",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "labels":list(CLASSES),
        "source":"4TU PCB-MC-C full-MD5 board-aware fold0, 23 published source labels",
        "source_audit":audit,
        "train":train_summary,
        "validation":val_summary,
        "parameters":{"epochs":epochs,"batch_size":batch_size,"side":SIDE,
                      "balanced_sampler":True,
                      "pretrained":"MobileNet_V3_Small_Weights.IMAGENET1K_V1"},
        "best_epoch":best["epoch"],
        "best_result":best,
        "history":history,
        "model":{"file":onnx_path.name,"bytes":onnx_path.stat().st_size,"sha256":sha256(onnx_path)},
        "approved_for_live_use":False,
        "production_model_unchanged":True,
        "limitations":[
            "Other class contains annotated other components, NOT proof of background negatives.",
            "Independent real YOLO detection crop evaluation remains necessary.",
            "No datasheet, nominal electrical-value, or health assertions.",
            "May abstain or disagree; never overwrite technician label.",
        ],
    }
    (output/"reviewer_v2_training_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prepared",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--epochs",type=int,default=12)
    p.add_argument("--batch-size",type=int,default=32)
    p.add_argument("--device",default="cpu")
    args=p.parse_args()
    result=train(args.prepared,args.output,args.epochs,args.batch_size,args.device)
    print(json.dumps({"best_epoch":result["best_epoch"],"metrics":result["best_result"],
                      "model":result["model"],"approved_for_live_use":False},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
