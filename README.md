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


## V0.4 - fotoğraf işaretleme ve PDF

Önce bağımlılıkları kurun:

```bash
python3 -m pip install -r requirements.txt
python3 gui.py
```

**Fotoğrafı işaretle:** Kart fotoğrafını seçtikten sonra görüntüde ölçüm noktalarına tıklayın ve numaralı PNG kaydedin. Bu dosya PDF raporunda kullanılır. **PDF servis raporu:** En az bir ölçüm girildikten sonra PDF kaydedin. Fotoğraf işaretleme otomatik komponent tanıma değildir. Fotoğrafın üzerine numaralar çizilir; ölçüm kayıtlarıyla otomatik eşleştirme henüz yoktur.

Mac M1 üzerinde uygulama açılışı ve PDF çıktı testi henüz yapılmadı.


## V0.5 - ölçüme dayalı kontrol öncelikleri

**Olası kontrolleri sırala** düğmesi, düşük direnç ve 0 V diyot okuması gibi ölçümler için kontrol önerileri gösterir. Bu **kural tabanlı** özelliktir; yapay zekâ veya kesin komponent teşhisi değildir. Uyarı çıkmaması kartın sağlam olduğunu göstermez. Test komutu: `python3 -m unittest test_guide.py test_diagnosis.py`.

Fotoğraftan otomatik komponent tanıma henüz geliştirilmedi; bunun için doğrulanmış görüntü veri seti ve model değerlendirmesi gerekecek.


## V0.6 - görüntü analizi için veri hazırlama

**Komponent etiketle** düğmesiyle kart fotoğrafında direnç, kondansatör, diyot, entegre, transistör, bobin ve konnektörleri elle dikdörtgen içine alın. Etiketleri, görüntü boyutuna göre normalize edilmiş koordinatlarla JSON olarak dışa aktarın. Bu aşama gelecekteki bir görüntü tanıma modeline veri hazırlamak içindir; **otomatik komponent algılama, OCR veya eğitilmiş model henüz bulunmuyor**. Etiketler doğrulanmamış kullanıcı girişidir.

Birim testleri: `python3 -m unittest test_guide.py test_diagnosis.py test_component_labeler.py`.
