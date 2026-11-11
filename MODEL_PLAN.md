# Komponent algılama geliştirme planı

## Şu an mevcut
- Kullanıcının elle çizdiği komponent kutuları ve sınıf etiketleri JSON olarak kaydedilir.
- `dataset.py` JSON kutularını doğrular ve YOLO biçimindeki normalize edilmiş kutu etiketlerine dönüştürür.
- Otomatik komponent algılayan eğitilmiş bir model **henüz yoktur**.

## Eğitim için gerekli veri
1. Farklı ışık, açı, çözünürlük ve PCB türlerinde, paylaşım izni bulunan kart fotoğrafları toplayın.
2. Komponentleri elle işaretleyin; bir ikinci kişi etiketleri doğrulasın.
3. Aynı kartın benzer fotoğraflarını eğitim ve test kümelerine dağıtmayın (veri sızıntısı).
4. Sınıf başına başarıyı precision, recall ve mAP ile raporlayın. Yanlış algılamaları ayrıca inceleyin.
5. Yalnızca yeterince doğrulanmış modelin tahminlerini kullanıcıya **öneri** olarak sunun; onay isteyin.

## Örnek dönüştürme
```bash
python3 dataset.py kart_etiketleri.json kart_etiketleri.txt
python3 -m unittest test_dataset.py
```

Etiket sınıf sırası `dataset.py` içindeki `CLASSES` listesidir. YOLO eğitimine ayrıca görüntü dosyaları, veri bölümü ve eğitim ortamı gerekir. Bu proje henüz model eğitimi veya otomatik arıza teşhisi yapmaz.
