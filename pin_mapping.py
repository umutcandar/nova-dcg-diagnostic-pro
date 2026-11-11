"""Pin roles and photo coordinates must be technician-confirmed.

Datasheet pin numbering alone cannot locate pins on an arbitrarily rotated photo.
"""
import math

def suggest_probe_pair(pinout, photo_pins, red_role, black_role):
    if not pinout.get("technician_verified"):
        raise ValueError("Datasheet pinout must be verified")
    roles=pinout.get("pins",{})
    if not isinstance(roles,dict) or not roles:
        raise ValueError("Pinout has no pin roles")
    candidates={}
    for role in (red_role,black_role):
        numbers=[str(number) for number,name in roles.items() if name==role]
        if len(numbers)!=1:
            raise ValueError("Role must match exactly one pin: "+role)
        number=numbers[0]
        point=photo_pins.get(number)
        if not isinstance(point,(list,tuple)) or len(point)!=2:
            raise ValueError("Photo location not confirmed for pin "+number)
        if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in point):
            raise ValueError("Invalid photo point")
        candidates[role]={"pin":number,"point":list(point)}
    if candidates[red_role]["pin"]==candidates[black_role]["pin"]:
        raise ValueError("Probe roles must map to different pins")
    return {"red":candidates[red_role],"black":candidates[black_role],
            "status":"Teknisyen onayı bekleniyor",
            "note":"Pin numaraları ve fotoğraf yönü ayrı ayrı doğrulanmalı; öneri otomatik güvenli ölçüm kararı değildir."}
