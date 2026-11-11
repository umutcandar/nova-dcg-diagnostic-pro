"""Validate local PCB detector setup and generate an actionable status report."""
import importlib.util
import json
from pathlib import Path

def status(weights="models/yolov8s_pcb_best.pt", image=None):
    weights=Path(weights)
    result={
        "ultralytics_installed":importlib.util.find_spec("ultralytics") is not None,
        "pillow_installed":importlib.util.find_spec("PIL") is not None,
        "weights_present":weights.is_file(),
        "pcb_image_present":bool(image and Path(image).is_file()),
        "ready_for_inference":False,
    }
    if weights.is_file():
        from download_and_test_model import EXPECTED_SIZE
        result["weights_size_valid"]=weights.stat().st_size==EXPECTED_SIZE
    result["ready_for_inference"]=all((
        result["ultralytics_installed"],
        result["pillow_installed"],
        result["weights_present"],
        result.get("weights_size_valid",False),
        result["pcb_image_present"],
    ))
    return result

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--weights",default="models/yolov8s_pcb_best.pt")
    p.add_argument("--image")
    args=p.parse_args()
    print(json.dumps(status(args.weights,args.image),indent=2))
