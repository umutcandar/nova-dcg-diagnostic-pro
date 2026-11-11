"""Conservative, context-aware follow-up checks; no definitive fault verdicts."""
def next_checks(measurements, fault_description=""):
    description=str(fault_description).lower()
    recommendations=[]
    def add(priority, title, rationale):
        if title not in [item["title"] for item in recommendations]:
            recommendations.append({"priority":priority,"title":title,"reason":rationale})
    if not measurements:
        add(1,"Ölçüm planı oluştur","Enerjisiz ve deşarj edilmiş kartta güvenli test noktalarını belirleyin.")
    for row in measurements:
        mode=str(row.get("mode",""))
        point=str(row.get("point","bilinmeyen nokta"))
        try:
            value=float(row.get("value"))
        except (TypeError,ValueError):
            add(1,"Geçersiz ölçümü kontrol et",f"{point}: sayısal değer eksik.")
            continue
        if value < 0:
            add(1,"Negatif ölçümü doğrula",f"{point}: negatif değer beklenmiyor.")
        elif "Direnç" in mode and value < 2:
            add(2,"Düşük direnç için devre içi yolları incele",
                f"{point}: {value:g} Ω; paralel yol veya bobin normal düşük direnç gösterebilir.")
        elif "Diyot" in mode and value == 0:
            add(2,"Diyot ölçümünü iki yönde tekrarla",
                f"{point}: 0 V; prob teması ve paralel yolları kontrol et.")
    if any(word in description for word in ("açılmıyor","enerji yok","güç yok","çalışmıyor")):
        add(3,"Güç giriş yolunu incele","Şema ve üretici güvenlik prosedürüne göre sigorta, konnektör ve besleme yolunu enerjisiz kontrol et.")
    if any(word in description for word in ("ısın","sıcak","yanık")):
        add(3,"Termal hasar izlerini incele","Enerjisiz kartta kararma, çatlak ve hasarlı komponentleri görsel kontrol et.")
    if not recommendations:
        add(4,"Şema ile karşılaştır","Tekil ölçümler arızayı kanıtlamaz; nominal değer ve sağlam referans kartla karşılaştır.")
    return sorted(recommendations,key=lambda item:item["priority"])
