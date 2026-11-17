"""Pinned, CPU-only 21-class PCB component detector for NOVA DCG web.

The original publisher's ONNX has 21 classes including potentiometer. The
publisher's model card says MIT; model metadata embeds an Ultralytics AGPL-3.0
notice. Clarify commercial redistribution/network-use obligations separately.

No PyTorch checkpoints or pickle execution; all downloaded bytes must match the
exact SHA256 verified in isolated GitHub Actions model-probe.
"""
import ast
import hashlib
import logging
import math
import os
from pathlib import Path
from shutil import copyfileobj
from threading import Lock
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

LOG = logging.getLogger("nova_web_model")
ONNX_URL = ("https://huggingface.co/Arshia82sbn/pcb-yolov8s-detection/"
            "resolve/main/best.onnx?download=true")
EXPECTED_SIZE = 44777137
EXPECTED_SHA256 = "bfc398bb93ce61d9d7d00389db51b651bd90c4e2141163a0ae6dad79a247ae29"
CLASSES = (
    "battery", "button", "buzzer", "capacitor", "clock", "connector",
    "diode", "display", "fuse", "heatsink", "ic", "inductor",
    "led", "pads", "pins", "potentiometer", "relay", "resistor",
    "switch", "transformer", "transistor",
)
LABELS = {
    "battery": "Batarya", "button": "Anahtar", "buzzer": "Buzzer",
    "capacitor": "Kondansatör", "clock": "Kristal", "connector": "Konnektör",
    "diode": "Diyot", "display": "Ekran", "fuse": "Sigorta",
    "heatsink": "Soğutucu", "ic": "Entegre", "inductor": "Bobin",
    "led": "LED", "pads": "Pad", "pins": "Pin",
    "potentiometer": "Trimpot", "relay": "Röle", "resistor": "Direnç",
    "switch": "Anahtar", "transformer": "Trafo", "transistor": "Transistör",
}
MODEL_PATH = Path(os.environ.get(
    "NOVA_ONNX_WEIGHTS_PATH",
    str(Path(__file__).resolve().parent / "models" / "pcb_21class.onnx")
))
_DOWNLOAD_LOCK = Lock()
_SESSION_LOCK = Lock()
_SESSION = None
_DOWNLOAD_STATE = {"state": "not_ready", "detail": "Model dosyası henüz doğrulanmadı."}


class OnnxDetectorError(RuntimeError):
    pass


def _hash_file(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def model_state():
    return {**_DOWNLOAD_STATE, "classes": 21, "runtime": "ONNX Runtime CPU",
            "mode": "unverified_visual_predictions"}


def ensure_weights(destination=MODEL_PATH):
    path = Path(destination)
    with _DOWNLOAD_LOCK:
        if path.exists():
            if path.stat().st_size != EXPECTED_SIZE or _hash_file(path) != EXPECTED_SHA256:
                _DOWNLOAD_STATE.update(state="error", detail="Mevcut modelin SHA256 doğrulaması başarısız.")
                raise OnnxDetectorError(_DOWNLOAD_STATE["detail"])
            _DOWNLOAD_STATE.update(state="ready", detail="Doğrulanmış 21-sınıf model dosyası hazır.")
            return path
        _DOWNLOAD_STATE.update(state="downloading", detail="Doğrulanmış 21-sınıf ONNX modeli indiriliyor.")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".download")
        try:
            request = Request(ONNX_URL, headers={"User-Agent": "NOVA-DCG-ONNX/1.0"})
            size = 0
            sha = hashlib.sha256()
            with urlopen(request, timeout=100) as response, temp.open("wb") as out:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > EXPECTED_SIZE:
                        raise OnnxDetectorError("Model boyutu beklenen dosyayla uyuşmuyor.")
                    out.write(chunk)
                    sha.update(chunk)
            if size != EXPECTED_SIZE or sha.hexdigest() != EXPECTED_SHA256:
                raise OnnxDetectorError("Model SHA256 doğrulaması başarısız; çalıştırılmadı.")
            temp.replace(path)
            _DOWNLOAD_STATE.update(state="ready", detail="Doğrulanmış 21-sınıf model indirildi.")
            return path
        except Exception as exc:
            _DOWNLOAD_STATE.update(state="error", detail="Model indirilemedi/doğrulanamadı. Manuel inceleme kullanılabilir.")
            LOG.warning("Verified ONNX model unavailable: %s", type(exc).__name__)
            if isinstance(exc, OnnxDetectorError):
                raise
            raise OnnxDetectorError(_DOWNLOAD_STATE["detail"]) from exc
        finally:
            temp.unlink(missing_ok=True)


