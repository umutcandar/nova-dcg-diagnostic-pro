# NOVA DCG Diagnostic Pro V0.2

M1 MacBook üzerinde Fluke multimetre ölçümlerini **manuel** kaydetmek için masaüstü prototipi.

## Grafik arayüzü açma

```bash
python3 gui.py
```

macOS Python kurulumunda Tkinter bulunmalıdır. `python3 -m tkinter` ile kontrol edin. Yoksa Tk destekli Python kurulumu gerekir.

- İş/kart numarası ve fotoğraf dosyası seçimi (fotoğraf **analiz edilmez**)
- Direnç (Ω) ve diyot (V) değerlerini elle girme
- İhtiyatlı ön değerlendirme
- JSON ve CSV kayıt dışa aktarma

Eski terminal sürümü: `python3 diagnostic.py`.

**Sınırlar:** Gerçek kart üzerinde doğrulanmadı; otomatik teşhis, yapay zekâ, kamera üzerinden komponent tanıma ve PDF raporu henüz yok. Yalnızca enerjisiz, artık gerilimi doğrulanmış düşük gerilimli kartlarda kullanın. Şebeke/yüksek gerilimli kartlarda kullanmayın.

## V0.3 ölçüm rehberi

Arayüzde **Kontrol rehberi** menüsünden Güç girişi, Sigorta, Diyot, Kondansatör veya Direnç seçip **Ölçüm adımlarını göster** düğmesini kullanın. Rehber kesin teşhis sunmaz. Rehber mantığı `guide.py` dosyasındadır. Basit birim testleri: `python3 -m unittest test_guide.py`.
