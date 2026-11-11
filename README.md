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


## V0.8 - isteğe bağlı yerel YOLO modeli

**Model ile tara** düğmesi, kullanıcı tarafından sağlanan eğitilmiş `.pt` ağırlık dosyasını seçerek fotoğraftaki olası komponentleri listeler. Ek kurulum: `python3 -m pip install ultralytics`. Projede **eğitilmiş model ağırlıkları bulunmuyor**; dolayısıyla bu düğme tek başına otomatik tanıma sağlamaz. Model sınıfları `dataset.CLASSES` ile birebir eşleşmelidir. Sonuçlar doğrulanmamış önerilerdir. Ayrıntılar: `MODEL_SETUP.md`.

Testler: `python3 -m unittest test_guide.py test_diagnosis.py test_component_labeler.py test_dataset.py test_model_inference.py`.


## V0.9 - veri seti hazırlama ve yerel eğitim

`prepare_dataset.py`, doğrulanmış manuel etiketlerden aynı kartı farklı veri kümelerine dağıtmadan train/val/test klasörleri ve YOLO `data.yaml` oluşturur. JSON dosyalarına aynı fiziksel karta ait tüm fotoğraflarda aynı `board_id` alanı eklenmelidir. `train_model.py`, kullanıcı tarafından sağlanan yerel temel model ağırlıklarıyla isteğe bağlı eğitim başlatabilir. **Veri seti, eğitilmiş model ve doğrulanmış performans sonuçları henüz yoktur.** Ayrıntılar: `DATA_COLLECTION.md`.


## V1.0 - açık PCB modeliyle ilk entegrasyon

Kaynak: [wangshnegqi/pcb-component-detection-dataset-yolo](https://github.com/wangshnegqi/pcb-component-detection-dataset-yolo). Kaynağın `dataset/data.yaml` dosyasında 10 sınıf bulunduğu doğrulandı. `source_model.py` bunları NOVA'nın mevcut sınıflarıyla **yalnızca eşleşenler için** eşler; LED, Header, Crystal vb. farklı sınıfları 'Diğer' olarak korur. `model_inference.py` artık bu kaynağın eğitilmiş `models/yolov8s_pcb_best.pt` ağırlıklarını, dosya kullanıcı tarafından sağlandığında tanıyabilir. Model veya veri seti henüz NOVA deposuna kopyalanmadı; ilk eğitim ve gerçek kart doğruluk testi yapılmadı. Kaynağın README'sinde görüntü/etiketler CC BY 4.0, ağırlıklar Apache 2.0 olarak belirtiliyor. Atıf ve lisans dosyalarını inceleyin.

Kaynak modelle denemek için: kaynak depodan ağırlıkları indirip NOVA arayüzünde **Model ile tara** düğmesiyle seçin. Test: `python3 -m unittest test_source_model.py test_model_inference.py`.


## V1.1 - Mac olmadan kalite kontrol

GitHub Actions iş akışı her push ve pull request sonrası Python kaynak sözdizimini (`preflight.py`) ve `test_*.py` birim testlerini çalıştıracak şekilde eklendi. `python preflight.py` ve `python -m unittest discover -p 'test_*.py' -v` komutları yerelde de kullanılabilir. Bu değişiklik **GitHub Actions'ın başarıyla çalıştığı anlamına gelmez**; iş akışı sonuçları ayrıca kontrol edilmelidir. M1 Mac ve gerçek model çıkarımı testleri sonraya bırakıldı.
