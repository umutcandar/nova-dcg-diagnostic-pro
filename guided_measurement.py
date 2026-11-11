"""Interactive photo-guided manual measurements.

The image detector proposes regions. A technician confirms component type and
probe placement. Rules are intentionally conservative; no automatic verdict
of electrical health is inferred from appearance alone.
"""
import math
from measurement_guides import instruction_for

MODES = {
    "Direnç": "Direnç (Ω)",
    "Bobin": "Direnç (Ω)",
    "Diyot": "Diyot (V)",
    "Kondansatör": "Kapasitans (F)",
    "MOSFET": "Diyot (V)",
    "Transistör": "Diyot (V)",
    "Entegre": "Direnç (Ω)",
    "Konnektör": "Direnç (Ω)",
}

def measurement_plan(detections):
    """Create one guided task per detected region; no invented pin positions."""
    tasks=[]
    for index, detection in enumerate(detections,1):
        label=str(detection.get("label","Bilinmiyor"))
        bbox=detection.get("bbox_xyxy_pixels")
        if not isinstance(bbox,(list,tuple)) or len(bbox)!=4:
            raise ValueError("Detection bounding box must have four coordinates")
        coords=[float(v) for v in bbox]
        if not all(math.isfinite(v) for v in coords) or coords[2]<=coords[0] or coords[3]<=coords[1]:
            raise ValueError("Invalid bounding box")
        component=label if label in MODES else "Bilinmiyor"
        suggested_mode, guidance=instruction_for(component)
        tasks.append({"id":index,"component":component,"source_label":label,
                      "bbox_xyxy_pixels":coords,"mode":suggested_mode,
                      "instruction":guidance+" Kart enerjisiz ve deşarj edilmiş olmalı.",
                      "confidence":detection.get("confidence"),
                      "status":"ölçüm bekleniyor"})
    return tasks

def evaluate(task, value, unit=None):
    """Evaluate measurement completeness, not component health."""
    try:
        reading=float(value)
    except (TypeError,ValueError):
        raise ValueError("Sayısal ölçüm girin") from None
    if not math.isfinite(reading) or reading<0:
        raise ValueError("Negatif veya sonlu olmayan ölçüm geçersiz")
    mode=task["mode"]
    if unit is not None and unit!=mode:
        raise ValueError("Ölçüm modu uyuşmuyor")
    if task["component"]=="Bilinmiyor":
        return {"status":"Ek ölçüm gerekli","detail":"Komponent tipi doğrulanmadan elektriksel sonuç yorumlanamaz."}
    if mode=="Direnç (Ω)" and reading<2:
        return {"status":"Ek ölçüm gerekli","detail":"Düşük direnç ölçüldü. Paralel yollar, bobin ve nominal değer kontrol edilmeli."}
    if mode=="Diyot (V)" and reading==0:
        return {"status":"Arıza şüphesi var","detail":"0 V ölçümü tekrar edilmeli; ters yön ve devre dışı ölçüm gerekebilir."}
    return {"status":"Ek ölçüm gerekli","detail":"Ölçüm kaydedildi; sağlamlık için parça kodu, nominal değer veya ek ölçüm gerekli."}