def _session():
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is not None:
            return _SESSION
        path = ensure_weights()
        try:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session = ort.InferenceSession(str(path), sess_options=options,
                                           providers=["CPUExecutionProvider"])
            model_inputs = session.get_inputs()
            outputs = session.get_outputs()
            if len(model_inputs) != 1 or model_inputs[0].shape != [1,3,640,640] or len(outputs) != 1:
                raise OnnxDetectorError("ONNX model giriş/çıkış biçimi değişmiş.")
            if outputs[0].shape != [1,25,8400]:
                raise OnnxDetectorError("ONNX model sınıf/çıktı boyutu değişmiş.")
            metadata = session.get_modelmeta().custom_metadata_map
            names = ast.literal_eval(metadata.get("names", ""))
            actual = tuple(names[i] for i in range(len(names))) if isinstance(names, dict) else tuple(names)
            if actual != CLASSES:
                raise OnnxDetectorError("ONNX model sınıf sırası doğrulaması başarısız.")
        except OnnxDetectorError:
            raise
        except Exception as exc:
            LOG.exception("ONNX model initialization failed")
            raise OnnxDetectorError("Model başlatılamadı. Manuel inceleme kullanılabilir.") from exc
        _SESSION = session
        _DOWNLOAD_STATE.update(state="ready", detail="21 sınıflı ONNX modeli CPU'da çalışmaya hazır.")
        return session


def _iou(box, candidates):
    import numpy as np
    upper_left = np.maximum(candidates[:, :2], box[:2])
    lower_right = np.minimum(candidates[:, 2:], box[2:])
    wh = np.maximum(lower_right-upper_left, 0)
    overlap = wh[:,0]*wh[:,1]
    a=(box[2]-box[0])*(box[3]-box[1])
    b=(candidates[:,2]-candidates[:,0])*(candidates[:,3]-candidates[:,1])
    return overlap/np.maximum(1e-9,a+b-overlap)


def decode_predictions(output, width, height, scale, pad_x, pad_y, confidence=0.28):
    """Decode YOLOv8 ONNX output 1x25x8400 without a pickle/model import."""
    import numpy as np
    array = np.asarray(output)
    if array.ndim != 3 or array.shape != (1,25,8400) or not np.isfinite(array).all():
        raise OnnxDetectorError("Beklenmeyen veya geçersiz ONNX tahmin çıktısı.")
    raw = array[0].T
    scores = raw[:,4:]
    ids = scores.argmax(axis=1)
    certainty = scores[np.arange(len(scores)), ids]
    mask = certainty >= confidence
    if not mask.any():
        return []
    coords=raw[mask,:4]
    class_scores=scores[mask]
    ids=ids[mask]
    certainty=certainty[mask]
    x1=(coords[:,0]-coords[:,2]/2-pad_x)/scale
    y1=(coords[:,1]-coords[:,3]/2-pad_y)/scale
    x2=(coords[:,0]+coords[:,2]/2-pad_x)/scale
    y2=(coords[:,1]+coords[:,3]/2-pad_y)/scale
    boxes=np.stack([x1,y1,x2,y2],axis=1)
    boxes[:,[0,2]]=np.clip(boxes[:,[0,2]],0,width)
    boxes[:,[1,3]]=np.clip(boxes[:,[1,3]],0,height)
    valid=(boxes[:,2]-boxes[:,0]>=2)&(boxes[:,3]-boxes[:,1]>=2)
    boxes=boxes[valid];ids=ids[valid];certainty=certainty[valid]
    class_scores=class_scores[valid]
    kept=[]
    for idx in np.argsort(certainty)[::-1]:
        if len(kept)>=200:
            break
        if any(ids[idx] == ids[previous] and _iou(boxes[idx],boxes[previous:previous+1])[0]>.48
               for previous in kept):
            continue
        kept.append(int(idx))
    results=[]
    for index in kept:
        name=CLASSES[int(ids[index])]
        results.append({
            "label": LABELS[name],
            "source_label": name,
            "confidence": round(float(certainty[index]),6),
            "bbox_xyxy_pixels": boxes[index].astype(float).tolist(),
            "source": "model_21_onnx",
            "alternatives": [
                {
                    "label": LABELS[CLASSES[int(class_id)]],
                    "source_label": CLASSES[int(class_id)],
                    "confidence": round(float(class_scores[index, class_id]), 6),
                }
                for class_id in np.argsort(class_scores[index])[::-1][:3]
                if float(class_scores[index, class_id]) >= 0.08
            ],
            "verified": False,
        })
    return sorted(results,key=lambda obj:(obj["bbox_xyxy_pixels"][1],obj["bbox_xyxy_pixels"][0]))


