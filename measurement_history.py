"""Per-component measurement history with validated numeric entries."""
from datetime import datetime, timezone
import math

def record_measurement(task, reading, status, detail="", mode=None, unit=None):
    number=float(str(reading).replace(",", "."))
    if not math.isfinite(number):
        raise ValueError("Ölçüm sonlu bir sayı olmalı")
    entry={
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value": number,
        "mode": mode or task.get("mode",""),
        "unit": unit or task.get("unit",""),
        "status": status,
        "detail": detail,
    }
    task.setdefault("measurement_history",[]).append(entry)
    task["reading"]=number
    task["status"]=status
    return entry

def history_text(task):
    history=task.get("measurement_history",[])
    if not history:
        return "Bu komponent için kayıtlı ölçüm yok."
    return "\n".join(
        f'{n}. {entry["value"]:g} {entry.get("unit","")} | {entry.get("mode","")} | {entry.get("status","")} | {entry.get("timestamp","")}'
        for n,entry in enumerate(history,1)
    )
