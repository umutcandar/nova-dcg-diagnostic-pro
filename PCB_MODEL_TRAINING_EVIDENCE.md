# NOVA DCG — PCB eğitim ve bağımsız test kayıtları

## 17 Kasım 2026 — PCB-MC gerçek arşiv, ZIP64 ve poligon veri kalitesi

Resmî 4TU PCB-MC-C veri arşivi doğrulandı: `PCB_MC.zip`,
3.772.070.324 bayt, yayımcının MD5 değeri
`1533d1ca6d54c37b19c1a94297c0745c`. Bağımsız küçük aralık
okumalarıyla 30.944 ZIP64 kaydı sayıldı; `images/PCB-MC-C/kfold_data/fold_N/{train,valid}/`
altında 5 katlamada toplam 3.075 JPG fotoğraf kaydı bulundu.
COCO anotasyonları her katlamanın train/valid bölümünde ayrı:
`components_only_foldN_train_annotations.json` ve
`components_only_foldN_valid_annotations.json`.

- Resmî arşiv indeks doğrulaması:
  https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44140550708
- İlk tam 3,77 GB indirme ve 23 sınıf eğitim denemesi:
  https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44141714858
- İlk deneme MD5 doğrulama sonrasında bir karışık YOLO etiketi yüzünden
  eğitim öncesinde güvenle durduruldu.
- Sorunlu gerçek dosya salt-okunur HTTP Range yöntemiyle ayrı incelendi.
  `pcb163rec1_jpg.rf.e09413b54fb81bd55aa9f7db2f5001b9.txt` 11.
  satırı **bir Capacitor sınıfı + 4 kapalı çokgen noktası** içeriyor,
  beş sütunlu dikdörtgen kutu değil. Kaynakta 21 kapasitör etiketi vardı.
- Yeni `_strict_yolo_label` yalnız doğrulanmış YOLO çokgenlerini
  `min/max(x,y)` kullanarak kapsayıcı dikdörtgen kutuya çevirir ve
  `import_audit.json` içine her dönüştürmeyi kaydeder. Belirsiz,
  sınır dışı veya dejenere çokgenler reddedilir. Kaynak ZIP değiştirilmez.
- Tek gerçek sorunlu etiket uzaktan tekrar okunup yeni dönüştürücüyle
  doğrulandı: satır 11 = `1 0.819320886 0.518027597 0.024495855 0.083881930`.
  Eğitim için bu aşamada bütün kaynak veri arşivini yeniden indirmeye
  gerek duyulmadı.
- Bu çözümün **tüm katlamadaki** karışık biçimleri temizlediği henüz
  kanıtlanmış sayılmaz; 23 sınıflı modelin gerçek eğitim sonucunu
  ayrı denemede doğrulamak gerekir.
- Kaynak tek satır doğrulaması:
  https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44143393469
- Yeni eğitim denemesi:
  https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44143570427

Güncel web etiketleri 28 teknisyen inceleme sınıfı içerir. Bunlar arasında
**Elektrolitik Kondansatör, Zener Diyot, Ferrit Boncuk ve Jumper** vardır.
Canlı ONNX tahmin modeli ise halen **21 otomatik sınıfta** çalışır;
yeni etiketlerin kendiliğinden öğrenildiği iddia edilemez.

---


## 17 Kasım 2026 — 36 epoch ve üç modelin aynı veri üzerindeki karşılaştırması

36 epoch, 640px YOLOv8n `candidate10.onnx` gerçekten eğitildi;
kaynak veri 117 eğitim / 13 doğrulama görüntüsüdür. Eğitim raporu:
https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44115087646

- Adayın yayımlanan doğrulama sonuçları: precision 0,6478;
  recall 0,2180; mAP50 0,2609; mAP50-95 0,1288.
- 6 epoch deneme: mAP50 0,0930. 36 epoch eğitim bu değeri artırdı,
  ama üretimdeki 21-sınıf ONNX'e otomatik geçiş gerekçesi değildir.
- **Eşit ölçüm sözleşmesi**: aynı 13 gerçek görüntü, IoU >=0,5, skor >=0,28;
  karşılaştırılabilen 6 ortak sınıf ve 169 etiketli parça.

