"""Conservative offline datasheet catalog and verified-source lookup helpers.

Do not turn absolute maximum ratings into multimeter pass/fail thresholds.
"""
import json
from pathlib import Path
from urllib.parse import quote

def normalize_part_number(value):
    part=str(value).strip().upper()
    if not part or len(part)>80 or not all(c.isalnum() or c in "-_." for c in part):
        raise ValueError("Invalid part number")
    return part

def manufacturer_search_url(part_number):
    """A search link, not a verified datasheet."""
    part=normalize_part_number(part_number)
    return "https://www.google.com/search?q="+quote(part+" manufacturer datasheet pdf")

def save_verified_entry(folder, part_number, manufacturer, source_url, notes="", pinout=None):
    part=normalize_part_number(part_number)
    if not str(manufacturer).strip():
        raise ValueError("Manufacturer required")
    if not str(source_url).startswith("https://"):
        raise ValueError("HTTPS datasheet URL required")
    data={"part_number":part,"manufacturer":str(manufacturer).strip(),
          "source_url":str(source_url),"notes":str(notes),
          "pinout":pinout or {},"verified_by_technician":True,
          "measurement_limits":None}
    root=Path(folder)
    root.mkdir(parents=True,exist_ok=True)
    path=root/(part+".json")
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return path

def load_entry(folder,part_number):
    part=normalize_part_number(part_number)
    path=Path(folder)/(part.replace("/","_")+".json")
    return json.loads(path.read_text(encoding="utf-8"))

def interpret_measurement(entry,mode,value):
    """No fabricated expected range: return next verification requirements."""
    float(value)
    return {"status":"Ek doğrulama gerekli",
            "detail":"Datasheet sınır değerleri doğrudan devre içi Fluke ölçümü için sağlamlık eşiği değildir.",
            "source_url":entry.get("source_url",""),
            "next_step":"Pin dizilimi, test koşulları, kart şeması ve ölçüm modu doğrulanmalı."}
