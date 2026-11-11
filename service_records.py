"""Offline service job storage. No cloud sync and no automatic fault diagnosis."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

def safe_job_id(value):
    value=str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("Job ID must contain 1-64 letters, digits, underscore or hyphen")
    return value

def save_job(folder, job_id, device, notes="", measurements=None):
    job_id=safe_job_id(job_id)
    if not str(device).strip():
        raise ValueError("Device name required")
    if measurements is None:
        measurements=[]
    if not isinstance(measurements,list):
        raise ValueError("Measurements must be a list")
    root=Path(folder)
    root.mkdir(parents=True,exist_ok=True)
    path=root/(job_id+".json")
    record={"schema_version":1,"job_id":job_id,"device":str(device).strip(),
            "notes":str(notes),"measurements":measurements,
            "updated_at":datetime.now(timezone.utc).isoformat()}
    tmp=root/(job_id+".tmp")
    try:
        with tmp.open("w",encoding="utf-8") as stream:
            json.dump(record,stream,ensure_ascii=False,indent=2)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path

def load_job(folder,job_id):
    path=Path(folder)/(safe_job_id(job_id)+".json")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version")!=1 or data.get("job_id")!=job_id:
        raise ValueError("Unsupported or mismatched service record")
    return data

def list_jobs(folder):
    root=Path(folder)
    if not root.is_dir():
        return []
    result=[]
    for path in sorted(root.glob("*.json")):
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema_version")==1 and data.get("job_id")==path.stem:
                result.append({"job_id":path.stem,"device":data.get("device",""),
                               "updated_at":data.get("updated_at","")})
        except (OSError,ValueError,TypeError):
            continue
    return sorted(result,key=lambda x:x["updated_at"],reverse=True)
