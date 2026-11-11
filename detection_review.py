"""Review and correct detector labels before creating measurement tasks."""
import math

ALLOWED={"Direnç","Kondansatör","Diyot","Bobin","MOSFET","Transistör","Entegre","Konnektör","Bilinmiyor"}
def review_detections(detections, corrections=None, threshold=0.55):
    if not 0<=threshold<=1:
        raise ValueError("Confidence threshold must be between zero and one")
    corrections=corrections or {}
    result=[]
    for i,item in enumerate(detections):
        if not isinstance(item,dict):
            raise ValueError("Detection must be an object")
        record=dict(item)
        confidence=record.get("confidence")
        if confidence is not None:
            try:
                confidence=float(confidence)
            except (ValueError,TypeError):
                raise ValueError("Invalid confidence") from None
            if not math.isfinite(confidence) or not 0<=confidence<=1:
                raise ValueError("Invalid confidence")
        label=record.get("label","Bilinmiyor")
        if i in corrections:
            label=corrections[i]
            if label not in ALLOWED:
                raise ValueError("Unsupported corrected component type")
            record["verified"]=True
            record["review_note"]="Teknisyen tarafından düzeltildi"
        else:
            record["verified"]=False
            record["review_note"]="Düşük güven: teknisyen doğrulaması gerekli" if confidence is None or confidence<threshold else "Model tahmini: teknisyen doğrulaması gerekli"
        record["label"]=label if label in ALLOWED else "Bilinmiyor"
        result.append(record)
    return result
