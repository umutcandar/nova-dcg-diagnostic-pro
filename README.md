# NOVA DCG Diagnostic Studio V2

**Varsayılan uygulama:** `python gui.py` artık koyu temalı fotoğraf odaklı V2 çalışma alanını açar. Önceki `gui.py` servis sınıfı uyumluluk için korunmuştur.

## MacBook M1 — çalıştırma

```bash
cd ~/Desktop/nova-dcg-diagnostic-pro
source .venv/bin/activate
git pull --ff-only
python -m pip install -r requirements.txt
python gui.py
```

**Mac Finder sürükle-bırak:** İlk kurulumda `python -m pip install -r requirements.txt`
komutu `tkinterdnd2` paketini de yükler. Sonra Finder'dan bir JPG/PNG/WebP/BMP/TIFF
dosyasını doğrudan ortadaki **PCB GÖRÜNÜMÜ** alanına sürükleyip bırakın.
Dosya adı boşluk içerebilir. Yerel fotoğraf hemen açılır ve model taraması
otomatik başlar. Sürükle-bırak Mac'in Tk kurulumunda yüklenemiyorsa program
bunu bildirir; **Fotoğraf değiştir** düğmesi çalışmaya devam eder.
Mac'teki bazı Tk sürümlerinin beyaz sistem düğmesi problemine karşı
V2 kontrolleri yüksek kontrastlı, klavyeyle etkinleştirilebilen koyu
düğme yüzeyleri olarak çizilir.

## V2 araçları

- **Fotoğraf değiştir:** Üst araç çubuğundan yeni JPG/PNG/WebP kart seç.
- **Zoom:** Görüntü üzerindeyken fare tekerleği veya + / −. Yakınlaştırma imlecin bulunduğu noktayı korur.
- **Pan:** Fotoğrafı basılı tutup sürükle. **Sığdır** tüm kartı yeniden gösterir.
- **Parça seçimi:** Sol komponent listesi veya fotoğraftaki kutu. Sarı kutular **model tahminidir**, doğrulanmış parça kimliği değildir.
- **Fluke:** Sağ panel Ω, kapasitans, diyot, vb. modunu, güvenlik hazırlığını, prob talimatlarını ve sonraki kontrolü gösterir.
- **Doğrulanmış referans:** Nominal, tolerans, birim ve teknisyen onayı olmadan sayısal değer üretilmez.
- **Ölçüm geçmişi:** Manual Fluke okumaları komponent bazında tutulur. Yerel otomatik yedekler `~/.nova_dcg/autosave` altında; sunucuya yüklenmez.
- **Kaydet:** Ayrıca oturum JSON'u belirtilen yere dışa aktarılır.

**Sınırlar:** Gerçek model karttaki her parçayı bulamayabilir. Fotoğraftan güvenilir prob pinleri, nominal değerler veya kesin elektriksel arıza belirlenemez. Fluke okumaları manuel girilir.

## V2 eğitim altyapısı

Mevcut eğitim taksonomisi 14 sınıfa genişletildi; eski sınıf ID'leri korunur. Etiketleme ekranında her fiziksel karta sabit `board_id` verilmeli ve teknisyen etiketleri doğrulamalı.

Veri denetimi (model eğitmez):

```bash
python train_v2_pipeline.py /path/to/annotations /path/to/output --base-model models/yolov8s_pcb_best.pt --audit-only
```

Yerel M1 eğitimi (doğrulanmış etiketli veri gerektiğinden uzun sürebilir):

```bash
python train_v2_pipeline.py /path/to/annotations /path/to/output --base-model models/yolov8s_pcb_best.pt --epochs 70 --imgsz 960 --batch 4 --device mps
```

Pipeline farklı fiziksel kartları train / validation / test arasında ayırır; eğitimden sonra görülmemiş test kartları için metrikler kaydedilir. Test metrikleri ve 14 sınıf eşleşmesi doğrulanırsa eğitilmiş `best.pt` yerel `~/.nova_dcg/trained_model.json` kayıt dosyasında SHA256 değeriyle kaydedilir; **sonraki açılışta otomatik seçilir**. Kayıt veya dosya sonradan değiştirilirse güvenlik için açılmaz. **Şu anda yeni V2 modelinin eğitimi tamamlanmadı; gerçek ve doğrulanmış PCB fotoğraflarına ihtiyaç var.**

---
# NOVA DCG Diagnostic Pro — otomatik fotoğraf akışı (V1.5)

## MacBook M1: bir kez kur, ardından fotoğraf seç

Proje klasöründeki sanal ortam aktifken:

```bash
python -m pip install -r requirements.txt
python gui.py
```

- **Kart fotoğrafı seç** ile JPEG/PNG/WebP açıldığında model kontrolü, gerekirse yaklaşık **90 MB** eğitilmiş checkpoint'in SHA256 doğrulamasıyla indirilmesi ve YOLO taraması arka planda başlar. Arayüz donmaz; durum önizlemenin altında görünür.
- Komponent adayları kutularla işaretlenir ve en az bir aday bulunursa fotoğraf üzerinde ölçüm rehberi **kendiliğinden açılır**. Model tahminleri doğrulanmamıştır, otomatik arıza teşhisi değildir.
- İlk kurulumda Ultralytics bağımlılığı PyPI'den yüklenir. Doğrulanmış checkpoint kaynağı üçüncü taraf açık PCB modelidir. İnternet veya kurulum sorunu varsa uygulama nedenini gösterir; parça türü tahmin ediyormuş gibi davranmaz.
- Ölçüm değerleri Fluke üzerinden **manuel** girilir. Fotoğraftan güvenilir prob pinleri, gerçek nominal değer ve parça sağlamlığı belirlenemez.
- Otomatik model denetimi: `python -m unittest -v test_auto_detector`. Tk UI otomasyon testi GitHub Actions'da sanal ekranla çalıştırılır.

---

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


## Fotoğraftan yönlendirmeli ölçüm hedefi (V1.5 hazırlık)

İstenen iş akışı: PCB fotoğrafı yükle → eğitilmiş modelle komponent bölgelerini öner → görüntü üzerinde kutu çiz → teknisyen komponenti ve prob yerlerini doğrulasın → Fluke ölçümünü elle girsin → sonucu ihtiyatlı yorumla → sıradaki ölçümü öner. `guided_measurement.py` ilk görev oluşturma ve değerlendirme çekirdeğidir. **Görüntü üstü işaretleme, güvenilir pin/prob konumu, otomatik sıra belirleme ve GUI entegrasyonu henüz tamamlanmadı.** Model ağırlıkları ve gerçek fotoğraf testleri de yoktur. Tek fotoğraf veya tek direnç ölçümüyle sağlam/bozuk kararı verilemez; şema, veri sayfası ve devre içi paralel yollar dikkate alınmalıdır.
