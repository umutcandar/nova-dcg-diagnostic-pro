"""NOVA DCG research-only second visual model: capacitor-vs-diode crop reviewer.

An INDEPENDENT MobileNetV3-Small image classifier learns PCB-MC photos
instead of trusting the main 21-class YOLO's own logits. Classes:
 - capacitor: publisher Capacitor (1), Electrolytic Capacitor (6)
 - diode: publisher Diode (4), Zener Diode (22)

Data: fully MD5-verified 4TU PCB-MC-C official fold, board-aware train/val.
This is a second visual proposal, NEVER technician verification or a health
judgment. No automatic production deployment; gate independent evaluations
and model licensing before enabling any live external inference.
"""
import argparse
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps
from pcb_mc_import import PRESENT_NAMES
from pcb_mc_train import validate_fold

TARGET_GROUPS = {"capacitor":(1,6),"diode":(4,22)}
CLASS_NAMES = ("capacitor","diode")
RESEARCH_SEED = 42
SIDE = 160
MAX_TRAIN_CAPS = 1400
MAX_VALID_CAPS = 450


def sha256(path):
    hasher=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_box_label(line, where):
    parts=line.split()
    if len(parts)!=5:
        raise ValueError(f"Expected 5-column validated YOLO box: {where}")
    try:
        class_id=int(parts[0])
        cx,cy,bw,bh=[float(x) for x in parts[1:]]
    except (TypeError,ValueError) as exc:
        raise ValueError(f"Invalid YOLO crop label: {where}") from exc
    if (class_id not in range(len(PRESENT_NAMES)) or
        not all(math.isfinite(x) for x in (cx,cy,bw,bh)) or
        bw<=0 or bh<=0 or cx-bw/2 < -1e-5 or cy-bh/2 < -1e-5 or
        cx+bw/2 > 1+1e-5 or cy+bh/2 > 1+1e-5):
        raise ValueError(f"Bad YOLO bounding box: {where}")
    return class_id,(cx,cy,bw,bh)


def collect_records(prepared,split,limit_cap,seed=RESEARCH_SEED):
    """Return cropped objects only from the requested official board split."""
    prepared=Path(prepared)
    image_dir=prepared/"images"/split
    label_dir=prepared/"labels"/split
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise FileNotFoundError("Missing official-fold training/validation files")
    allowed={1:0,6:0,4:1,22:1}
    groups={0:[],1:[]}
    source_counts=Counter()
    image_paths=sorted(
        p for p in image_dir.iterdir()
        if p.suffix.lower() in (".jpg",".jpeg",".png")
    )
    if not image_paths:
        raise ValueError("No official source photos found")
    for path in image_paths:
        file=label_dir/(path.stem+".txt")
        if not file.is_file():
            raise FileNotFoundError(f"Photo missing label: {path.name}")
        for line_number,line in enumerate(file.read_text(encoding="utf-8").splitlines(),1):
            if not line.strip():
                continue
            index,box=parse_box_label(line,f"{path.name}:{line_number}")
            if index not in allowed:
                continue
            group=allowed[index]
            groups[group].append((path,box,group,index))
            source_counts[PRESENT_NAMES[index]]+=1
    rng=random.Random(seed)
    if len(groups[0])>limit_cap:
        groups[0]=rng.sample(groups[0],limit_cap)
    # Never silently drop rare diode and Zener examples.
    chosen=groups[0]+groups[1]
    rng.shuffle(chosen)
    counts=Counter(x[2] for x in chosen)
    if counts[0]<100 or counts[1]<30:
        raise ValueError(f"Insufficient labeled held-out classes: {dict(counts)}")
    return chosen,{"source_instances":dict(source_counts),
                   "sampled_capacitors":counts[0],
                   "sampled_diodes":counts[1],
                   "source_photo_count":len(image_paths)}


def crop_region(image, box, side=SIDE, margin=.27):
    """Crop with surrounding PCB context, never infer nonexistent terminals."""
    width,height=image.size
    cx,cy,bw,bh=box
    x,y=cx*width,cy*height
    diameter=max(5.0,bw*width,bh*height)*(1.0+2.0*margin)
    x1=int(math.floor(x-diameter/2))
    y1=int(math.floor(y-diameter/2))
    x2=int(math.ceil(x+diameter/2))
    y2=int(math.ceil(y+diameter/2))
    if x2<=x1 or y2<=y1:
        raise ValueError("Degenerate crop")
    # PIL crop pads the outside of source with black. Avoid distorting aspect ratio.
    cut=image.crop((x1,y1,x2,y2))
    return cut.convert("RGB").resize((side,side),resample=Image.Resampling.BICUBIC)