def candidate_tiles(width, height):
    """At most 9 overlapping detail crops; cover EVERY pixel of large PCB photos.

    On 4K/8K photos a fixed 1024px 3-column grid silently leaves gaps.
    Size tiles for three positions per axis with >=20% overlap, retaining
    a fixed CPU inference budget on the small Render instance.
    """
    if width < 1 or height < 1 or max(width, height) <= 1024:
        return []
    size = min(1024, max(640, round(max(width, height) * 0.58)))
    # Three evenly spaced windows can only cover the full dimension with
    # 20% overlap when tile >= total / (3 - 2*0.20) = total / 2.6.
    tilew = min(width, max(size, math.ceil(width / 2.6)))
    tileh = min(height, max(size, math.ceil(height / 2.6)))

    def starts(total, tile):
        remaining = max(0, total - tile)
        return sorted(set((0, remaining // 2, remaining)))

    result = [
        (x, y, min(width, x + tilew), min(height, y + tileh))
        for y in starts(height, tileh)
        for x in starts(width, tilew)
    ]
    return [rect for rect in result if rect != (0, 0, width, height)]


def merge_overlapping_detections(predictions, threshold=.50):
    """Suppress duplicates of the SAME class, preserving competing classes."""
    sorted_items=sorted(predictions,key=lambda x:x["confidence"],reverse=True)
    accepted=[]
    for item in sorted_items:
        current=item["bbox_xyxy_pixels"]
        if any(other["source_label"]==item["source_label"] and
               float(_iou(
                   __import__("numpy").asarray(current,dtype=float),
                   __import__("numpy").asarray([other["bbox_xyxy_pixels"]],dtype=float)
               )[0]) >= threshold for other in accepted):
            continue
        accepted.append(item)
        if len(accepted)>=220:break
    return sorted(accepted,key=lambda x:(x["bbox_xyxy_pixels"][1],x["bbox_xyxy_pixels"][0]))


def predict_image_crop(session, crop, left, top):
    """Run a single 640x640 ONNX pass and map results to whole-image coordinates."""
    import numpy as np
    width,height=crop.size
    scale=min(640/width,640/height)
    w,h=max(1,round(width*scale)),max(1,round(height*scale))
    px,py=(640-w)//2,(640-h)//2
    resized=crop.resize((w,h),Image.Resampling.BILINEAR)
    padded=Image.new("RGB",(640,640),(114,114,114))
    padded.paste(resized,(px,py))
    tensor=np.asarray(padded,dtype=np.float32).transpose(2,0,1)[None]/255.0
    raw=session.run(None,{session.get_inputs()[0].name:tensor})[0]
    results=decode_predictions(raw,width,height,scale,px,py)
    if left or top:
        for item in results:
            b=item["bbox_xyxy_pixels"]
            item["bbox_xyxy_pixels"]=[
                b[0]+left,b[1]+top,b[2]+left,b[3]+top
            ]
    return results


def detailed_detect(image_path):
    """Research-only multi-scale pass; enable in production ONLY after benchmark."""
    image_path=Path(image_path)
    if not image_path.is_file():
        raise OnnxDetectorError("Kart fotoğrafı bulunamadı.")
    session=_session()
    with Image.open(image_path) as original:
        board=ImageOps.exif_transpose(original).convert("RGB")
    width,height=board.size
    try:
        all_detections=predict_image_crop(session,board,0,0)
        for x1,y1,x2,y2 in candidate_tiles(width,height):
            with board.crop((x1,y1,x2,y2)) as crop:
                all_detections.extend(predict_image_crop(session,crop,x1,y1))
        return merge_overlapping_detections(all_detections)
    except OnnxDetectorError:
        raise
    except Exception as exc:
        LOG.exception("Detailed PCB ONNX inference failed")
        raise OnnxDetectorError("Ayrıntılı tarama başarısız. Normal tarama kullanılabilir.") from exc


def automatic_detect(image_path, progress=None):
    """Return unverified proposals from the pinned 21-class ONNX checkpoint."""
    import numpy as np
    path=Path(image_path)
    if not path.is_file():
        raise OnnxDetectorError("Kart fotoğrafı bulunamadı.")
    sess=_session()
    with Image.open(path) as original:
        board=ImageOps.exif_transpose(original).convert("RGB")
    w,h=board.size
    side=640
    scale=min(side/w,side/h)
    new_w,new_h=round(w*scale),round(h*scale)
    pad_x=(side-new_w)//2
    pad_y=(side-new_h)//2
    resized=board.resize((new_w,new_h), Image.Resampling.BILINEAR)
    padded=Image.new("RGB",(side,side),(114,114,114))
    padded.paste(resized,(pad_x,pad_y))
    tensor=np.asarray(padded,dtype=np.float32).transpose(2,0,1)[None]/255.0
    name=sess.get_inputs()[0].name
    try:
        prediction=sess.run(None,{name:tensor})[0]
    except Exception as exc:
        LOG.exception("ONNX inference failed")
        raise OnnxDetectorError("Kart görüntüsü taranamadı. Manuel inceleme kullanılabilir.") from exc
    return decode_predictions(prediction,w,h,scale,pad_x,pad_y)


def warm_up():
    """Optional non-blocking startup download; does not load model with pickle."""
    try:
        ensure_weights()
        LOG.info("Verified 21-class ONNX model downloaded, SHA256 prefix=%s", EXPECTED_SHA256[:12])
    except OnnxDetectorError:
        LOG.warning("21-class ONNX model warm-up failed; manual review remains available")
