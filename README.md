# NOVA DCG Diagnostic Pro V0.1

M1 MacBook ve Fluke multimetre ile manuel ölçüm kaydı için ilk Python prototipi.

## Başlatma

```bash
python3 diagnostic.py
```

`resistance` (ohm), `diode` (volt) veya `quit` yazın. Kayıtlar `measurements.json` dosyasına yazılır.

**Güvenlik:** Sadece enerjisiz ve artık gerilimi kontrol edilmiş düşük gerilimli devrelerde kullanın. Yazılım kesin arıza teşhisi yapmaz. Görsel arayüz, kamera analizi, yapay zekâ ve PDF henüz yoktur.
