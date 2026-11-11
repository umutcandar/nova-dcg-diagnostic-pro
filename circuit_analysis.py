"""Explainable, topology-aware checks based on user-entered net/component facts.

No circuit topology is inferred from photos. No definitive diagnosis.
"""
from collections import defaultdict

def analyze_circuit(components, nets, measurements):
    """Return ordered hypotheses.

    components: [{ref,type,nets:[...]}]
    nets: [{name,role}] role optionally 'ground' or 'supply'
    measurements: [{net,mode,value}]
    """
    known_nets={n["name"]:n for n in nets}
    members=defaultdict(list)
    for part in components:
        ref=str(part.get("ref","")).strip()
        if not ref:
            raise ValueError("Component reference is required")
        for net in part.get("nets",[]):
            if net not in known_nets:
                raise ValueError(f"Unknown net: {net}")
            members[net].append(part)
    findings=[]
    for measurement in measurements:
        net=measurement.get("net")
        if net not in known_nets:
            raise ValueError(f"Unknown measured net: {net}")
        try:
            value=float(measurement["value"])
        except (ValueError,TypeError,KeyError):
            raise ValueError(f"Invalid measurement for {net}") from None
        mode=str(measurement.get("mode","")).lower()
        if value < 0:
            findings.append({"priority":1,"net":net,"title":"Ölçümü doğrula",
                             "reason":"Negatif değer; bağlantı ve ölçüm modu kontrol edilmeli.",
                             "refs":[]})
        elif ("direnç" in mode or "resistance" in mode) and value < 2:
            connected=members.get(net,[])
            refs=sorted({str(x["ref"]) for x in connected})
            roles=known_nets[net].get("role","")
            if roles=="supply":
                title="Besleme hattında düşük direnç: bağlantılı elemanları sırayla incele"
                priority=2
            else:
                title="Düşük direnç: paralel yolları ve bobinleri değerlendir"
                priority=3
            findings.append({"priority":priority,"net":net,"title":title,
                             "reason":f"{net} üzerinde {value:g} Ω. Devre içi ölçüm tek başına kısa devre kanıtı değildir.",
                             "refs":refs})
    return sorted(findings,key=lambda f:(f["priority"],f["net"]))

def example_circuit():
    return {
        "nets":[{"name":"GND","role":"ground"},{"name":"VIN","role":"supply"},
                {"name":"VOUT","role":"supply"}],
        "components":[{"ref":"F1","type":"Fuse","nets":["VIN"]},
                      {"ref":"C1","type":"Capacitor","nets":["VIN","GND"]},
                      {"ref":"L1","type":"Inductor","nets":["VIN","VOUT"]}],
        "measurements":[{"net":"VIN","mode":"Direnç (Ω)","value":0.8}]
    }
