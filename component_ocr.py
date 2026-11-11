"""Optional local OCR for component markings. Never assumes OCR is a part number."""
import re
from pathlib import Path

def candidate_markings(text):
    tokens=re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{2,39}",str(text).upper())
    return list(dict.fromkeys(x for x in tokens if any(ch.isdigit() for ch in x)))

def read_markings(image_path,bbox=None):
    """Return unverified text candidates, requiring technician confirmation."""
    from PIL import Image,ImageOps,ImageEnhance
    path=Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("Optional OCR dependency pytesseract is missing") from exc
    with Image.open(path) as original:
        image=original.convert("RGB")
        if bbox is not None:
            if len(bbox)!=4:
                raise ValueError("Four bounding box coordinates required")
            x1,y1,x2,y2=map(int,bbox)
            if x1<0 or y1<0 or x2>image.width or y2>image.height or x1>=x2 or y1>=y2:
                raise ValueError("Bounding box outside image")
            image=image.crop((x1,y1,x2,y2))
        image=ImageEnhance.Contrast(ImageOps.grayscale(image)).enhance(2)
        image=image.resize((image.width*3,image.height*3))
        raw=pytesseract.image_to_string(image,config="--psm 6")
    return {"raw_text":raw,"candidates":candidate_markings(raw),
            "verified":False,"warning":"OCR tahminidir; parça kodu ve üretici teknisyen tarafından doğrulanmalı."}
