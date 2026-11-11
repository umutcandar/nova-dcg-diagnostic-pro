"""NOVA DCG Diagnostic Pro V0.1: offline manual measurement log."""
import json
from datetime import datetime
from pathlib import Path

def assess(mode, value):
    if value < 0:
        return "Geçersiz negatif ölçüm."
    if mode == "resistance":
        if value < 2:
            return "Çok düşük direnç; kısa devre ihtimalini ve paralel yolları kontrol et."
        return "Direnç kaydedildi; nominal değer bilinmeden sağlamlık doğrulanamaz."
    return "Diyot gerilimi kaydedildi; ters yön ölçümü ve devre etkileri kontrol edilmeli."

def main():
    print("NOVA DCG Diagnostic Pro V0.1 - sadece enerjisiz kartlar")
    print("Ölçmeden önce artık gerilim olmadığını doğrula.")
    entries = []
    while True:
        mode = input("Mod (resistance/diode/quit): ").strip().lower()
        if mode == "quit":
            break
        if mode not in ("resistance", "diode"):
            print("Geçersiz mod.")
            continue
        point = input("Test noktası: ").strip()
        try:
            value = float(input("Değer (ohm veya V): ").replace(",", "."))
        except ValueError:
            print("Sayısal değer gir.")
            continue
        note = assess(mode, value)
        print(note)
        entries.append({"point": point, "mode": mode, "value": value, "assessment": note})
    if entries:
        Path("measurements.json").write_text(
            json.dumps({"created": datetime.now().isoformat(), "entries": entries},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print("Ölçümler measurements.json dosyasına kaydedildi.")

if __name__ == "__main__":
    main()