def make_dataset(records,augment=False):
    import torch
    from torchvision import transforms
    if augment:
        recipe=transforms.Compose([
            transforms.RandomHorizontalFlip(p=.5),
            transforms.RandomVerticalFlip(p=.5),
            transforms.RandomApply([transforms.ColorJitter(brightness=.12,contrast=.15,
                                                         saturation=.12)],p=.5),
            transforms.ToTensor(),
            transforms.Normalize(mean=(.485,.456,.406),std=(.229,.224,.225)),
        ])
    else:
        recipe=transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=(.485,.456,.406),std=(.229,.224,.225)),
        ])
    class Crops(torch.utils.data.Dataset):
        def __len__(self):return len(records)
        def __getitem__(self,index):
            path,box,label,source_id=records[index]
            with Image.open(path) as opened:
                image=ImageOps.exif_transpose(opened).convert("RGB")
                cropped=crop_region(image,box)
            return recipe(cropped),label
    return Crops()


def precision_recall_f1_counts(expected,proposed):
    counts={name:{"gt":0,"predicted":0,"tp":0,"fp":0,"fn":0}
            for name in CLASS_NAMES}
    for y,p in zip(expected,proposed):
        counts[CLASS_NAMES[y]]["gt"]+=1
        counts[CLASS_NAMES[p]]["predicted"]+=1
        if y==p:
            counts[CLASS_NAMES[y]]["tp"]+=1
        else:
            counts[CLASS_NAMES[y]]["fn"]+=1
            counts[CLASS_NAMES[p]]["fp"]+=1
    metrics={}
    for name,c in counts.items():
        precision=c["tp"]/(c["tp"]+c["fp"]) if c["tp"]+c["fp"] else 0
        recall=c["tp"]/(c["tp"]+c["fn"]) if c["tp"]+c["fn"] else 0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0
        metrics[name]={**c,"precision":round(precision,4),
                       "recall":round(recall,4),"f1":round(f1,4)}
    return {"by_class":metrics,
            "macro_f1":round(sum(x["f1"] for x in metrics.values())/2,4),
            "accuracy":round(sum(a==b for a,b in zip(expected,proposed))/len(expected),4)
            if expected else None,
            "validation_objects":len(expected)}