| Yöntem | Doğru konum + sınıf | Oran | Kondansatör |
| --- | ---: | ---: | ---: |
| Eski 21-sınıf ONNX — tek görüntü | 51/169 | %30,18 | 10/59 |
| Eski 21-sınıf ONNX — önceki 3x3 detaylı | 91/169 | %53,85 | 29/59 |
| Yeni 10-sınıf aday — tek görüntü | 37/169 | %21,89 | 15/59 |

Eşit yöntemle karşılaştırma:
https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44134064015

### Dört ve sekiz bin piksellik fotoğraflarda karo boşluklarının kapatılması

Önceki 3x3 sabit pencereler kaynak 4K/8K görüntülerde bazı piksel
şeritlerini atlayabiliyordu. İlk düzeltmede pencereleri büyütmek
test doğruluğunu %53,85'ten **%43,20'ye düşürdü**; bu regresyon
fark edilip yaklaşım değiştirildi. Son algoritma başarılı özgün karo
yerlerini korur, yalnız aradaki boşluklara yeni taramalar ekler ve
en fazla 25 CPU taraması yapar. Aynı 13 resim üzerinde:

- Tek görüntü: 51/169, **%30,18**
- Yeni detaylı algoritma: **100/169, %59,17**
- Kondansatör: **32/59** doğru konum+sınıf
- Eski detaylı algoritma: 91/169, %53,85

Son ölçüm:
https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44135238512

Bu sonuçların hiçbiri geniş saha doğruluğu veya bağımsız fiziksel-kart
temelli mAP değildir. Diyot için yalnız 2 gerçek etiket vardır ve
hiçbiri doğru sınıflandırılmamıştır; yeni eğitim verisi gereklidir.
Gerçek müşteri kartlarında ayrıca kör test yapılmadan "hazır arıza
teşhisi" iddiası doğru olmaz.

### Veri sızıntısı kontrolleri

`train_v2_pipeline.py` artık aynı fotoğrafın SHA-256 içerik kopyasını
farklı `board_id` altında eğitim/test verisine almaz; belirsiz
`Bilinmiyor` sınıfının eğitim etiketi olarak kullanılmasını da
reddeder. Bu kontroller aynı görüntünün kayıpsız kopyalarını yakalar;
döndürülmüş, kırpılmış veya farklı ışıkta çekilmiş aynı kartın tüm
görünümlerinin tek fiziksel kart kimliğiyle etiketlenmesi ayrıca gerekir.


Bu dosya, gerçek model deneylerini ve veri/izin sınırlarını kaydeder. Model her
kartı doğru tanıyor, her parçanın değerini biliyor veya arızayı otomatik
belirliyor iddiası **yoktur**.

## Üretimdeki 21 sınıflı temel model

Arshia82sbn YOLOv8s ONNX modelinin sabit SHA-256 kimliği:
`bfc398bb93ce61d9d7d00389db51b651bd90c4e2141163a0ae6dad79a247ae29`.
Bu ağırlıkların yayıncısının bildirdiği mAP50=0,619, kaynak veri üzerindedir;
NOVA sahasında teyit edilmemiştir.

Bağımsız küçük değerlendirme kaynağı: 130 resimli, 10 sınıflı Wangshnegqi
dataseti (117 train / 13 validation), CC BY 4.0. Kaynak commit:
`0d7ae7310fa607389779b6132285336ad73e96e1`.
Yalnız kesin eşleşen altı sınıf (Direnç, Kondansatör, Diyot, LED, Entegre,
Konnektör) karşılaştırılır; Switch/Button, Header, Crystal, Debug/TP
eşdeğer kabul edilmez.

| Metrik | Tek 640px tarama | Ayrıntılı karo tarama |
| --- | ---: | ---: |
| Karşılaştırılabilir etiket | 169 | 169 |
| Konumsal eşleşme, IoU>=0.5 | 73 | 117 |
| Doğru konum + doğru sınıf | 51 | 91 |
| Oran | %30,18 | %53,85 |
| Kondansatör doğru | 10/59 | 29/59 |
| Diyot doğru | 0/2 | 0/2 |

Bunlar çok küçük ve fiziksel-kart ayrımı bağımsız denetlenmemiş bir veri
kümesindeki keşif ölçümleridir; yayın düzeyinde mAP veya saha güvenilirlik
garantisi değildir.

