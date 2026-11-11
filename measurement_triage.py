"""Offline safety-oriented measurement triage.

This module never infers a component failure from one in-circuit reading.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Measurement:
    component: str
    mode: str
    value: float
    unit: str
    circuit_state: str
    reference_verified: bool = False
    lower: float | None = None
    upper: float | None = None

def triage(measurement: Measurement):
    if measurement.circuit_state not in ("in_circuit", "out_of_circuit"):
        raise ValueError("Circuit state must be declared")
    if measurement.mode not in ("resistance", "diode", "capacitance", "continuity"):
        return {"status":"ek ölçüm gerekli","reason":"Ölçüm modu için doğrulanmış değerlendirme yok"}
    if not measurement.reference_verified or measurement.lower is None or measurement.upper is None:
        return {"status":"ek ölçüm gerekli","reason":"Üretici koşullarına uygun doğrulanmış referans eksik"}
    if measurement.lower > measurement.upper:
        raise ValueError("Invalid reference interval")
    if measurement.circuit_state == "in_circuit":
        return {"status":"ek ölçüm gerekli","reason":"Devre içindeki paralel yollar ölçümü etkileyebilir"}
    if measurement.lower <= measurement.value <= measurement.upper:
        return {"status":"referans aralığında","reason":"Bu ölçüm doğrulanmış aralık içinde; tek başına sağlamlık kanıtı değildir"}
    return {"status":"referans dışında","reason":"Koşulları ve ölçümü tekrar doğrulayın; tek başına arıza kanıtı değildir"}
