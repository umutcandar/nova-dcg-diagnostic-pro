# NOVA DCG — İkinci Görsel Yapay Zekâ: Gerçek Test Kanıtları (19 Kasım 2026)

## Neden ikinci model geliştirildi?

Canlı sistem, resmî SHA256 kimliği doğrulanmış **21 sınıflı YOLO ONNX** ile
komponentler için *öneri* üretir. Komponent 7 gibi yanlış *diyot* etiketleri
mümkündür. İkinci yapay zekâ ile ilk tahmini bağımsız görüntüden yeniden
incelemek istiyoruz. **Gövde görünümü veya model skorundan parça nominal
değeri, pin yönü, elektriksel sağlamlık veya arıza sonucu çıkarmayız.**

İlk model ile ikinci model arasında farklı mimari ve eğitim kaynağı vardır:
YOLO (Arshia82sbn kaynaklı 21 sınıf) ve **MobileNetV3-Small** (lisanslı
4TU PCB-MC-C araştırma fotoğraflarında eğitilmiş parça kırpıntısı modeli).
Görüntüler yerel ONNX inference için kalır; fotoğrafları herhangi bir
üçüncü taraf görsel API'sine otomatik göndermiyoruz.

## Bağımsız görsel model V1: sadece kondansatör / diyot

- Eğitim kaynakları: doğrulanmış PCB-MC-C fold 0, train ve validation fiziksel
  kart bazlı ayrı. 12 epoch, ImageNet ön-eğitimli MobileNetV3-Small
  dondurulmuş görüntü özelliği çıkarıcısı.
- İki sınıf: **capacitor** (normal + elektrolitik), **diode** (normal + Zener).
- En iyi 7. tur: validation **macro-F1=0,9023**;
  kapasitör **440/450** (%97,78), diyot **45/54** (%83,33).
- ONNX SHA256: `0b5dfc6fff65d2944c3c150580978dcdb69b5bec90a4ff7bff4bdabb33409439`.
- Eğitim ve ağırlık: https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44586413233

**Gerçek YOLO kutularında bağımsız test:**

- Başka yayıncıya ait 13 CC BY 4.0 PCB fotoğrafında YOLO'nun **108**
  kapasitör/diyot aday kırpıntısı ikinci modele verildi.
- 5 farklı aile önerisi; etiketiyle eşleştirilebilen doğru ana-model
  önerilerinden **2'si gereksiz yere çelişkili** gösterildi.
- Bağımsız doğrulanmış bir yanlış diyot→kondansatör düzeltmesi kanıtlanmadı.
- V1 binary model yanlış pozitif nesne/bakır yol/solder joint için
  üçüncü bir **other/background** sınıfına sahip değildir.
- Dış testte yalnız **2 gerçek diyot** etiketi olduğu için sahadaki
  diyot performansı hakkında genel oran vermiyoruz.
- Sonuç: **canlı kullanıma alınmadı**.
- Dış test: https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44588017665

## Bağımsız görsel model V2: kondansatör / diyot / diğer komponent

- Üçüncü sınıf: 4TU'nun etiketli diğer komponentleri — direnç, sigorta,
  entegre, konektör vb. Bu **boş PCB yüzeyi** ya da sınıfsız lehim
  bölgeleri için geniş bir negatif veri kümesi **değildir**.
- Sınıflar içinde nadir **112 elektrolitik**, **9 Zener** eğitim
  örneği özellikle korunarak dengeli örnekleme yapıldı.
- 12 epoch, en iyi 12. tur, validation **macro-F1=0,7715**.
- Kondansatör **383/450** (%85,11), diyot **32/54** (%59,26),
  diğer komponent **394/502** (%78,49).
- ONNX SHA256: `5d93c46f30af29d29f45db0b3a0b488a2a7fad9408331a19e05d0e24ac762415`.
- Eğitim ve ağırlık: https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44589148579

**Gerçek YOLO kutularında bağımsız test:**

- Aynı **13 fotoğraf**, 536 toplam ilk-model tespiti, 164 diyot veya
  kondansatör aileli model tahmini, bunların 108'i ayrıca değerlendirildi.
- **28** farklı aile önerisi; **26** öneride ikinci model “other” dedi.
- **19** güçlü çelişki uyarısı üretildi. Etiketli doğru kutularla eşleşen
  29 ana-model doğru tahmininin **9'u gereksiz güçlü uyarı** aldı.
- Etiketiyle eşleştirilebilen parçalarda kanıtlanmış faydalı otomatik
  sınıf düzeltmesi **0**; etiketleri kendiliğinden değiştirme **0**.
- Sadece 2 dış veri diyotu olduğu için modelin gerçek diyot sahası
  başarısı bilinmiyor.
- Sonuç: **canlı kullanıma alınmadı**.
- Dış test: https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/runs/44590261536

## Yanlış pozitifleri gerçekten azaltmak için gerekli veri

Üç sınıflı diğer-komponent sınıfı, parça olmayan bölgeleri temsil etmez.
Bu yüzden ikinci AI, YOLO'nun işaretlediği lehim pedi, baskı devre izi veya
başka yanlış pozitifler hakkında güvenilir "burada parça yok" kararı veremez.

Devam çalışması için **farklı fiziksel kartlara ait** tam etiketli fotoğraflar
ve denetlenmiş “no component/background” kırpıntıları gerekli. Özellikle
diyot, elektrolitik kondansatör ve Zener diyot örnekleri çok azdır. Farklı
kartlar, ışık, kamera ve parça boyutları eğitim, doğrulama ve testte
birbirine karıştırılmamalıdır.

Ayrıca yeni modele yalnız kusursuz etiket kutularından kesilmiş görüntü
değil, **ilk YOLO'nun gerçek tespit kutularındaki hatalı kadrajlar** da
gösterilmeli. Yine yalnız bağımsız kartlarda fayda kanıtlanırsa gündeme alınır.

## Canlı sistemin güvenli davranışı

- İlk 21-sınıflı ONNX **aynen çalışmaya devam eder**.
- İnsan tarafından onaylı etiketler hiçbir ikinci model tarafından
  değiştirilmez.
- `pcb_secondary_inference.py` araştırma çıktısını ancak yerel ONNX
  modelinin SHA256 + kaynak denetimi + **ayrıca yayın onayı** varsa ve açıkça
  etkinleştirilmişse kullanabilir. Normal ayar **devre dışıdır**.
- İkinci görsel öneriler, kanıtı güçlü değilse otomatik şüpheli sınıf alarmı
  üretmez; güçlü olsa bile *teknisyen incelemesi* ister.
- Fluke üzerinde kesin değer aralığı ancak parça kodu, üretici datasheet'i,
  şema, ölçüm modu ve koşullar doğrulandığında gösterilebilir.
- Üçüncü taraf API'lerine kullanıcı PCB fotoğrafı otomatik gönderilmez.
- Prototip ağırlıkların ticari kullanımdaki lisansları ayrıca incelenmelidir.

## Otomatik yayın engeli

`pcb_secondary_release_gate.py` gerçek dış testleri inceler; nadir diyot
verisi, gereksiz çelişki uyarısı, bağımsız servis kartı doğrulamasının
eksikliği ve lisans durumunu inceleyerek ikinci modelin canlıya geçmesini
**bloklar**. Başarılı bir laboratuvar skorunu üretim onayıyla karıştırmaz.

- Otomatik kapı: https://github.com/umutcandar/nova-dcg-diagnostic-pro/actions/workflows/pcb-secondary-release-gate.yml
