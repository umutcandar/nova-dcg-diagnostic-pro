# NOVA DCG PCB Studio — saha testi ve etiketleme

**Durum:** Özel erişimli web prototipi. Gerçek arızalı PCB'lerde genel doğruluk ve otomatik arıza teşhisi kanıtlanmadı. Modelin çizdiği kutular yalnızca öneridir.

## Fotoğraf ve Fluke ölçüm akışı

1. Render üzerinden NOVA DCG web uygulamasını aç. Kimlik bilgileri sadece Render Environment'da saklanmalı; GitHub koduna ekleme.
2. **Fotoğraf ekle** ile JPG/PNG/WebP yükle veya sürükle. 12 MB sınırı vardır. Sunucuda kalıcı fotoğraf depolanmaz.
3. Sarı model kutularını doğrula, hatalı adayları kaldır. Eksik parçaları **Elle işaretle** ile ekle. Model hata verirse manuel işaretleme kullanılabilir.
4. Kartı güvenli biçimde enerjisiz bırak, artık gerilimin olmadığını doğrula. Şebeke/yüksek gerilimli kartlarda bu prototiple ölçüm yapma.
5. Parça türünü doğrula, Fluke modunu seç, prob noktalarını şema/datasheet ile kontrol et, sonucu gir.
6. Yalnızca aynı ölçüm modu, ölçüm koşulu, kaynak, parça/nominal tanımı ve teknisyen onayı varsa referansla kıyasla. Devre içi ölçüm tek başına arıza kanıtı değildir.
7. **JSON raporunu indir**. Kayıtlar bu sayfadaki geçici oturuma aittir.

## Model eğitimi için etiket hazırlığı

1. Müşteri etiketleri, seri numaraları, kişisel veriler veya gizli tasarım içeren izinsiz fotoğrafları veri kümesine ekleme.
2. Fotoğraftaki **tüm görünür komponentleri** kutularla işaretleyip türünü onayla; yanlış model kutularını sil ve bilinmeyenleri çözümle.
3. Her fiziksel PCB için kararlı bir **board_id** yaz (`kart_001` gibi). Aynı kartın bütün fotoğraflarında aynı kimliği kullan.
4. Tüm görünür parçaları kontrol ettiğini onayla, **Eğitim etiketi JSON indir** düğmesini kullan.
5. Fotoğrafın orijinal dosyası ile indirilen JSON'u **aynı klasöre** koy. JSON'daki `image` alanı fotoğraf adına işaret eder.
6. Veri denetimini çalıştır:

```bash
python train_v2_pipeline.py /path/to/annotations /path/to/output --base-model /path/to/trusted_base.pt --audit-only
```

Web JSON'u `coordinate_system: "xyxy_normalized"`, `image_coordinate_space: "exif_transposed"`, `technician_verified: true`, `board_id`, `image` ve `regions` alanlarını taşır. Veri hazırlama betiği EXIF yönünü düzeltir; telefon fotoğraflarında kutuların kaymasını önler.

**En az 3 ayrı kart**, veri bölmenin minimum şartıdır, yüksek doğruluk kanıtı değildir. 30'dan az kart, 150'den az etiketli fotoğraf ve sınıflarda az örnek için eğitim denetimi uyarı verir.

## Otomatik testler

```bash
python -m unittest -v test_web_studio test_web_security test_web_dataset_alignment
node --test test_web_review.cjs
python -m unittest discover -p 'test_*.py' -v
```

GitHub Actions'taki `web-studio-smoke.yml`, kimlik doğrulamayı, kutu koordinatlarını, etiket biçimini ve referans kurallarını test eder. Bunlar henüz gerçek arızalı PCB'de bağımsız doğrulama değildir.