def train_reviewer(prepared,output,epochs=12,device="cpu",batch_size=32):
    if not isinstance(epochs,int) or not 1<=epochs<=100:
        raise ValueError("epochs must be 1–100")
    if not isinstance(batch_size,int) or not 2<=batch_size<=128:
        raise ValueError("batch size must be 2–128")
    audit=validate_fold(prepared)
    if audit.get("full_zip_md5_verified") is not True:
        raise ValueError("Only training on fully verified 4TU archive permitted")
    if audit.get("official_fold")!=0:
        raise ValueError("Initial reviewer experiment is restricted to official fold 0")
    train,train_info=collect_records(prepared,"train",MAX_TRAIN_CAPS)
    val,val_info=collect_records(prepared,"val",MAX_VALID_CAPS)
    if not set(x[0] for x in train).isdisjoint(set(x[0] for x in val)):
        raise ValueError("Training and validation share physical photo filenames")
    out=Path(output).resolve()
    out.mkdir(parents=True,exist_ok=True)

    import torch
    from torch import nn
    from torch.utils.data import DataLoader,WeightedRandomSampler
    from torchvision.models import MobileNet_V3_Small_Weights,mobilenet_v3_small
    torch.manual_seed(RESEARCH_SEED)
    random.seed(RESEARCH_SEED)
    torch.set_num_threads(2)
    training=make_dataset(train,True)
    validation=make_dataset(val,False)
    train_counts=Counter(x[2] for x in train)
    weights=[1.0/train_counts[x[2]] for x in train]
    sampler=WeightedRandomSampler(weights, num_samples=len(train),replacement=True,
                                  generator=torch.Generator().manual_seed(RESEARCH_SEED))
    loader=DataLoader(training,batch_size=batch_size,sampler=sampler,num_workers=0)
    evaluator=DataLoader(validation,batch_size=batch_size,shuffle=False,num_workers=0)
    model=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    for parameter in model.features.parameters():
        parameter.requires_grad_(False)
    model.classifier[3]=nn.Linear(model.classifier[3].in_features,2)
    model=model.to(device)
    criterion=nn.CrossEntropyLoss()
    optimizer=torch.optim.AdamW(model.classifier.parameters(),lr=.001,weight_decay=.01)
    best_f1=-1.0
    best_path=out/"reviewer_best_state.pt"
    history=[]
    for epoch in range(epochs):
        model.train()
        total_loss=0.0
        total_samples=0
        for pictures,labels in loader:
            pictures,labels=pictures.to(device),labels.to(device)
            logits=model(pictures)
            loss=criterion(logits,labels)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total_loss+=float(loss.item())*len(labels)
            total_samples+=len(labels)
        model.eval()
        correct,guesses=[],[]
        with torch.inference_mode():
            for pictures,labels in evaluator:
                logits=model(pictures.to(device))
                predicted=logits.argmax(dim=1).cpu().tolist()
                correct.extend(labels.tolist())
                guesses.extend(predicted)
        metrics=precision_recall_f1_counts(correct,guesses)
        history.append({"epoch":epoch+1,"train_loss":round(total_loss/total_samples,5),
                        **metrics})
        print(f"NOVA reviewer epoch {epoch+1}/{epochs} "
              f"macro_f1={metrics['macro_f1']:.3f} "
              f"capacitor_recall={metrics['by_class']['capacitor']['recall']:.3f} "
              f"diode_recall={metrics['by_class']['diode']['recall']:.3f}",flush=True)
        if metrics["macro_f1"]>best_f1:
            best_f1=metrics["macro_f1"]
            torch.save(model.state_dict(),best_path)
    # State dictionary is generated by this code; no third-party .pt unpickling.
    state=torch.load(best_path,map_location=device,weights_only=True)
    model.load_state_dict(state)
    model=model.to("cpu").eval()
    onnx=out/"reviewer_capacitor_diode.onnx"
    torch.onnx.export(model,torch.randn(1,3,SIDE,SIDE),
                      onnx,input_names=["image"],output_names=["logits"],
                      opset_version=13,do_constant_folding=True)
    import onnxruntime as ort
    session=ort.InferenceSession(str(onnx),providers=["CPUExecutionProvider"])
    output_data=session.run(None,{"image":__import__("numpy").zeros((1,3,SIDE,SIDE),dtype="float32")})[0]
    if output_data.shape!=(1,2):
        raise RuntimeError("Unexpected exported independent reviewer output")
    selected=max(history,key=lambda x:x["macro_f1"])
    report={
        "schema":"nova-independent-capacitor-diode-reviewer-v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "purpose":"independent_smd_crop_review_not_replacement_or_health_test",
        "labels":list(CLASS_NAMES),
        "source":"Official 4TU PCB-MC 23-class full MD5-verified board-fold-zero",
        "source_fold":0,
        "source_audit":audit,
        "train":train_info,"validation":val_info,
        "parameters":{"epochs":epochs,"batch_size":batch_size,"side":SIDE,
                      "torchvision_pretrained":"MobileNet_V3_Small_Weights.IMAGENET1K_V1",
                      "frozen_backbone":True,"seed":RESEARCH_SEED},
        "model":{"file":onnx.name,"sha256":sha256(onnx),"bytes":onnx.stat().st_size},
        "best_epoch":selected["epoch"],
        "best_result":selected,
        "history":history,
        "approved_for_live_use":False,
        "independent_board_disjoint":True,
        "live_21class_detector_unchanged":True,
        "requirements_before_live":[
            "Validate as a second-stage model on actual YOLO crops from unseen NOVA boards",
            "Check class-wise error rates and out-of-distribution abstention",
            "Verify pretrained weights licensing and end-user privacy",
            "Never auto-correct human-reviewed labels or infer electrical health",
        ],
    }
    (out/"reviewer_training_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prepared",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--epochs",type=int,default=12)
    ap.add_argument("--batch-size",type=int,default=32)
    ap.add_argument("--device",default="cpu")
    args=ap.parse_args()
    result=train_reviewer(args.prepared,args.output,
                          epochs=args.epochs,batch_size=args.batch_size,device=args.device)
    print(json.dumps({"best_epoch":result["best_epoch"],
                      "best_validation":result["best_result"],
                      "model":result["model"],
                      "approved_for_live_use":False},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
