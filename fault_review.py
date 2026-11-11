"""Conservative fault-review queue: prioritize checks, never declare a component failed."""
def review_queue(tasks):
    rows=[]
    for i,task in enumerate(tasks):
        history=task.get("measurement_history",[])
        statuses=[str(h.get("status","")).lower() for h in history]
        last=statuses[-1] if statuses else ""
        if "referans dışında" in last:
            priority=0
            reason="Son ölçüm referans dışında; koşulları ve referansı doğrulayın."
        elif "ek ölçüm" in last:
            priority=1
            reason="Son ölçüm için ek doğrulama gerekiyor; tek başına sağlamlık kanıtı değildir."
        elif not history:
            priority=2
            reason="Henüz ölçüm kaydı yok."
        else:
            priority=3
            reason="Ölçüm kaydı var; tek başına sağlamlık kanıtı değildir."
        if task.get("reference_result",{}).get("status","").lower().find("referans dışında")>=0:
            priority=0
            reason="Doğrulanmış referans karşılaştırması aralık dışında; yeniden ölçün."
        rows.append({
            "index":i,
            "component":str(task.get("id",i+1)),
            "label":str(task.get("source_label",task.get("component","Bilinmiyor"))),
            "priority":priority,
            "reason":reason,
            "measurements":len(history),
        })
    return sorted(rows,key=lambda row:(row["priority"],row["index"]))
