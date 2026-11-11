"""Optional local YOLO inference. Requires a user-supplied trained weights file.

Never downloads a model, never claims an untrained model can identify PCB parts.
"""
from pathlib import Path
from dataset import CLASSES
from source_model import SOURCE_CLASSES, adapt_source_classes, mapped_label

def detect_components(image_path, weights_path, confidence=0.4):
    image=Path(image_path)
    weights=Path(weights_path)
    if not image.is_file():
        raise FileNotFoundError(f"Image not found: {image}")
    if not weights.is_file():
        raise FileNotFoundError(f"Trained weights not found: {weights}")
    if not 0 < confidence <= 1:
        raise ValueError("Confidence must be in (0, 1]")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install optional dependency: python3 -m pip install ultralytics") from exc
    model=YOLO(str(weights))
    result=model.predict(source=str(image),conf=confidence,verbose=False)[0]
    names=result.names
    class_names=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
    if class_names == CLASSES:
        label_adapter = lambda name: name
    elif class_names == SOURCE_CLASSES:
        adapt_source_classes(names)
        label_adapter = mapped_label
    else:
        raise ValueError("Unknown model class mapping; only NOVA or verified source PCB classes are supported")
    predictions=[]
    for box in result.boxes:
        class_id=int(box.cls[0])
        name=names[class_id] if isinstance(names,dict) else names[class_id]
        x1,y1,x2,y2=(float(v) for v in box.xyxy[0].tolist())
        predictions.append({"label":label_adapter(str(name)),"source_label":str(name),"confidence":float(box.conf[0]),
                            "bbox_xyxy_pixels":[x1,y1,x2,y2],
                            "source":"model","verified":False})
    return predictions

def validate_model_classes(names):
    """Explicitly check class names before interpreting a custom model's output."""
    actual=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
    if actual != CLASSES:
        raise ValueError("Model classes differ from NOVA dataset classes/order")
    return True