- Temel koşum: https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44112887568
- A/B koşum: https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44114484446

Büyük görüntüde ayrıntılı ONNX tarama küçük komponentlerin ayrıntısını korur.
Uygulama bu tarama başarısız olursa standart taramaya döner.
NOVA_DETAILED_SCAN=0 ile ayrıntılı tarama kapatılabilir.

## Gerçek yeni eğitim

Kod: `pcb_train_candidate.py`. Açık ve CC BY 4.0 olarak kredilendirilmiş
117 train / 13 valid fotoğrafta YOLOv8n tabanlı **ayrı 10 sınıflı yardımcı
aday model** gerçekten eğitildi. Altı epoch / 512px ilk denemede:
`mAP50=0.0930, recall=0.0889`. En iyi ağırlıklar ve ONNX artifacts olarak
saklandı; üretim modeli değiştirilmedi.

- https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44113896875
- `.github/workflows/pcb-train-candidate.yml` ile CPU üzerinde uzun eğitim
  deneyi yürütülebilir. GitHub artifacts 30 gün saklanır.

Bu 10 sınıf, 21 sınıflı temel modelin yerini otomatik olarak alamaz;
öğretilmemiş sınıflara yeteneği yoktur. Ayrıca 13 fotoğraflık val setinin
bağımsız *board_id* gruplarına sahip olduğu kanıtlanmadı. Kaynak val sonucu
bağımsız saha testinden farklıdır. Üretim için ayrı kart tabanlı test gerekir.

## Daha büyük lisanslı veri kaynakları

- PCB-MC (University of Twente; CC BY 4.0):
  https://doi.org/10.4121/7c6e5bda-eecf-4feb-8a3a-7f823b1b0140.v2
  615 fotoğraf, 197 ayrı fiziksel kart düzeni, 23 var olan komponent sınıfı,
  ayrı eksik parça sınıfları ve board-aware 5-fold. 3,77 GB ZIP verisi
  ücretsiz Render'a koyulmaz. COCO etiketleri ve resmî fold ayrımı korunmalı.
- ElectroCom61 (Mendeley Data v2, CC BY 4.0):
  https://data.mendeley.com/datasets/6scy6h8sjz/2
  2.121 anotasyonlu fotoğraf ve 61 parça; tekil nesnelerde ek ön eğitim için
  yararlı ancak yoğun PCB üzerinde testin yerine geçmez.
- Arshia modelinin 21 sınıflı orijinal Roboflow verisi:
  https://universe.roboflow.com/arshiasbn-4s0xh/detecting-the-pcb-object
  MIT duyurusu altında. Aynı modelin kendi eğitim görselleri bağımsız test
  değildir. Hugging Face veri kümesi kartının 780 KB içeriği tüm görüntüleri
  barındırmaz.
- Wangshnegqi gerçek PCB dataset, CC BY 4.0:
  https://github.com/wangshnegqi/pcb-component-detection-dataset-yolo

İzinsiz müşteri kartlarını, seri numaralarını veya özel şemaları halka açık
veri kümesine göndermeyin. Görsellerin kaynak, lisans, kart kimliği ve
etiket denetimi raporlanmalı.

## Eğitim kabul protokolü

1. Fiziksel kart başına sabit board_id. Aynı kartın tüm fotoğrafları aynı
   train/validation/test bölmesinde kalır; kopyalar ve döndürülmüş tekrarlar
   kontrol edilir.
2. 24 etiketlik web inceleme taksonomisi ile 21 sınıflı model isimleri
   farklıdır. MOSFET, Header gibi yeni sınıflar veri bulunmadan mevcut
   ONNX modelinde varmış gibi gösterilmez.
3. Teknik personel bütün görünür elemanların sınıfını ve kutusunu doğrular,
   yanlış etiketli görüntüler ayrı incelenir.
4. Yüksek çözünürlük/karo, 640px tarama ve farklı eğitim denemeleri aynı
   bağımsız test kartlarıyla karşılaştırılır.
5. Özellikle elektrolitik kondansatör, diyot ve trimpot karışmalarının
   confusion matrix ve per-class recall değerleri incelenir.
