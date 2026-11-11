"""Conservative evidence-based prioritization, not automated fault identification."""
from dataclasses import dataclass

@dataclass
class Finding:
    title: str
    priority: str
    reason: str
    next_step: str

def prioritize(measurements):
    """Only suggest checks; never assert a specific component is defective."""
    findings=[]
    for item in measurements:
        point=str(item.get("point","")).strip() or "Bilinmeyen nokta"
        mode=str(item.get("mode",""))
        try:
            value=float(item.get("value"))
        except (ValueError,TypeError):
            continue
        if not (0 <= value < float("inf")):
            continue
        if mode in ("Direnç (Ω)","resistance") and value < 2:
            findings.append(Finding(
                point + ": düşük direnç", "Kontrol gerekli",
                f"{value:g} Ω ölçüldü. Devre içi paralel yollar veya düşük empedanslı yük normal olabilir.",
                "Enerjiyi kesilmiş tutun; şema ve besleme hattı yapısını kontrol edin. Uygunsa izole ölçüm yapın."))
        elif mode in ("Diyot (V)","diode") and value == 0:
            findings.append(Finding(
                point + ": 0 V diyot okuması", "Kontrol gerekli",
                "0 V ölçüldü; prob teması, paralel yollar veya kısa devre olasılıkları ayrıştırılmalı.",
                "Probları ters çevirerek karşılaştırın; devre şemasını inceleyin."))
    if not findings:
        findings.append(Finding(
            "Belirgin uyarı yok", "Yetersiz kanıt",
            "Girilen ölçümler bu sınırlı kurallarda bir uyarı üretmedi; kartın sağlam olduğu anlamına gelmez.",
            "Nominal değerleri, kart şemasını ve arıza belirtisini ekleyerek ölçümleri genişletin."))
    return findings
