# NOVA DCG — PCB eğitim ve bağımsız test kayıtları

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
