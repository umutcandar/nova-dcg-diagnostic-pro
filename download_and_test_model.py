"""Download the optional public PCB checkpoint and run a local smoke test.

Explicit user-initiated download; weights are never committed to GitHub.
"""
import argparse
import hashlib
import urllib.request
from pathlib import Path

URL = "https://media.githubusercontent.com/media/wangshnegqi/pcb-component-detection-dataset-yolo/main/models/yolov8s_pcb_best.pt"
DEFAULT = Path("models") / "yolov8s_pcb_best.pt"
EXPECTED_SHA256 = "ad21e33f0962e3a23119223e0f82ef7d189ef118a8d4b79d51ab62187612e93c"
EXPECTED_SIZE = 89552854

def download(destination=DEFAULT):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "NOVA-DCG/1.0"})
    temp = destination.with_suffix(".download")
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as out:
            import shutil
            shutil.copyfileobj(response, out)
        if temp.stat().st_size < 1024:
            raise ValueError("Downloaded file is unexpectedly small or is a Git LFS pointer, not model weights")
        with temp.open("rb") as check:
            if check.read(64).startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError("Git LFS pointer downloaded instead of model weights")
        if temp.stat().st_size != EXPECTED_SIZE:
            raise ValueError(f"Model size mismatch: {temp.stat().st_size} != {EXPECTED_SIZE}")
        digest=hashlib.sha256(temp.read_bytes()).hexdigest()
        if digest != EXPECTED_SHA256:
            raise ValueError("Model SHA256 mismatch; refusing unverified weights")
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return destination, digest

def smoke_test(weights, image):
    from model_inference import detect_components
    results=detect_components(image,weights)
    print(f"Model loaded. Detections: {len(results)}")
    for result in results[:20]:
        print(f"  {result['label']}: {result['confidence']:.1%}")
    print("Unverified suggestions only; no electrical fault diagnosis.")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--image",help="Optional local PCB image to test")
    parser.add_argument("--weights",default=str(DEFAULT))
    parser.add_argument("--skip-download",action="store_true")
    args=parser.parse_args()
    if args.skip_download:
        path=Path(args.weights)
        if not path.is_file():
            parser.error(f"Weights not found: {path}")
    else:
        path,digest=download(args.weights)
        print(f"Downloaded {path} ({path.stat().st_size} bytes), SHA256={digest}")
    if args.image:
        smoke_test(path,args.image)
    else:
        print("To test inference: python3 download_and_test_model.py --skip-download --image path/to/pcb.jpg")
