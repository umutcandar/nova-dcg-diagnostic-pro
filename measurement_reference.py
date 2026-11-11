"""Technician-entered, source-backed test specifications.

Only compare readings when mode, unit, circuit state and conditions match.
No absolute-maximum-rating comparisons.
"""
import math
from datasheet_catalog import normalize_part_number

MODES={"Direnç (Ω)","Diyot (V)","Kapasitans (F)"}
def validate_spec(spec):
    if not isinstance(spec,dict):
        raise ValueError("Specification must be an object")
    required=("part_number","source_url","mode","unit","minimum","maximum","conditions","circuit_state")
    if any(k not in spec for k in required):
        raise ValueError("Missing specification field")
    normalize_part_number(spec["part_number"])
    if not str(spec["source_url"]).startswith("https://"):
        raise ValueError("Verified HTTPS source required")
    if spec["mode"] not in MODES or spec["unit"]!=spec["mode"]:
        raise ValueError("Mode and unit mismatch")
    if spec["circuit_state"] not in ("out_of_circuit","in_circuit"):
        raise ValueError("Circuit state must be specified")
    if not str(spec["conditions"]).strip():
        raise ValueError("Measurement conditions required")
    low,high=float(spec["minimum"]),float(spec["maximum"])
    if not all(math.isfinite(x) for x in (low,high)) or low<0 or high<low:
        raise ValueError("Invalid limits")
    if spec.get("limit_type")!="measurement_reference":
        raise ValueError("Only measured reference limits accepted, not absolute maximum ratings")
    if not spec.get("technician_verified"):
        raise ValueError("Technician must verify source and conditions")
    return True

def compare(spec,task,value,circuit_state):
    validate_spec(spec)
    try:
        reading=float(value)
    except (ValueError,TypeError):
        raise ValueError("Numeric reading required") from None
    if not math.isfinite(reading) or reading<0:
        raise ValueError("Invalid reading")
    if spec["part_number"]!=task.get("part_number") or spec["mode"]!=task.get("mode"):
        return {"status":"Ek ölçüm gerekli","detail":"Parça kodu veya ölçüm modu uyuşmuyor."}
    if circuit_state!=spec["circuit_state"]:
        return {"status":"Ek ölçüm gerekli","detail":"Referansın devre içi/dışı koşulu ölçümle uyuşmuyor."}
    low,high=float(spec["minimum"]),float(spec["maximum"])
    if low<=reading<=high:
        return {"status":"Referans aralığında","detail":"Değer, doğrulanmış referans aralığında; bu tek başına parçanın sağlam olduğunu kanıtlamaz."}
    return {"status":"Aralık dışında — doğrula","detail":"Referans aralığı dışında. Paralel yollar, ölçüm koşulları ve ikinci ölçüm kontrol edilmeli."}
