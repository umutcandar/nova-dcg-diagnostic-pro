"""Opt-in local model training. Requires reviewed data and ultralytics."""
import argparse
from pathlib import Path

def train(data_yaml, base_model, epochs=40, imgsz=640):
    if not Path(data_yaml).is_file():
        raise FileNotFoundError(data_yaml)
    if not Path(base_model).is_file():
        raise FileNotFoundError("Supply a local pretrained weights file; no automatic downloads.")
    from ultralytics import YOLO
    model=YOLO(base_model)
    return model.train(data=str(Path(data_yaml).resolve()),epochs=epochs,imgsz=imgsz,
                       project="nova_training",name="pcb_components",exist_ok=False)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("data_yaml")
    parser.add_argument("base_model",help="Local YOLO .pt file")
    parser.add_argument("--epochs",type=int,default=40)
    parser.add_argument("--imgsz",type=int,default=640)
    args=parser.parse_args()
    train(args.data_yaml,args.base_model,args.epochs,args.imgsz)