6. Yeterli veri, bağımsız test, model sınıf sırası, SHA-256 ve lisans uygunluğu
   kanıtlanmadan yeni ağırlıklar Render uygulamasına alınmaz.

## Elektriksel ölçüm değeri ayrı konudur

Fotoğrafta gövde tanınması parçanın nominal kapasitesi, direnç toleransı,
ESR değeri, devre içi aralığı veya arıza durumunu ispatlamaz. Kod/renk
okunması, parça datasheeti, şema, Fluke modu ve ölçüm koşulları ayrıca
doğrulanmalıdır. Kesin aralık verisi olmayan elemana sayısal sağlamlık
eşiği uydurulmaz.

## Ticari lisans

Kaynak datasetinin CC BY veya model kartının MIT olması, Ultralytics
YOLO/AGPL mimarisi ve eğitim araçlarıyla ilgili yükümlülükleri ortadan
kaldırmayabilir. Lisans incelemesi:
https://www.ultralytics.com/license

Bu belge hukuki tavsiye değildir. Ticari entegrasyon öncesi lisans
uyumluluğunu netleştirin.


## PCB-MC 23 sınıflı tam eğitim hattı (hazır, büyük veri henüz indirilmedi)

Bu kısım **eğitim yapıldı** anlamına gelmez. 4TU tarafından yayımlanan
**3,77 GB** veri kümesinin tamamı henüz çalışma ortamına indirilip
model eğitilmedi. GitHub içinde ham veri yüklemiyoruz, Render ücretsiz
web servisini eğitici olarak kullanmıyoruz.

- Kaynak DOI: https://doi.org/10.4121/7c6e5bda-eecf-4feb-8a3a-7f823b1b0140.v2
- Dataset resmi ZIP MD5: `1533d1ca6d54c37b19c1a94297c0745c`.
  Dosyayı indirince hash doğrulanmalı (Mac: `md5 PCB_MC.zip`).
- Akademik kaynak kodu: https://github.com/betvillab/PCB-MC
- **Dikkat:** Veride 23 var olan + 8 eksik komponent etiketi bulunur.
  NOVA parça tanıma eğitiminde **PCB-MC-C (yalnız mevcut parçalar)**
  kullanılmalı; yokluğu algılayan etiketler karıştırılmamalı.
- Yeni `pcb_mc_import.py` bu 23 sınıfı kaynak COCO'dan dönüştürür,
  **Elektrolitik Kondansatör** ile **Kondansatör**, **Zener Diyot** ile
  **Diyot** ayrımını korur. Resmi `components_only_splits.json`
  kart bazlı 5-fold ayrımı değiştirmeden yükler.
- `pcb_mc_train.py` resmi fold ile gerçek 23-sınıflı eğitimi
  başlatabilir; ilk şart: elde gerçek ZIP, fotoğraflar, görev C COCO
  anotasyonları, resmi manifest olmalı. Eğitim sonrası ağırlıklar
  **otomatik canlıya alınmaz**.

Aşağıdaki örnekler, resmi veri paketinin tam yapısı doğrulandıktan
sonra çalıştırılmak üzere hazırlanmıştır:

```bash
# Dataseti resmi 4TU'dan edinip ZIP'in MD5 değerini doğrula.
python pcb_mc_import.py   --images-dir ~/Downloads/PCB-MC/images   --coco-file ~/Downloads/PCB-MC/annotations/PCB-MC-C/annotations.json   --fold-manifest ~/Downloads/PCB-MC/splits/components_only_splits.json   --output ~/nova-pcb-mc/fold0 --fold 0
python pcb_mc_train.py   --prepared ~/nova-pcb-mc/fold0 --output ~/nova-pcb-mc/experiments/fold0   --epochs 60 --imgsz 960 --batch 4 --device mps
```

Yayın dosya yapısındaki COCO anotasyonları tek dosya değilse,
`--coco-file` yolunun her fold'a göre ayarlanması veya importer
adaptasyonu gerekir. Kaynak arşiv gerçekten kontrol edilmeden bunun
kesin çalıştığı iddia edilmez.

**Kabul şartı:** 5-fold per-class ölçümlerin tamamı, kontrol setinde
elektrolitik-kondansatör / diyot karışmaları, model lisansı, model SHA256
ve hiç görülmemiş NOVA müşteri kartlarında teknisyen incelemesi.
